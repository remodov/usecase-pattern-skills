---
name: ucp-node-cqrs-design
lang: node
description: Спроектировать CQRS-разделение в NestJS-сервисе (Node) по UCP (требования cqrs/*) — маркеры Command/Query (Уровень 2) или полный split (Уровень 3: <X>ViewRepository с raw select, read-DTO), read-model через outbox+Kafka, idempotent consumer.
when_to_use: Триггеры — «CQRS для X», «read-модель Y», «вынести чтение в проекцию». При добавлении read-проекций.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# CQRS — проектирование (Node / NestJS + TypeORM)

Ты проектируешь CQRS по **контракту** `backend/cqrs/spec.md` (`R-CQRS-*`) и **Node-реализации** `backend/cqrs/references/node/implementation.md`.

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/node/...` (маркеры `Command<R>`/`Query<R>` из `core/usecase.ts`, Handler), `backend/node/typeorm/spec.md` (`typeorm/view-repository-for-projections` ViewRepository, `R-TYPEORM-TX-*` границы транзакций), `kafka` (outbox sync), `ddd-tactical` (агрегат на write-side).

2. **Реши уровень** (`R-CQRS-WHEN-*`/`R-CQRS-TIER-*`): Уровень 2 → lightweight (маркеры + read без транзакции, один `<X>Repository`); Уровень 3 → `<X>ViewRepository` + read-DTO; event-driven → отдельная read-таблица/Redis/ES + outbox. Не вводи полный split без доказанной read-нагрузки (`cqrs/lightweight-first-full-on-evidence`). Назови выбор.

3. **Command side** (`R-CQRS-CMD-*`): класс с `readonly`-полями `implements Command<R>`; меняет один агрегат; handler: `tx.run` → load → доменный метод → `save` → commit на границе Handler (`typeorm/transaction-on-handler`, транзакционный `EntityManager`/CLS-контекст); возвращает минимум (id/статус/`void`), не read-DTO; валидация входа на request-DTO через class-validator, инварианты — в агрегате.

4. **Query side** (`R-CQRS-QRY-*`): класс `implements Query<R>`; handler через `<X>ViewRepository`, без транзакции и без записи (`typeorm/transaction-on-handler`); raw select с bind-параметрами (`getRawMany`/`dataSource.query`) → read-DTO (frozen plain object / readonly-класс) под UI, не агрегат; не зовёт доменные методы.

5. **Read-model** (`R-CQRS-RM/SYNC-*`): денормализована, восстановима (rebuild-скрипт по агрегатам); sync через **outbox + Kafka** в одну сторону, idempotent consumer (`processed_event`); eventual consistency задекларируй в OpenAPI (`@ApiOperation({ description })`); read-your-writes если критично.

6. **Самопроверка** (§7) + предложи `ucp-node-cqrs-review`. Read-проекции в TypeORM — `ucp-node-typeorm-design`; outbox-publishing — `ucp-node-kafka-design`.

## Антипаттерны, которые НЕ генерировать

- Полный CQRS/разделение БД без боли (`R-CQRS-WHEN-X1/X2`); маркеры без enforcement (`cqrs/split-matches-maturity-level`).
- Read-DTO из command (`cqrs/command-returns-minimum`); SELECT-for-later-update в command (`cqrs/command-handler-does-not-query`); несколько агрегатов в одной транзакции без саги (`cqrs/command-changes-one-aggregate`).
- Write в query-handler (`cqrs/query-is-read-only`); загрузка агрегата целиком (`relations`/lock) ради read-DTO (`cqrs/read-via-projection-not-aggregate`); агрегат/Entity наружу из query (`cqrs/query-returns-read-model`).
- Sync INSERT/UPDATE read-model в command-транзакции (`cqrs/read-model-synced-by-events`); PG-триггеры (`cqrs/read-model-synced-by-events`); schema-coupled events (payload = TypeORM-Entity, `cqrs/events-not-coupled-to-write-schema`); bidirectional sync (`cqrs/projection-has-no-logic-or-backflow`).

После работы скилла — обязательно `ucp-node-cqrs-review`.

$ARGUMENTS
