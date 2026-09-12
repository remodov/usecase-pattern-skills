---
name: ucp-py-kafka-review
lang: python
description: Ревью работы с Kafka в FastAPI-сервисе на aiokafka по UCP (требования kafka/*) — producer idempotence/acks/key, consumer manual commit и идемпотентность, outbox-relay, retry-топики + DLQ, дизайн событий, конфиг и безопасность.
when_to_use: Ревью producer/consumer-кода на aiokafka, KafkaSettings, outbox-relay, processed_event, event-классов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka (Python / aiokafka)

Ты ревьюишь работу с Kafka на соответствие **контракту** `backend/kafka/spec.md` (`R-KFK-*`) и **Python-реализации** `backend/kafka/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/kafka/spec.md`** + **`backend/kafka/references/python/implementation.md`**.
- Парные: `backend/ddd-tactical/python/...` (событие), `cqrs` (outbox sync), `pg-runtime` (`FOR UPDATE SKIP LOCKED`), `resilience` (CB в consumer).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`kafka/manual-offset-commit`, `kafka/publish-via-outbox`), не префикс.

2. **Скоп.** Producer/consumer-код (`aiokafka`), `KafkaSettings`, outbox-relay, `processed_event`, event-классы; `git diff`.

3. **Прогон.**
   - **Producer (`R-KFK-PROD-*`):** `enable_idempotence=True` (False→`kafka/producer-is-idempotent`); `acks="all"` (0/1→`kafka/producer-is-idempotent`); key=aggregate id (нет→`kafka/partition-key-required`); domain-события через outbox, не прямой send из handler (`kafka/publish-via-outbox`).
   - **Consumer (`R-KFK-CONS-*`):** `group_id` per-purpose (нет/общий→`kafka/consumer-group-per-purpose`); `enable_auto_commit=False`+commit после обработки (True→`kafka/manual-offset-commit`); `earliest`; нет `asyncio.sleep`>1s в цикле (`kafka/listener-does-not-block-poll-loop`); HTTP из listener с CB (без→`kafka/listener-does-not-block-poll-loop`).
   - **Outbox (`R-KFK-OBX-*`):** `send` из транзакции с DB → `kafka/publish-via-outbox`; публикация после commit без outbox → `kafka/publish-via-outbox`; нет `published_at`/partial-индекса → `kafka/outbox-table-shape`; relay через `FOR UPDATE SKIP LOCKED`, batch.
   - **Idempotent (`R-KFK-IDEM-*`):** `processed_event` PK на `event_id`, dedup+результат в одной TX. Нет проверки `event_id` → `kafka/consumer-is-idempotent`. Offset как dedup → `kafka/consumer-is-idempotent`.
   - **Retry/DLQ (`R-KFK-RTRY-*`):** retry-топики (не blocking `asyncio.sleep`→`kafka/retry-topics-with-limits`); проглатывание+commit→`kafka/no-swallowing-in-listener`; max-attempts (`kafka/retry-topics-with-limits`); DLQ monitoring (`kafka/dlq-monitored-and-manually-replayed`).
   - **Event (`R-KFK-EVT-*`):** прошедшее время (команда→`kafka/event-named-in-past-tense`); без агрегата (`kafka/event-payload-hygiene`)/PII (`kafka/event-payload-hygiene`); версия в `event_type` (`kafka/event-schema-forward-compatible`).
   - **Config (`R-KFK-CFG-*`):** десериализация через статический реестр; динамический импорт по `event_type` → `kafka/deserialization-allow-list` (RCE-риск); brokers через env (`kafka/settings-are-typed-and-external`).
   - **Security/Obs (`R-KFK-SEC/OBS-*`):** TLS в проде (plaintext→`kafka/transport-security-and-acls`); per-service ACL (`kafka/transport-security-and-acls`); consumer-lag alerts (нет→`kafka/consumer-lag-alerting`); traceparent в headers.

4. **Cross-check:** событие как frozen dataclass — `ucp-py-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` — `ucp-pg-runtime-review`; CB для HTTP из consumer — `ucp-py-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `send` из транзакции с DB/без outbox (`kafka/publish-via-outbox`/`kafka/publish-via-outbox`), `enable_auto_commit=True` (`kafka/manual-offset-commit`), нет dedup по `event_id` (`kafka/consumer-is-idempotent`), проглатывание исключения+commit (`kafka/no-swallowing-in-listener`), динамический импорт по `event_type` (`kafka/deserialization-allow-list`), plaintext в проде (`kafka/transport-security-and-acls`).
   - **Предупреждение** — `enable_idempotence=False`/`acks=1` (`R-KFK-PROD-X1/X2`), send без key (`kafka/partition-key-required`), blocking-retry (`kafka/retry-topics-with-limits`), PII/агрегат в payload (`R-KFK-EVT-X2/X3`), нет lag-alerts (`kafka/consumer-lag-alerting`).
   - **Замечание** — имя-команда события (`kafka/event-named-in-past-tense`), нет версии в `event_type` (`kafka/event-schema-forward-compatible`), общий service-account (`kafka/transport-security-and-acls`).

## Что не входит

- Событие как frozen dataclass — `ucp-py-ddd-tactical-review`. Outbox-таблица/locks — `ucp-pg-runtime-review`.
- CB для HTTP из consumer — `ucp-py-resilience-review`. CQRS read-model sync — `ucp-py-cqrs-review`.

$ARGUMENTS
