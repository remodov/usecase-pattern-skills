# Kafka — реализация на Python (aiokafka)

Реализация язык-нейтрального контракта `../spec.md` (`R-KFK-*`) на Python с **aiokafka** (async-native;
`confluent-kafka` — альтернатива для высокой пропускной). Коды общие с Java; меняется клиент, семантика одна.

## 1. Producer (`R-KFK-PROD-*`)

`kafka/producer-is-idempotent` — идемпотентный producer: `AIOKafkaProducer(enable_idempotence=True)` (тянет `acks="all"`,
бесконечные retries, `max_in_flight ≤ 5`). `kafka/partition-key-required` — `key=` обязателен для бизнес-событий = **aggregate id**
(`key=str(order.id).encode()`) — ordering per-aggregate. `kafka/serialization-format` — JSON-сериализация
(`value_serializer=lambda v: json.dumps(v).encode()`); Avro/Protobuf + Schema Registry — для bandwidth-топиков.
`kafka/publish-via-outbox` — domain-события **не** через прямой `producer.send_and_wait(...)` из handler — через **outbox**.

`kafka/producer-is-idempotent` — `enable_idempotence=False` в проде. `kafka/producer-is-idempotent` — `acks=0`/`acks=1`. `kafka/partition-key-required` — send
без key для бизнес-событий. `kafka/publish-via-outbox` — `producer.send` из той же транзакции, что DB-операция (Kafka не XA;
rollback БД не откатит publish) — outbox.

```python
producer = AIOKafkaProducer(
    bootstrap_servers=settings.kafka.brokers,
    enable_idempotence=True,                  # R-KFK-PROD-1: тянет acks=all, retries, max_in_flight≤5
    value_serializer=lambda v: json.dumps(v).encode(),
)
await producer.start()
# бизнес-событие: key = aggregate id (R-KFK-PROD-2). Из handler — НЕ прямой send, а через outbox (R-KFK-PROD-4).
await producer.send_and_wait("orders.confirmed", key=str(order.id).encode(), value=payload)
```

## 2. Consumer (`R-KFK-CONS-*`)

`kafka/consumer-group-per-purpose` — уникальный `group_id="<service>-<purpose>"` per-роль. `kafka/manual-offset-commit` — **manual commit**:
`AIOKafkaConsumer(enable_auto_commit=False)`, `await consumer.commit()` **после** успешной обработки. `kafka/consumer-is-idempotent` —
listener идемпотентен (`R-KFK-IDEM-*`). `kafka/earliest-offset-for-critical-consumers` — `auto_offset_reset="earliest"` для critical-consumer'ов.
`kafka/concurrency-and-poll-interval` — concurrency через несколько consumer-тасок ≤ числу партиций. `kafka/concurrency-and-poll-interval` — `max_poll_interval_ms`
≥ времени обработки.

```python
consumer = AIOKafkaConsumer(
    "orders.confirmed", bootstrap_servers=settings.brokers,
    group_id="billing-order-confirmed", enable_auto_commit=False,
    auto_offset_reset="earliest", value_deserializer=lambda b: json.loads(b))
async for msg in consumer:
    event = OrderConfirmed(**msg.value)
    await handler.handle(event)          # идемпотентен по event_id (R-KFK-IDEM)
    await consumer.commit()
```

`kafka/manual-offset-commit` — `enable_auto_commit=True` в проде. `kafka/listener-does-not-block-poll-loop` — `asyncio.sleep`/блокирующая операция >1s в
цикле обработки (держит poll → rebalance). `kafka/consumer-group-per-purpose` — нет `group_id`/общий на разные listener'ы. `kafka/listener-does-not-block-poll-loop` —
HTTP к внешней системе из listener без CB/bulkhead (`resilience/outbound-calls-fully-protected`).

## 3. Outbox publishing (`R-KFK-OBX-*`)

