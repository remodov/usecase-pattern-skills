---
name: ucp-node-typeorm-design
lang: node
description: Сгенерировать persistence-слой на TypeORM 0.3 (DataSource API) из доменного порта по UCP (требования typeorm/*) — TypeOrm<X>Repository реализует порт из core/, маппер Entity↔domain, TX на Handler, relations явно, ViewRepository, миграции.
when_to_use: После ucp-node-pattern-design (есть порт в core/). Триггеры — «репозиторий на TypeORM для X», «persistence для агрегата Y».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(typeorm*) Bash(jest*)
---

# Проектирование persistence (Node / TypeORM 0.3 DataSource API)

Ты генерируешь persistence-слой согласно `backend/node/typeorm/spec.md` (`R-TYPEORM-*`). Репозиторий реализует
порт из `core/`, маппит Entity↔domain, граница транзакции — на Handler.

## Инструкции

1. **Прочитай** `.claude/docs/backend/node/typeorm/spec.md` (`R-TYPEORM-*`). Связанные: `backend/usecase-pattern/node/...` (порт/слои), `backend/node/nest-bootstrap/spec.md` (`nest-bootstrap/inject-by-port-tokens` DI-токены, `NESTBOOT-8/9` wiring и миграции), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (locks/bulk).

2. **Вход:** доменный порт-интерфейс из `core/<bc>/port/` (от `ucp-node-pattern-design`) + агрегат.

3. **Произведи код** (TypeScript strict, Data Mapper; без комментариев; коды правил НЕ цитируй):
   - `adapters/out/persistence/<x>.entity.ts` — `@Entity` + `@Column`, без `BaseEntity`; relations `eager: false`, без lazy-Promise; типы: деньги `numeric(p,s)` → `string` + Big.js/decimal.js (НЕ `number`), время `timestamptz` → `Date`, идентификаторы `uuid` (`R-TYPEORM-ENT-1/2/3`).
   - `adapters/out/persistence/<x>.mapper.ts` — явные `toDomain(entity)`/`toEntity(aggregate)` (`R-TYPEORM-MAP-1/2`).
   - `adapters/out/persistence/typeorm-<x>.repository.ts` — `TypeOrm<X>Repository` реализует порт, биндится через DI-токен (`{ provide: X_REPOSITORY, useClass: ... }`); `EntityManager` инжектится/резолвится из транзакционного контекста; методы принимают/возвращают домен; запросы с явным `relations: [...]`/`leftJoinAndSelect`, bind-параметры именованные (`R-TYPEORM-REPO-*`, `R-TYPEORM-QRY-1/5`).
   - read-проекции — `TypeOrm<X>ViewRepository`: raw `select` (`getRawMany`/bind-параметры) → read-DTO (`typeorm/view-repository-for-projections`).
   - миграция — `typeorm migration:generate`, **вычитать diff руками** (rename видит как drop+create); запуск `migration:run` отдельной командой; `synchronize: false` (`typeorm/schema-via-reviewed-migrations`, `nest-bootstrap/datasource-and-migrations`); безопасность по `PG-M-*`.

4. **Граница транзакции — НЕ в репозитории** (`dataSource.transaction(async (em) => ...)` или CLS-обёртка на Handler, `R-TYPEORM-TX-1/2`). Update агрегата — load → мутация домена → `save(toEntity(...))` полного агрегата в транзакции (`typeorm/update-full-aggregate-or-explicit`).

5. **Самопроверка** + предложи `ucp-node-typeorm-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат Entity наружу (`typeorm/repository-speaks-domain-types`); бизнес-логика в репозитории (`typeorm/no-business-logic-in-repository`); `commitTransaction()` внутри репозитория (`typeorm/transaction-on-handler`).
- `DataSource`/`createQueryBuilder` в `core/` (`typeorm/port-in-core-implementation-in-adapter`); доменная логика на Entity (`typeorm/entities-are-anemic-data-mapper`); ActiveRecord `extends BaseEntity`/`order.save()` (`typeorm/entities-are-anemic-data-mapper`).
- `number` для money-колонок через `parseFloat`-transformer (`typeorm/precise-column-types`); lazy relations `Promise<T[]>` (`typeorm/relations-are-explicit`).
- `save()` частичного объекта без load (`typeorm/update-full-aggregate-or-explicit`); `find()` без `take` на больших таблицах (`typeorm/pagination-and-counting`); сырой SQL конкатенацией (`typeorm/bind-parameters-only`).
- `synchronize: true` вне одноразовых unit-тестов (`typeorm/schema-via-reviewed-migrations`); несколько `save()` без общей транзакции (`typeorm/transaction-on-handler`).

После работы скилла — обязательно `ucp-node-typeorm-review`.

$ARGUMENTS
