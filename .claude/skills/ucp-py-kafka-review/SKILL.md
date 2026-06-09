---
name: ucp-py-kafka-review
lang: python
description: Ревью работы с Kafka в FastAPI-сервисе на aiokafka по UCP (коды R-KFK-*) — producer idempotence/acks/key, consumer manual commit и идемпотентность, outbox-relay, retry-топики + DLQ, дизайн событий, конфиг и безопасность.
when_to_use: Ревью producer/consumer-кода на aiokafka, KafkaSettings, outbox-relay, processed_event, event-классов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka (Python / aiokafka)

Ты ревьюишь работу с Kafka на соответствие **контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`) и **Python-реализации** `backend/kafka/python/kafka-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/kafka/kafka-rules.md`** + **`backend/kafka/python/kafka-style-guide.md`**.
- Парные: `backend/ddd-tactical/python/...` (событие), `cqrs` (outbox sync), `pg-runtime` (`FOR UPDATE SKIP LOCKED`), `resilience` (CB в consumer).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-KFK-CONS-X1`, `R-KFK-OBX-X1`), не префикс.

2. **Скоп.** Producer/consumer-код (`aiokafka`), `KafkaSettings`, outbox-relay, `processed_event`, event-классы; `git diff`.

3. **Прогон.**
   - **Producer (`R-KFK-PROD-*`):** `enable_idempotence=True` (False→`R-KFK-PROD-X1`); `acks="all"` (0/1→`R-KFK-PROD-X2`); key=aggregate id (нет→`R-KFK-PROD-X3`); domain-события через outbox, не прямой send из handler (`R-KFK-PROD-X4`).
   - **Consumer (`R-KFK-CONS-*`):** `group_id` per-purpose (нет/общий→`R-KFK-CONS-X3`); `enable_auto_commit=False`+commit после обработки (True→`R-KFK-CONS-X1`); `earliest`; нет `asyncio.sleep`>1s в цикле (`R-KFK-CONS-X2`); HTTP из listener с CB (без→`R-KFK-CONS-X4`).
   - **Outbox (`R-KFK-OBX-*`):** `send` из транзакции с DB → `R-KFK-OBX-X1`; публикация после commit без outbox → `R-KFK-OBX-X2`; нет `published_at`/partial-индекса → `R-KFK-OBX-X3`; relay через `FOR UPDATE SKIP LOCKED`, batch.
   - **Idempotent (`R-KFK-IDEM-*`):** `processed_event` PK на `event_id`, dedup+результат в одной TX. Нет проверки `event_id` → `R-KFK-IDEM-X1`. Offset как dedup → `R-KFK-IDEM-X2`.
   - **Retry/DLQ (`R-KFK-RTRY-*`):** retry-топики (не blocking `asyncio.sleep`→`R-KFK-RTRY-X1`); проглатывание+commit→`R-KFK-RTRY-X2`; max-attempts (`R-KFK-RTRY-X3`); DLQ monitoring (`R-KFK-RTRY-X4`).
   - **Event (`R-KFK-EVT-*`):** прошедшее время (команда→`R-KFK-EVT-X1`); без агрегата (`R-KFK-EVT-X2`)/PII (`R-KFK-EVT-X3`); версия в `event_type` (`R-KFK-EVT-X4`).
   - **Config (`R-KFK-CFG-*`):** десериализация через статический реестр; динамический импорт по `event_type` → `R-KFK-CFG-X1` (RCE-риск); brokers через env (`R-KFK-CFG-X2`).
   - **Security/Obs (`R-KFK-SEC/OBS-*`):** TLS в проде (plaintext→`R-KFK-SEC-X1`); per-service ACL (`R-KFK-SEC-X2`); consumer-lag alerts (нет→`R-KFK-OBS-X1`); traceparent в headers.

4. **Cross-check:** событие как frozen dataclass — `ucp-py-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` — `ucp-pg-runtime-review`; CB для HTTP из consumer — `ucp-py-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `send` из транзакции с DB/без outbox (`R-KFK-OBX-X1`/`R-KFK-PROD-X4`), `enable_auto_commit=True` (`R-KFK-CONS-X1`), нет dedup по `event_id` (`R-KFK-IDEM-X1`), проглатывание исключения+commit (`R-KFK-RTRY-X2`), динамический импорт по `event_type` (`R-KFK-CFG-X1`), plaintext в проде (`R-KFK-SEC-X1`).
   - **Предупреждение** — `enable_idempotence=False`/`acks=1` (`R-KFK-PROD-X1/X2`), send без key (`R-KFK-PROD-X3`), blocking-retry (`R-KFK-RTRY-X1`), PII/агрегат в payload (`R-KFK-EVT-X2/X3`), нет lag-alerts (`R-KFK-OBS-X1`).
   - **Замечание** — имя-команда события (`R-KFK-EVT-X1`), нет версии в `event_type` (`R-KFK-EVT-X4`), общий service-account (`R-KFK-SEC-X2`).

## Что не входит

- Событие как frozen dataclass — `ucp-py-ddd-tactical-review`. Outbox-таблица/locks — `ucp-pg-runtime-review`.
- CB для HTTP из consumer — `ucp-py-resilience-review`. CQRS read-model sync — `ucp-py-cqrs-review`.

$ARGUMENTS