`kafka/publish-via-outbox` — domain-события пишутся в `outbox`-таблицу в той же транзакции (UoW), не `producer.send` из handler.
`kafka/outbox-relay-reads-in-batches` — **outbox-relay** — отдельная asyncio-задача/scheduler (APScheduler/arq) читает unpublished
`SELECT ... FOR UPDATE SKIP LOCKED` (`pg-runtime/skip-locked-for-queues`), публикует через aiokafka, проставляет `published_at`.
`kafka/outbox-relay-reads-in-batches` — topic из `event_type`/`aggregate_type`. `kafka/outbox-relay-reads-in-batches` — relay обрабатывает batch (10–50), не по одному.

`kafka/publish-via-outbox` — `producer.send` из транзакции с DB-операцией. `kafka/publish-via-outbox` — публикация после commit без outbox
(падение между commit и publish теряет событие). `kafka/outbox-table-shape` — outbox без `published_at`/partial-индекса
`WHERE published_at IS NULL` (full scan).

```python
# В handler — запись в outbox в той же UoW-транзакции, что и доменное изменение (R-KFK-OBX-1):
session.add(OutboxEventModel(
    aggregate_id=order.id, topic="orders.confirmed",
    payload=OrderConfirmedSchema.model_validate(event).model_dump(mode="json"),
))

# Доступ к outbox-таблице — только через репозиторий (select/update в persistence, не в relay):
class OutboxRepository:
    async def claim_unpublished(self, session: AsyncSession, *, limit: int) -> list[OutboxRecord]:
        rows = (await session.execute(
            select(OutboxEventModel)
            .where(OutboxEventModel.published_at.is_(None))
            .order_by(OutboxEventModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True))                # R-KFK-OBX-2, cross-ref PG-L-021
        ).scalars().all()
        return [to_outbox_record(r) for r in rows]             # домен/DTO наружу, не ORM (R-SQLA-REPO-2)

    async def mark_published(self, session: AsyncSession, event_ids: list[UUID], *, at: datetime) -> None:
        await session.execute(
            update(OutboxEventModel)
            .where(OutboxEventModel.event_id.in_(event_ids))
            .values(published_at=at))                          # partial-индекс WHERE published_at IS NULL

# Relay лишь оркестрирует: репозиторий читает/помечает, relay публикует и держит границу TX (R-SQLA-SESS-1):
class OutboxRelay:
    def __init__(self, session_factory, outbox_repo: OutboxRepository, producer: AIOKafkaProducer) -> None:
        self._session_factory = session_factory
        self._outbox_repo = outbox_repo
        self._producer = producer

    async def run_once(self, batch: int = 50) -> None:
        async with self._session_factory() as session, session.begin():
            records = await self._outbox_repo.claim_unpublished(session, limit=batch)
            published: list[UUID] = []
            for rec in records:
                await self._producer.send_and_wait(
                    rec.topic, key=str(rec.aggregate_id).encode(), value=rec.payload)
                published.append(rec.event_id)
            if published:
                await self._outbox_repo.mark_published(
                    session, published, at=datetime.now(timezone.utc))
```

## 4. Idempotent consumer (`R-KFK-IDEM-*`)

`kafka/consumer-is-idempotent` — у события уникальный `event_id` (UUID v7) в payload/header; consumer проверяет, обрабатывалось ли.
`kafka/processed-record-in-same-transaction` — таблица `processed_event` с PK на `event_id` (UNIQUE дедуп под race); TTL через partition-drop/
background-job. `kafka/processed-record-in-same-transaction` — запись в `processed_event` и бизнес-результат — в **одной транзакции** (UoW).
`kafka/money-operations-double-protected` — для money — двойная защита: `event_id` + `Idempotency-Key` на downstream HTTP (`auth-patterns/money-commands-need-idempotency-key`).

`kafka/consumer-is-idempotent` — listener без проверки `event_id` там, где дубль критичен. `kafka/consumer-is-idempotent` — Kafka offset как
dedup-ключ (зависит от group; новый group → всё «впервые»).

