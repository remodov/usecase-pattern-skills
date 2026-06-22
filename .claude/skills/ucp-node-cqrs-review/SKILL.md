---
name: ucp-node-cqrs-review
lang: node
description: Ревью CQRS-разделения в NestJS-сервисе (Node/TypeScript, коды R-CQRS-*) — command в транзакции Handler-а, query через ViewRepository без транзакции (raw select), read-model sync через outbox+Kafka, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler-ов с маркерами Command/Query, ViewRepository, read-DTO, outbox-publishers, read-side consumers в NestJS.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью CQRS (Node / NestJS + TypeORM)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/cqrs-rules.md` (`R-CQRS-*`) и **Node-реализации** `backend/cqrs/node/cqrs-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/cqrs-rules.md`** + **`backend/cqrs/node/cqrs-style-guide.md`**.
- Парные: `backend/usecase-pattern/node/...` (`Command`/`Query`/Handler), `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-QRY-4`, `R-TYPEORM-TX-1/3`), `kafka` (outbox/idempotent), `ddd-tactical` (агрегат).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-CQRS-QRY-X2`), не префикс.

2. **Скоп.** Handler-классы с `Command<R>`/`Query<R>`, `*-view.repository.ts` (`TypeOrm<X>ViewRepository`), read-DTO, outbox-publishers, read-side consumers, эндпоинты с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры имеют enforcement (query без транзакции и записи, `R-TYPEORM-TX-3`) — иначе `R-CQRS-TIER-X1`; полный split без боли → `R-CQRS-WHEN-X1`; event-driven read-model с одним Repository → `R-CQRS-TIER-X2`.
   - **Command (`R-CQRS-CMD-*`):** `Command<R>` с `readonly`-полями, меняет один агрегат, commit на границе Handler (`DataSource.transaction`, `R-TYPEORM-TX-1`), возвращает минимум. Read-DTO из command → `R-CQRS-CMD-X2`. SELECT-for-later-update → `R-CQRS-CMD-X1`. Несколько агрегатов без саги → `R-CQRS-CMD-X3`.
   - **Query (`R-CQRS-QRY-*`):** `Query<R>`, через `<X>ViewRepository` (raw select с bind-параметрами → read-DTO, `R-TYPEORM-QRY-4`), без транзакции. Write в query → `R-CQRS-QRY-X1`. Грузит агрегат целиком (с `relations`/lock) ради read-DTO → `R-CQRS-QRY-X2`. Агрегат/Entity наружу → `R-CQRS-QRY-X3`. Зовёт доменный метод → нарушение `R-CQRS-QRY-4`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована, восстановима, одна сторона. Бизнес-логика в read-model → `R-CQRS-RM-X1`. Source-of-truth read-model → `R-CQRS-RM-X2`. Bidirectional sync → `R-CQRS-RM-X3`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+Kafka, idempotent consumer, rebuild при бутстрапе, eventual consistency задекларирована (`@ApiOperation({ description })`). Sync INSERT/UPDATE read-model в command-транзакции → `R-CQRS-SYNC-X1`. PG-триггеры → `R-CQRS-SYNC-X2`. Schema-coupled events (payload = TypeORM-Entity) → `R-CQRS-SYNC-X3`.

4. **Cross-check:** ViewRepository-реализация — `ucp-node-typeorm-review`; outbox/idempotent consumer — `ucp-node-kafka-review`; агрегат на write-side — `ucp-node-ddd-tactical-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — write в query-handler (`R-CQRS-QRY-X1`), sync UPDATE read-model в command-транзакции (`R-CQRS-SYNC-X1`), bidirectional sync (`R-CQRS-RM-X3`), агрегат наружу из query (`R-CQRS-QRY-X3`), schema-coupled events (`R-CQRS-SYNC-X3`).
   - **Предупреждение** — грузит агрегат ради read-DTO (`R-CQRS-QRY-X2`), read-DTO из command (`R-CQRS-CMD-X2`), PG-триггеры sync (`R-CQRS-SYNC-X2`), маркеры без enforcement (`R-CQRS-TIER-X1`), бизнес-логика в read-model (`R-CQRS-RM-X1`).
   - **Замечание** — полный split «just in case» (`R-CQRS-WHEN-X1`), eventual consistency не задекларирована в API (`R-CQRS-SYNC-4`).

## Что не входит

- ViewRepository/SQL — `ucp-node-typeorm-review`. Outbox/consumer — `ucp-node-kafka-review`. Агрегат — `ucp-node-ddd-tactical-review`.

$ARGUMENTS
