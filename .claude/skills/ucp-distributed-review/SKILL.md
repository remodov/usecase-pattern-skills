---
name: ucp-distributed-review
description: Ревью распределённых паттернов на Java/Spring (коды R-DIST-*) — saga и compensation, idempotency на receiver, eventual consistency, outbox/inbox, запрет 2PC/JTA/XA/ChainedTransactionManager.
when_to_use: Ревью cross-service flows, saga-классов, idempotency-таблиц, multi-datasource конфигов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью distributed patterns

Ты ревьюишь cross-service flows и распределённые паттерны на соответствие Distributed Patterns Style Guide. Главные точки контроля: saga (compensation + state в БД), idempotency на receiver, outbox publishing, отсутствие 2PC.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/distributed-patterns-rules.md`** — индекс всех правил (полный текст — соответствующий `*-style-guide.md`). Подгруппы: `R-DIST-WHEN-*` (когда применять), `R-DIST-SAGA-*` (saga), `R-DIST-IDEM-*` (idempotency), `R-DIST-EC-*` (eventual consistency), `R-DIST-OBX-*` (outbox/inbox), `R-DIST-COMP-*` (compensation), `R-DIST-TX-*` (запрет 2PC).
- Парные: `backend/kafka/kafka-rules.md` (`R-KFK-OBX-*`/`R-KFK-IDEM-*`), `backend/cqrs/cqrs-rules.md` (`R-CQRS-SYNC-*`), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-19` Idempotency-Key), `backend/rest-api/rest-api-rules.md` (`R-HDR-3` Idempotency-Key header).

## Инструкции

1. **Прочти** `.claude/docs/backend/distributed-patterns/distributed-patterns-rules.md`. Цитируй коды (`R-DIST-SAGA-X1`, `R-DIST-IDEM-X1`).

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
   - `JtaTransactionManager` или `XADataSource` в Spring config — `R-DIST-SAGA-X1` / `R-DIST-TX-X1` критическое.
   - `ChainedTransactionManager` для multi-datasource — `R-DIST-TX-X3`.
   - Saga-orchestrator без compensation-методов (только happy path) — `R-DIST-SAGA-X2`/`R-DIST-COMP-X1` критическое.
   - Saga state в `Map<UUID, SagaState>` (in-memory) без БД — `R-DIST-SAGA-X3`.
   - Saga-orchestrator реализован как `@Service`, но логика смешана с handler — `R-DIST-SAGA-X4`.
   - `@KafkaListener` для money / critical-event без проверки `eventId` через `processed_event` — `R-DIST-IDEM-X1` критическое.
   - HTTP money-endpoint без `Idempotency-Key` обработки (нет `idempotency_record` таблицы) — `R-DIST-IDEM-X1` + `AUTH-19`.
   - Producer с `enable.idempotence: false` — `R-DIST-IDEM-X2`.
   - Client-side код генерирует `Idempotency-Key = UUID.randomUUID()` каждый retry — `R-DIST-IDEM-X3`.
   - Endpoint возвращает eventual-consistent данные без `description` в OpenAPI про задержку — `R-DIST-EC-X1`.
   - 2PC для money-операций между сервисами — `R-DIST-EC-X2` критическое.
   - `kafkaTemplate.send(...)` в command-handler без outbox — `R-DIST-OBX-X1`.
   - `@TransactionalEventListener(phase = AFTER_COMMIT)` для Kafka send — `R-DIST-OBX-X2`.
   - `DELETE FROM payment WHERE id = ?` как compensation — `R-DIST-COMP-X2` критическое (теряется audit + создаются «висящие» refund'ы).
   - Compensation бросает exception без отправки в DLQ + alert — `R-DIST-COMP-X3` (висящие деньги).

5. **При ревью DDL `saga_*`:**
   - Поля: `saga_id PK`, `status` (IN_PROGRESS/COMPLETED/FAILED/COMPENSATING), `current_step`, `payload JSONB`, `started_at`, `completed_at`, `last_error`.
   - Индекс по `status` (для recovery in-flight sagas).

6. **При ревью DDL `processed_event` / `idempotency_record`:**
   - PRIMARY KEY на natural-key (`event_id` / `idempotency_key`) — UNIQUE constraint предотвращает дубли под race conditions.
   - TTL strategy (background-cleanup или partition+drop_old).

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md`.

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