```python
# ORM-модель + доступ к ней — в persistence (репозиторий), не в listener:
class ProcessedEventModel(Base):                  # R-KFK-IDEM-2: PK на event_id = UNIQUE дедуп под race
    __tablename__ = "processed_event"
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    consumer_group: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ProcessedEventRepository:
    async def exists(self, session: AsyncSession, event_id: UUID) -> bool:
        return await session.get(ProcessedEventModel, event_id) is not None

    async def mark(self, session: AsyncSession, event_id: UUID, *, consumer_group: str) -> None:
        session.add(ProcessedEventModel(event_id=event_id, consumer_group=consumer_group))

# Listener/handler оркестрирует и держит границу TX; обращения к БД — через репозиторий (R-KFK-IDEM-3):
async def handle(event: OrderConfirmed, session_factory, processed_repo: ProcessedEventRepository) -> None:
    async with session_factory() as session, session.begin():          # одна транзакция
        if await processed_repo.exists(session, event.event_id):
            return                                                     # дубль → skip
        await apply_business_change(session, event)                    # доменное изменение — тоже через репозитории
        await processed_repo.mark(session, event.event_id, consumer_group="billing-order-confirmed")
```

## 5. Retry topic + DLQ (`R-KFK-RTRY-*`)

`kafka/retry-topics-with-limits` — retry-топики с возрастающим delay (`orders.confirmed.retry.5s/30s/...`), не блокирующий повтор в
listener. `kafka/retry-only-transient-failures` — retry только для transient (timeout/5xx/брокер), не для контрактных/poison. `kafka/dlq-monitored-and-manually-replayed` —
alert на размер DLQ за час. `kafka/dlq-monitored-and-manually-replayed` — replay из DLQ — ручная админ-операция.

`kafka/retry-topics-with-limits` — blocking retry через `asyncio.sleep`/повтор в listener (держит poll). `kafka/no-swallowing-in-listener` — проглатывание
исключения + commit (событие потеряно). `kafka/retry-topics-with-limits` — retry-топик без max-attempts (бесконечный lock-step).
`kafka/dlq-monitored-and-manually-replayed` — DLQ без monitoring.

```python
async for msg in consumer:
    try:
        await handler.handle(deserialize(msg))
        await consumer.commit()                                # только после успеха
    except RetryableError:                                     # transient: timeout/5xx/брокер (R-KFK-RTRY-2)
        await retry_producer.send_and_wait(
            "orders.confirmed.retry.30s", key=msg.key, value=msg.value)
        await consumer.commit()                                # non-blocking: не держим poll (R-KFK-RTRY-X1)
    except NonRetryableError:                                  # poison/контракт → DLQ, не зацикливаемся
        await dlq_producer.send_and_wait(
            "orders.confirmed.dlq", key=msg.key, value=msg.value)
        await consumer.commit()
```

## 6. Event design (`R-KFK-EVT-*`)

`kafka/event-named-in-past-tense` — имя в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderConfirmation`). `kafka/event-payload-hygiene` —
payload: `event_id`, `occurred_at`, `aggregate_id`, версия, бизнес-значения. `kafka/event-schema-forward-compatible` — forward-compatible:
добавление полей non-breaking; удаление/переименование → `event_type.v2`. `kafka/event-payload-hygiene` — событие как
`@dataclass(frozen=True)` (наследует `DomainEvent`, cross-ref `ddd-tactical/event-is-immutable-record`, `ucp-py-ddd-tactical-*`); для (де)сериализации
по схеме — Pydantic-модель на границе consumer.

`kafka/event-named-in-past-tense` — имя-команда (`ConfirmOrder`). `kafka/event-payload-hygiene` — агрегат/Entity целиком в payload (нестабильные поля,
ломает forward-compat). `kafka/event-payload-hygiene` — PII в широковещательных топиках (только `customer_id`, full PII — запросом).
`kafka/event-schema-forward-compatible` — breaking change без версии в `event_type`.

```python
@dataclass(frozen=True)                       # R-KFK-EVT-4: доменное событие в core/ (cross-ref R-EVT-1)
class OrderConfirmed(DomainEvent):
    event_id: UUID
    occurred_at: datetime
    order_id: UUID                            # aggregate_id, не агрегат целиком (R-KFK-EVT-X2)
    total_amount: Decimal                     # бизнес-поля; без PII (R-KFK-EVT-X3)

