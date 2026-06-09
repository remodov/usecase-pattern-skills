# Kafka — Python Style Guide (aiokafka)

Реализация язык-нейтрального контракта `../kafka-rules.md` (`R-KFK-*`) на Python с **aiokafka** (async-native;
`confluent-kafka` — альтернатива для высокой пропускной). Коды общие с Java; меняется клиент, семантика одна.

## 1. Producer (`R-KFK-PROD-*`)

`R-KFK-PROD-1` — идемпотентный producer: `AIOKafkaProducer(enable_idempotence=True)` (тянет `acks="all"`,
бесконечные retries, `max_in_flight ≤ 5`). `R-KFK-PROD-2` — `key=` обязателен для бизнес-событий = **aggregate id**
(`key=str(order.id).encode()`) — ordering per-aggregate. `R-KFK-PROD-3` — JSON-сериализация
(`value_serializer=lambda v: json.dumps(v).encode()`); Avro/Protobuf + Schema Registry — для bandwidth-топиков.
`R-KFK-PROD-4` — domain-события **не** через прямой `producer.send_and_wait(...)` из handler — через **outbox**.

`R-KFK-PROD-X1` — `enable_idempotence=False` в проде. `R-KFK-PROD-X2` — `acks=0`/`acks=1`. `R-KFK-PROD-X3` — send
без key для бизнес-событий. `R-KFK-PROD-X4` — `producer.send` из той же транзакции, что DB-операция (Kafka не XA;
rollback БД не откатит publish) — outbox.

## 2. Consumer (`R-KFK-CONS-*`)

`R-KFK-CONS-1` — уникальный `group_id="<service>-<purpose>"` per-роль. `R-KFK-CONS-2` — **manual commit**:
`AIOKafkaConsumer(enable_auto_commit=False)`, `await consumer.commit()` **после** успешной обработки. `R-KFK-CONS-3` —
listener идемпотентен (`R-KFK-IDEM-*`). `R-KFK-CONS-4` — `auto_offset_reset="earliest"` для critical-consumer'ов.
`R-KFK-CONS-5` — concurrency через несколько consumer-тасок ≤ числу партиций. `R-KFK-CONS-6` — `max_poll_interval_ms`
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

`R-KFK-CONS-X1` — `enable_auto_commit=True` в проде. `R-KFK-CONS-X2` — `asyncio.sleep`/блокирующая операция >1s в
цикле обработки (держит poll → rebalance). `R-KFK-CONS-X3` — нет `group_id`/общий на разные listener'ы. `R-KFK-CONS-X4` —
HTTP к внешней системе из listener без CB/bulkhead (`R-RES-WHERE-1`).

## 3. Outbox publishing (`R-KFK-OBX-*`)

`R-KFK-OBX-1` — domain-события пишутся в `outbox`-таблицу в той же транзакции (UoW), не `producer.send` из handler.
`R-KFK-OBX-2` — **outbox-relay** — отдельная asyncio-задача/scheduler (APScheduler/arq) читает unpublished
`SELECT ... FOR UPDATE SKIP LOCKED` (`PG-L-021`), публикует через aiokafka, проставляет `published_at`.
`R-KFK-OBX-3` — topic из `event_type`/`aggregate_type`. `R-KFK-OBX-4` — relay обрабатывает batch (10–50), не по одному.

`R-KFK-OBX-X1` — `producer.send` из транзакции с DB-операцией. `R-KFK-OBX-X2` — публикация после commit без outbox
(падение между commit и publish теряет событие). `R-KFK-OBX-X3` — outbox без `published_at`/partial-индекса
`WHERE published_at IS NULL` (full scan).

## 4. Idempotent consumer (`R-KFK-IDEM-*`)

`R-KFK-IDEM-1` — у события уникальный `event_id` (UUID v7) в payload/header; consumer проверяет, обрабатывалось ли.
`R-KFK-IDEM-2` — таблица `processed_event` с PK на `event_id` (UNIQUE дедуп под race); TTL через partition-drop/
background-job. `R-KFK-IDEM-3` — запись в `processed_event` и бизнес-результат — в **одной транзакции** (UoW).
`R-KFK-IDEM-4` — для money — двойная защита: `event_id` + `Idempotency-Key` на downstream HTTP (`AUTH-19`).

`R-KFK-IDEM-X1` — listener без проверки `event_id` там, где дубль критичен. `R-KFK-IDEM-X2` — Kafka offset как
dedup-ключ (зависит от group; новый group → всё «впервые»).

