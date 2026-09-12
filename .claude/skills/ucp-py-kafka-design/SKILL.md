---
name: ucp-py-kafka-design
lang: python
description: Спроектировать работу с Kafka на Python/aiokafka по UCP — идемпотентный producer с partition key, outbox-relay через FOR UPDATE SKIP LOCKED, consumer с manual commit и processed_event, retry-топики + DLQ, событие как frozen dataclass.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на питоне». При добавлении producer/consumer/outbox.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Kafka — проектирование (Python / aiokafka)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/spec.md` (`R-KFK-*`) и **Python-реализации** `backend/kafka/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `backend/ddd-tactical/python/...` (событие как frozen dataclass), `cqrs` (sync read-model через outbox), `pg-runtime` (outbox-relay `FOR UPDATE SKIP LOCKED`), `resilience` (CB для HTTP из consumer).

2. **Producer** (`R-KFK-PROD-*`): `AIOKafkaProducer(enable_idempotence=True)`, `key`=aggregate id, JSON; domain-события — **через outbox**, не прямой `send` из handler (`kafka/publish-via-outbox`).

3. **Outbox-relay** (`R-KFK-OBX-*`): запись в `outbox` в той же UoW-транзакции; отдельная asyncio-задача/scheduler читает unpublished `FOR UPDATE SKIP LOCKED`, batch 10–50, публикует, ставит `published_at`; partial-индекс `WHERE published_at IS NULL`.

4. **Consumer** (`R-KFK-CONS-*`): уникальный `group_id="<service>-<purpose>"`, `enable_auto_commit=False` + commit после обработки, `auto_offset_reset="earliest"`, идемпотентен.

5. **Idempotent consumer** (`R-KFK-IDEM-*`): `event_id` (UUID v7); таблица `processed_event` (PK на `event_id`); запись dedup + бизнес-результат в одной TX; для money — `event_id` + `Idempotency-Key`.

6. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay (не blocking-retry), max-attempts, DLQ + alert.

7. **Event design** (`R-KFK-EVT-*`): `@dataclass(frozen=True)`, прошедшее время, `event_id`/`occurred_at`/`aggregate_id`/версия, без агрегата/PII; десериализация через статический реестр `event_type→Pydantic-модель`.

8. **Config/Security** (`R-KFK-CFG/SEC-*`): `pydantic-settings`, env для brokers, TLS, per-service ACL. **Observability**: lag/DLQ alerts, `traceparent` в headers.

9. **Самопроверка** (§10) + предложи `ucp-py-kafka-review`. Outbox-таблица DDL — `ucp-pg-schema-design`.

## Антипаттерны, которые НЕ генерировать

- `enable_idempotence=False`/`acks=0|1` (`R-KFK-PROD-X1/X2`); send без key (`kafka/partition-key-required`); `producer.send` из транзакции с DB (`kafka/publish-via-outbox`/`kafka/publish-via-outbox`).
- `enable_auto_commit=True` (`kafka/manual-offset-commit`); `asyncio.sleep`>1s в цикле обработки (`kafka/listener-does-not-block-poll-loop`); HTTP из listener без CB (`kafka/listener-does-not-block-poll-loop`).
- Listener без dedup по `event_id` (`kafka/consumer-is-idempotent`); offset как dedup-ключ (`kafka/consumer-is-idempotent`); проглатывание исключения + commit (`kafka/no-swallowing-in-listener`).
- Имя-команда у события (`kafka/event-named-in-past-tense`); агрегат/PII в payload (`R-KFK-EVT-X2/X3`); breaking без версии (`kafka/event-schema-forward-compatible`); динамический импорт класса по `event_type` (`kafka/deserialization-allow-list`); plaintext в проде (`kafka/transport-security-and-acls`).

После работы скилла — обязательно `ucp-py-kafka-review`.

$ARGUMENTS