class OrderConfirmedSchema(BaseModel):        # Pydantic на границе consumer — (де)сериализация по схеме
    event_id: UUID
    occurred_at: datetime
    order_id: UUID
    total_amount: Decimal
```

## 7. Конфигурация (`R-KFK-CFG-*`)

`kafka/settings-are-typed-and-external` — параметры через `pydantic-settings` (`KafkaSettings`, валидируется). `kafka/deserialization-allow-list` — десериализация
событий — через **явный реестр `event_type → Pydantic-модель`** (allow-list), не «распарсить любой класс по имени из
payload». `kafka/missing-topics-are-fatal` — старт падает, если ожидаемый топик отсутствует (проверка на старте).

`kafka/deserialization-allow-list` — динамический импорт класса по строке из payload (`importlib` по `event_type`) — RCE-риск (аналог
`trusted.packages: '*'`); только статический реестр. `kafka/settings-are-typed-and-external` — `bootstrap_servers` хардкодом без env.

```python
class KafkaSettings(BaseSettings):                       # R-KFK-CFG-1: валидируемый конфиг
    brokers: str                                         # R-KFK-CFG-X2: из env, не хардкод
    security_protocol: str = "SSL"                       # R-KFK-SEC-1: TLS в проде
    model_config = SettingsConfigDict(env_prefix="KAFKA_")

# R-KFK-CFG-3: статический allow-list event_type → модель; НЕ importlib по строке из payload (R-KFK-CFG-X1)
EVENT_REGISTRY: dict[str, type[BaseModel]] = {
    "order.confirmed.v1": OrderConfirmedSchema,
}

def deserialize(msg) -> BaseModel:
    schema = EVENT_REGISTRY[msg.headers["event_type"]]   # KeyError на неизвестный тип — fail-fast
    return schema.model_validate_json(msg.value)
```

## 8. Observability (`R-KFK-OBS-*`)

`kafka/consumer-lag-alerting` — метрики producer/consumer через `prometheus-client` (lag, throughput, errors). `kafka/consumer-lag-alerting` —
**alert на consumer lag** для критичных топиков. `kafka/trace-context-in-headers` — tracing: producer кладёт `traceparent` в Kafka
headers, consumer извлекает и продолжает trace (OTel instrumentation для aiokafka). `kafka/dlq-monitored-and-manually-replayed` — DLQ-size alert.

`kafka/consumer-lag-alerting` — отсутствие consumer-lag alert.

## 9. Security (`R-KFK-SEC-*`)

`kafka/transport-security-and-acls` — в проде TLS (`security_protocol="SSL"`/`SASL_SSL`), не plaintext. `kafka/transport-security-and-acls` — ACL на топики
per-сервис (clientId в `KafkaSettings`). `kafka/event-payload-hygiene` — PII — отдельные restricted-топики либо «слабая ссылка»
(`customer_id` + запрос PII у Customer-сервиса).

`kafka/transport-security-and-acls` — `PLAINTEXT` в проде. `kafka/transport-security-and-acls` — один service-account на весь кластер.

## 10. Чеклист подключения к новому сервису (Python)

1. Producer идемпотентный, partition key = aggregate id, JSON; domain-события через outbox, не прямой send.
2. Consumer: уникальный `group_id`, manual commit после обработки, идемпотентен по `event_id`, `earliest`.
3. Outbox-relay: `FOR UPDATE SKIP LOCKED`, batch, partial-индекс; нет send из транзакции с DB.
4. `processed_event` PK на `event_id`, запись в одной TX с бизнес-результатом.
5. Retry-топики + DLQ + monitoring; нет blocking-retry/проглатывания.
6. Событие — прошедшее время, без агрегата/PII; версия в `event_type`; десериализация через статический реестр.
7. TLS + per-service ACL; lag/DLQ alerts; traceparent в headers.