## 5. Retry topic + DLQ (`R-KFK-RTRY-*`)

`R-KFK-RTRY-1` — retry-топики с возрастающим delay (`orders.confirmed.retry.5s/30s/...`), не блокирующий повтор в
listener. `R-KFK-RTRY-2` — retry только для transient (timeout/5xx/брокер), не для контрактных/poison. `R-KFK-RTRY-3` —
alert на размер DLQ за час. `R-KFK-RTRY-4` — replay из DLQ — ручная админ-операция.

`R-KFK-RTRY-X1` — blocking retry через `asyncio.sleep`/повтор в listener (держит poll). `R-KFK-RTRY-X2` — проглатывание
исключения + commit (событие потеряно). `R-KFK-RTRY-X3` — retry-топик без max-attempts (бесконечный lock-step).
`R-KFK-RTRY-X4` — DLQ без monitoring.

## 6. Event design (`R-KFK-EVT-*`)

`R-KFK-EVT-1` — имя в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderConfirmation`). `R-KFK-EVT-2` —
payload: `event_id`, `occurred_at`, `aggregate_id`, версия, бизнес-значения. `R-KFK-EVT-3` — forward-compatible:
добавление полей non-breaking; удаление/переименование → `event_type.v2`. `R-KFK-EVT-4` — событие как
`@dataclass(frozen=True)` (наследует `DomainEvent`, cross-ref `R-EVT-1`, `ucp-py-ddd-tactical-*`); для (де)сериализации
по схеме — Pydantic-модель на границе consumer.

`R-KFK-EVT-X1` — имя-команда (`ConfirmOrder`). `R-KFK-EVT-X2` — агрегат/Entity целиком в payload (нестабильные поля,
ломает forward-compat). `R-KFK-EVT-X3` — PII в широковещательных топиках (только `customer_id`, full PII — запросом).
`R-KFK-EVT-X4` — breaking change без версии в `event_type`.

## 7. Конфигурация (`R-KFK-CFG-*`)

`R-KFK-CFG-1` — параметры через `pydantic-settings` (`KafkaSettings`, валидируется). `R-KFK-CFG-3` — десериализация
событий — через **явный реестр `event_type → Pydantic-модель`** (allow-list), не «распарсить любой класс по имени из
payload». `R-KFK-CFG-4` — старт падает, если ожидаемый топик отсутствует (проверка на старте).

`R-KFK-CFG-X1` — динамический импорт класса по строке из payload (`importlib` по `event_type`) — RCE-риск (аналог
`trusted.packages: '*'`); только статический реестр. `R-KFK-CFG-X2` — `bootstrap_servers` хардкодом без env.

## 8. Observability (`R-KFK-OBS-*`)

`R-KFK-OBS-1` — метрики producer/consumer через `prometheus-client` (lag, throughput, errors). `R-KFK-OBS-2` —
**alert на consumer lag** для критичных топиков. `R-KFK-OBS-3` — tracing: producer кладёт `traceparent` в Kafka
headers, consumer извлекает и продолжает trace (OTel instrumentation для aiokafka). `R-KFK-OBS-4` — DLQ-size alert.

`R-KFK-OBS-X1` — отсутствие consumer-lag alert.

## 9. Security (`R-KFK-SEC-*`)

`R-KFK-SEC-1` — в проде TLS (`security_protocol="SSL"`/`SASL_SSL`), не plaintext. `R-KFK-SEC-2` — ACL на топики
per-сервис (clientId в `KafkaSettings`). `R-KFK-SEC-3` — PII — отдельные restricted-топики либо «слабая ссылка»
(`customer_id` + запрос PII у Customer-сервиса).

`R-KFK-SEC-X1` — `PLAINTEXT` в проде. `R-KFK-SEC-X2` — один service-account на весь кластер.

## 10. Чеклист подключения к новому сервису (Python)

1. Producer идемпотентный, partition key = aggregate id, JSON; domain-события через outbox, не прямой send.
2. Consumer: уникальный `group_id`, manual commit после обработки, идемпотентен по `event_id`, `earliest`.
3. Outbox-relay: `FOR UPDATE SKIP LOCKED`, batch, partial-индекс; нет send из транзакции с DB.
4. `processed_event` PK на `event_id`, запись в одной TX с бизнес-результатом.
5. Retry-топики + DLQ + monitoring; нет blocking-retry/проглатывания.
6. Событие — прошедшее время, без агрегата/PII; версия в `event_type`; десериализация через статический реестр.
7. TLS + per-service ACL; lag/DLQ alerts; traceparent в headers.
