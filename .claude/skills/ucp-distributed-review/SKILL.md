---
name: ucp-distributed-review
description: Ревью распределённых паттернов на Java/Spring (требования distributed-patterns/*) — saga и compensation, idempotency на receiver, eventual consistency, outbox/inbox, запрет 2PC/JTA/XA/ChainedTransactionManager.
when_to_use: Ревью cross-service flows, saga-классов, idempotency-таблиц, multi-datasource конфигов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью distributed patterns

Ты ревьюишь cross-service flows и распределённые паттерны на соответствие требованиям `distributed-patterns/*`. Главные точки контроля: saga (compensation + state в БД), idempotency на receiver, outbox publishing, отсутствие 2PC.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/spec.md`** — индекс всех правил (полный текст — `references/<lang>/implementation.md`). Подгруппы: `R-DIST-WHEN-*` (когда применять), `R-DIST-SAGA-*` (saga), `R-DIST-IDEM-*` (idempotency), `R-DIST-EC-*` (eventual consistency), `R-DIST-OBX-*` (outbox/inbox), `R-DIST-COMP-*` (compensation), `R-DIST-TX-*` (запрет 2PC).
- Парные: `backend/kafka/spec.md` (`R-KFK-OBX-*`/`R-KFK-IDEM-*`), `backend/cqrs/spec.md` (`R-CQRS-SYNC-*`), `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` Idempotency-Key), `backend/rest-api/spec.md` (`rest-api/idempotency-key-header` Idempotency-Key header).

## Инструкции

1. **Прочти** `.claude/docs/backend/distributed-patterns/spec.md`. Цитируй коды (`distributed/no-two-phase-commit`, `distributed/receiver-deduplicates`).

2. **Определи объект ревью.** Если пользователь назвал — бери. Иначе:
   - `git diff` на `*Saga*`, `*Orchestrator*`, `*ProcessedEvent*`, `*Idempotency*`, `*Compensation*`.
   - DDL `saga_*`, `processed_event`, `inbox_event`, `idempotency_record` таблиц.
   - `application.yml` с `JtaTransactionManager` или `ChainedTransactionManager` упоминаниями.
   - Cross-service handlers + outbox-publishers.

3. **Прогон по подгруппам:**
   - **`R-DIST-WHEN-*`** — паттерны нужны для cross-service; для one-service `@Transactional` достаточно; перед введением — проверять modular monolith альтернативу.
   - **`R-DIST-SAGA-*`** — orchestration для complex (4+ steps), choreography для simple (2-3); saga state в `saga_<name>` таблице; sagaId сквозной; saga отдельно от use case.
   - **`R-DIST-IDEM-*`** — каждое cross-service сообщение с уникальным ID; receiver хранит processed-events; для HTTP `(idempotency_key, response)` запись; money — двойная защита; TTL 24-72h.
   - **`R-DIST-EC-*`** — декларация в OpenAPI; RYW через sticky session / polling / sync wait; bounded staleness SLO; causal consistency через version.
   - **`R-DIST-OBX-*`** — outbox обязателен (см. R-KFK-OBX-*); inbox опционально; БД — single source of truth.
   - **`R-DIST-COMP-*`** — каждая command в саге имеет compensation; идемпотентна; semantic state-change не DELETE; audit trail.
   - **`R-DIST-TX-*`** — JTA/2PC/XA/ChainedTransactionManager **запрещены**; альтернативы: saga / outbox / modular monolith.

4. **Ищи паттерны-нарушения:**
   - `JtaTransactionManager` или `XADataSource` в Spring config — `distributed/no-two-phase-commit` / `distributed/no-two-phase-commit` критическое.
   - `ChainedTransactionManager` для multi-datasource — `distributed/no-two-phase-commit`.
   - Saga-orchestrator без compensation-методов (только happy path) — `distributed/every-step-has-compensation`/`distributed/every-step-has-compensation` критическое.
   - Saga state в `Map<UUID, SagaState>` (in-memory) без БД — `distributed/saga-state-is-persistent`.
   - Saga-orchestrator реализован как `@Service`, но логика смешана с handler — `distributed/saga-separate-from-use-cases`.
   - `@KafkaListener` для money / critical-event без проверки `eventId` через `processed_event` — `distributed/receiver-deduplicates` критическое.
   - HTTP money-endpoint без `Idempotency-Key` обработки (нет `idempotency_record` таблицы) — `distributed/receiver-deduplicates` + `auth-patterns/money-commands-need-idempotency-key`.
   - Producer с `enable.idempotence: false` — `distributed/money-double-protection`.
   - Client-side код генерирует `Idempotency-Key = UUID.randomUUID()` каждый retry — `distributed/idempotency-key-per-operation`.
   - Endpoint возвращает eventual-consistent данные без `description` в OpenAPI про задержку — `distributed/bounded-and-declared-staleness`.
   - 2PC для money-операций между сервисами — `distributed-patterns/no-two-phase-commit` критическое.
   - `kafkaTemplate.send(...)` в command-handler без outbox — `distributed/outbox-for-outgoing-events`.
   - `@TransactionalEventListener(phase = AFTER_COMMIT)` для Kafka send — `distributed/outbox-for-outgoing-events`.
   - `DELETE FROM payment WHERE id = ?` как compensation — `distributed/compensation-is-semantic-and-idempotent` критическое (теряется audit + создаются «висящие» refund'ы).
   - Compensation бросает exception без отправки в DLQ + alert — `distributed/failed-compensation-goes-to-review` (висящие деньги).

5. **При ревью DDL `saga_*`:**
   - Поля: `saga_id PK`, `status` (IN_PROGRESS/COMPLETED/FAILED/COMPENSATING), `current_step`, `payload JSONB`, `started_at`, `completed_at`, `last_error`.
   - Индекс по `status` (для recovery in-flight sagas).

6. **При ревью DDL `processed_event` / `idempotency_record`:**
   - PRIMARY KEY на natural-key (`event_id` / `idempotency_key`) — UNIQUE constraint предотвращает дубли под race conditions.
   - TTL strategy (background-cleanup или partition+drop_old).

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md`.

8. **Доменные ориентиры серьёзности**:
   - **Критично:**
     - JTA/2PC/XA в коде — несовместимо со стеком, single point of failure.
     - Receiver money-events без dedup — двойные платежи.
     - Saga без compensation — «полусделанные» транзакции.
     - DELETE как compensation для финансовых таблиц — потеря audit + «висящие» refund'ы.
     - `kafkaTemplate.send` в `@Transactional` с DB — потеря consistency.
   - **Предупреждение:**
     - In-memory saga state — не переживает рестарт.
     - Idempotency-Key каждый раз новый — дедупликация бессмысленна.
     - Eventual consistency без декларации.
     - ChainedTransactionManager.
   - **Замечание:**
     - Choreography saga в complex flow (4+ шагов) — стоит orchestration.
     - Отсутствие SLO на bounded staleness.

## Что не входит

- Outbox-relay implementation — `ucp-pg-runtime-review` (`outbox` сценарий) / `ucp-kafka-review`.
- Idempotent consumer на Kafka — `ucp-kafka-review` (`R-KFK-IDEM-*`).
- CQRS read-model sync — `ucp-cqrs-review` (`R-CQRS-SYNC-*`).
- Spring Security `@PreAuthorize` для money-endpoints — `ucp-auth-review`.

$ARGUMENTS
