---
name: ucp-py-kafka-design
lang: python
description: Спроектировать работу с Kafka на Python/aiokafka по UCP (коды R-KFK-*) — идемпотентный producer с partition key, outbox-relay через FOR UPDATE SKIP LOCKED, consumer с manual commit и processed_event, retry-топики + DLQ, событие как frozen dataclass.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на питоне». При добавлении producer/consumer/outbox.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Kafka — проектирование (Python / aiokafka)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`) и **Python-реализации** `backend/kafka/python/kafka-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/ddd-tactical/python/...` (событие как frozen dataclass), `cqrs` (sync read-model через outbox), `pg-runtime` (outbox-relay `FOR UPDATE SKIP LOCKED`), `resilience` (CB для HTTP из consumer).

2. **Producer** (`R-KFK-PROD-*`): `AIOKafkaProducer(enable_idempotence=True)`, `key`=aggregate id, JSON; domain-события — **через outbox**, не прямой `send` из handler (`R-KFK-PROD-X4`).

3. **Outbox-relay** (`R-KFK-OBX-*`): запись в `outbox` в той же UoW-транзакции; отдельная asyncio-задача/scheduler читает unpublished `FOR UPDATE SKIP LOCKED`, batch 10–50, публикует, ставит `published_at`; partial-индекс `WHERE published_at IS NULL`.

4. **Consumer** (`R-KFK-CONS-*`): уникальный `group_id="<service>-<purpose>"`, `enable_auto_commit=False` + commit после обработки, `auto_offset_reset="earliest"`, идемпотентен.

5. **Idempotent consumer** (`R-KFK-IDEM-*`): `event_id` (UUID v7); таблица `processed_event` (PK на `event_id`); запись dedup + бизнес-результат в одной TX; для money — `event_id` + `Idempotency-Key`.

6. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay (не blocking-retry), max-attempts, DLQ + alert.

7. **Event design** (`R-KFK-EVT-*`): `@dataclass(frozen=True)`, прошедшее время, `event_id`/`occurred_at`/`aggregate_id`/версия, без агрегата/PII; десериализация через статический реестр `event_type→Pydantic-модель`.

8. **Config/Security** (`R-KFK-CFG/SEC-*`): `pydantic-settings`, env для brokers, TLS, per-service ACL. **Observability**: lag/DLQ alerts, `traceparent` в headers.

9. **Самопроверка** (§10) + предложи `ucp-py-kafka-review`. Outbox-таблица DDL — `ucp-pg-schema-design`.

## Антипаттерны, которые НЕ генерировать

- `enable_idempotence=False`/`acks=0|1` (`R-KFK-PROD-X1/X2`); send без key (`R-KFK-PROD-X3`); `producer.send` из транзакции с DB (`R-KFK-PROD-X4`/`R-KFK-OBX-X1`).
- `enable_auto_commit=True` (`R-KFK-CONS-X1`); `asyncio.sleep`>1s в цикле обработки (`R-KFK-CONS-X2`); HTTP из listener без CB (`R-KFK-CONS-X4`).
- Listener без dedup по `event_id` (`R-KFK-IDEM-X1`); offset как dedup-ключ (`R-KFK-IDEM-X2`); проглатывание исключения + commit (`R-KFK-RTRY-X2`).
- Имя-команда у события (`R-KFK-EVT-X1`); агрегат/PII в payload (`R-KFK-EVT-X2/X3`); breaking без версии (`R-KFK-EVT-X4`); динамический импорт класса по `event_type` (`R-KFK-CFG-X1`); plaintext в проде (`R-KFK-SEC-X1`).

После работы скилла — обязательно `ucp-py-kafka-review`.

$ARGUMENTS
