---
name: ucp-node-cqrs-review
lang: node
description: Ревью CQRS-разделения в NestJS-сервисе (Node/TypeScript, коды R-CQRS-*) — command в транзакции Handler-а, query через ViewRepository без транзакции (raw select), read-model sync через outbox+Kafka, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler-ов с маркерами Command/Query, ViewRepository, read-DTO, outbox-publishers, read-side consumers в NestJS.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS (Node / NestJS + TypeORM)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/spec.md` (`R-CQRS-*`) и **Node-реализации** `backend/cqrs/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/spec.md`** + **`backend/cqrs/references/node/implementation.md`**.
- Парные: `backend/usecase-pattern/node/...` (`Command`/`Query`/Handler), `backend/node/typeorm/spec.md` (`typeorm/view-repository-for-projections`, `R-TYPEORM-TX-1/3`), `kafka` (outbox/idempotent), `ddd-tactical` (агрегат).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`cqrs/read-via-projection-not-aggregate`), не префикс.

2. **Скоп.** Handler-классы с `Command<R>`/`Query<R>`, `*-view.repository.ts` (`TypeOrm<X>ViewRepository`), read-DTO, outbox-publishers, read-side consumers, эндпоинты с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры имеют enforcement (query без транзакции и записи, `typeorm/transaction-on-handler`) — иначе `cqrs/split-matches-maturity-level`; полный split без боли → `cqrs/lightweight-first-full-on-evidence`; event-driven read-model с одним Repository → `cqrs/split-matches-maturity-level`.
   - **Command (`R-CQRS-CMD-*`):** `Command<R>` с `readonly`-полями, меняет один агрегат, commit на границе Handler (`DataSource.transaction`, `typeorm/transaction-on-handler`), возвращает минимум. Read-DTO из command → `cqrs/command-returns-minimum`. SELECT-for-later-update → `cqrs/command-handler-does-not-query`. Несколько агрегатов без саги → `cqrs/command-changes-one-aggregate`.
   - **Query (`R-CQRS-QRY-*`):** `Query<R>`, через `<X>ViewRepository` (raw select с bind-параметрами → read-DTO, `typeorm/view-repository-for-projections`), без транзакции. Write в query → `cqrs/query-is-read-only`. Грузит агрегат целиком (с `relations`/lock) ради read-DTO → `cqrs/read-via-projection-not-aggregate`. Агрегат/Entity наружу → `cqrs/query-returns-read-model`. Зовёт доменный метод → нарушение `cqrs/query-is-read-only`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована, восстановима, одна сторона. Бизнес-логика в read-model → `cqrs/projection-has-no-logic-or-backflow`. Source-of-truth read-model → `cqrs/read-model-is-rebuildable`. Bidirectional sync → `cqrs/projection-has-no-logic-or-backflow`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+Kafka, idempotent consumer, rebuild при бутстрапе, eventual consistency задекларирована (`@ApiOperation({ description })`). Sync INSERT/UPDATE read-model в command-транзакции → `cqrs/read-model-synced-by-events`. PG-триггеры → `cqrs/read-model-synced-by-events`. Schema-coupled events (payload = TypeORM-Entity) → `cqrs/events-not-coupled-to-write-schema`.

4. **Cross-check:** ViewRepository-реализация — `ucp-node-typeorm-review`; outbox/idempotent consumer — `ucp-node-kafka-review`; агрегат на write-side — `ucp-node-ddd-tactical-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — write в query-handler (`cqrs/query-is-read-only`), sync UPDATE read-model в command-транзакции (`cqrs/read-model-synced-by-events`), bidirectional sync (`cqrs/projection-has-no-logic-or-backflow`), агрегат наружу из query (`cqrs/query-returns-read-model`), schema-coupled events (`cqrs/events-not-coupled-to-write-schema`).
   - **Предупреждение** — грузит агрегат ради read-DTO (`cqrs/read-via-projection-not-aggregate`), read-DTO из command (`cqrs/command-returns-minimum`), PG-триггеры sync (`cqrs/read-model-synced-by-events`), маркеры без enforcement (`cqrs/split-matches-maturity-level`), бизнес-логика в read-model (`cqrs/projection-has-no-logic-or-backflow`).
   - **Замечание** — полный split «just in case» (`cqrs/lightweight-first-full-on-evidence`), eventual consistency не задекларирована в API (`cqrs/eventual-consistency-declared`).

## Что не входит

- ViewRepository/SQL — `ucp-node-typeorm-review`. Outbox/consumer — `ucp-node-kafka-review`. Агрегат — `ucp-node-ddd-tactical-review`.

$ARGUMENTS
