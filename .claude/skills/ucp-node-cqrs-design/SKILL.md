---
name: ucp-node-cqrs-design
lang: node
description: Спроектировать CQRS-разделение в NestJS-сервисе (Node) по UCP (коды R-CQRS-*) — маркеры Command/Query (Уровень 2) или полный split (Уровень 3: <X>ViewRepository с raw select, read-DTO), read-model через outbox+Kafka, idempotent consumer.
when_to_use: Триггеры — «CQRS для X», «read-модель Y», «вынести чтение в проекцию». При добавлении read-проекций.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# CQRS — проектирование (Node / NestJS + TypeORM)

Ты проектируешь CQRS по **контракту** `backend/cqrs/cqrs-rules.md` (`R-CQRS-*`) и **Node-реализации** `backend/cqrs/node/cqrs-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/usecase-pattern/node/...` (маркеры `Command<R>`/`Query<R>` из `core/usecase.ts`, Handler), `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-QRY-4` ViewRepository, `R-TYPEORM-TX-*` границы транзакций), `kafka` (outbox sync), `ddd-tactical` (агрегат на write-side).

2. **Реши уровень** (`R-CQRS-WHEN-*`/`R-CQRS-TIER-*`): Уровень 2 → lightweight (маркеры + read без транзакции, один `<X>Repository`); Уровень 3 → `<X>ViewRepository` + read-DTO; event-driven → отдельная read-таблица/Redis/ES + outbox. Не вводи полный split без доказанной read-нагрузки (`R-CQRS-WHEN-X1`). Назови выбор.

3. **Command side** (`R-CQRS-CMD-*`): класс с `readonly`-полями `implements Command<R>`; меняет один агрегат; handler: `tx.run` → load → доменный метод → `save` → commit на границе Handler (`R-TYPEORM-TX-1`, транзакционный `EntityManager`/CLS-контекст); возвращает минимум (id/статус/`void`), не read-DTO; валидация входа на request-DTO через class-validator, инварианты — в агрегате.

4. **Query side** (`R-CQRS-QRY-*`): класс `implements Query<R>`; handler через `<X>ViewRepository`, без транзакции и без записи (`R-TYPEORM-TX-3`); raw select с bind-параметрами (`getRawMany`/`dataSource.query`) → read-DTO (frozen plain object / readonly-класс) под UI, не агрегат; не зовёт доменные методы.

5. **Read-model** (`R-CQRS-RM/SYNC-*`): денормализована, восстановима (rebuild-скрипт по агрегатам); sync через **outbox + Kafka** в одну сторону, idempotent consumer (`processed_event`); eventual consistency задекларируй в OpenAPI (`@ApiOperation({ description })`); read-your-writes если критично.

6. **Самопроверка** (§7) + предложи `ucp-node-cqrs-review`. Read-проекции в TypeORM — `ucp-node-typeorm-design`; outbox-publishing — `ucp-node-kafka-design`.

## Антипаттерны, которые НЕ генерировать

- Полный CQRS/разделение БД без боли (`R-CQRS-WHEN-X1/X2`); маркеры без enforcement (`R-CQRS-TIER-X1`).
- Read-DTO из command (`R-CQRS-CMD-X2`); SELECT-for-later-update в command (`R-CQRS-CMD-X1`); несколько агрегатов в одной транзакции без саги (`R-CQRS-CMD-X3`).
- Write в query-handler (`R-CQRS-QRY-X1`); загрузка агрегата целиком (`relations`/lock) ради read-DTO (`R-CQRS-QRY-X2`); агрегат/Entity наружу из query (`R-CQRS-QRY-X3`).
- Sync INSERT/UPDATE read-model в command-транзакции (`R-CQRS-SYNC-X1`); PG-триггеры (`R-CQRS-SYNC-X2`); schema-coupled events (payload = TypeORM-Entity, `R-CQRS-SYNC-X3`); bidirectional sync (`R-CQRS-RM-X3`).

После работы скилла — обязательно `ucp-node-cqrs-review`.

$ARGUMENTS
