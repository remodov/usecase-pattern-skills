---
name: ucp-node-typeorm-design
lang: node
description: Сгенерировать persistence-слой на TypeORM 0.3 (DataSource API) из доменного порта по UCP (коды R-TYPEORM-*) — TypeOrm<X>Repository реализует порт из core/, маппер Entity↔domain, TX на Handler, relations явно, ViewRepository, миграции.
when_to_use: После ucp-node-pattern-design (есть порт в core/). Триггеры — «репозиторий на TypeORM для X», «persistence для агрегата Y».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(typeorm*) Bash(jest*)
---

# Проектирование persistence (Node / TypeORM 0.3 DataSource API)

Ты генерируешь persistence-слой согласно `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-*`). Репозиторий реализует
порт из `core/`, маппит Entity↔domain, граница транзакции — на Handler.

## Инструкции

1. **Прочитай** `.claude/docs/backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-*`). Связанные: `backend/usecase-pattern/node/...` (порт/слои), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-6` DI-токены, `NESTBOOT-8/9` wiring и миграции), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (locks/bulk).

2. **Вход:** доменный порт-интерфейс из `core/<bc>/port/` (от `ucp-node-pattern-design`) + агрегат.

3. **Произведи код** (TypeScript strict, Data Mapper; без комментариев; коды правил НЕ цитируй):
   - `adapters/out/persistence/<x>.entity.ts` — `@Entity` + `@Column`, без `BaseEntity`; relations `eager: false`, без lazy-Promise; типы: деньги `numeric(p,s)` → `string` + Big.js/decimal.js (НЕ `number`), время `timestamptz` → `Date`, идентификаторы `uuid` (`R-TYPEORM-ENT-1/2/3`).
   - `adapters/out/persistence/<x>.mapper.ts` — явные `toDomain(entity)`/`toEntity(aggregate)` (`R-TYPEORM-MAP-1/2`).
   - `adapters/out/persistence/typeorm-<x>.repository.ts` — `TypeOrm<X>Repository` реализует порт, биндится через DI-токен (`{ provide: X_REPOSITORY, useClass: ... }`); `EntityManager` инжектится/резолвится из транзакционного контекста; методы принимают/возвращают домен; запросы с явным `relations: [...]`/`leftJoinAndSelect`, bind-параметры именованные (`R-TYPEORM-REPO-*`, `R-TYPEORM-QRY-1/5`).
   - read-проекции — `TypeOrm<X>ViewRepository`: raw `select` (`getRawMany`/bind-параметры) → read-DTO (`R-TYPEORM-QRY-4`).
   - миграция — `typeorm migration:generate`, **вычитать diff руками** (rename видит как drop+create); запуск `migration:run` отдельной командой; `synchronize: false` (`R-TYPEORM-MIG-1`, `NESTBOOT-9`); безопасность по `PG-M-*`.

4. **Граница транзакции — НЕ в репозитории** (`dataSource.transaction(async (em) => ...)` или CLS-обёртка на Handler, `R-TYPEORM-TX-1/2`). Update агрегата — load → мутация домена → `save(toEntity(...))` полного агрегата в транзакции (`R-TYPEORM-QRY-2`).

5. **Самопроверка** + предложи `ucp-node-typeorm-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат Entity наружу (`R-TYPEORM-REPO-X1`); бизнес-логика в репозитории (`R-TYPEORM-REPO-X2`); `commitTransaction()` внутри репозитория (`R-TYPEORM-TX-X1`).
- `DataSource`/`createQueryBuilder` в `core/` (`R-TYPEORM-REPO-X3`); доменная логика на Entity (`R-TYPEORM-ENT-X1`); ActiveRecord `extends BaseEntity`/`order.save()` (`R-TYPEORM-ENT-X2`).
- `number` для money-колонок через `parseFloat`-transformer (`R-TYPEORM-ENT-X3`); lazy relations `Promise<T[]>` (`R-TYPEORM-QRY-X1`).
- `save()` частичного объекта без load (`R-TYPEORM-QRY-X2`); `find()` без `take` на больших таблицах (`R-TYPEORM-QRY-X3`); сырой SQL конкатенацией (`R-TYPEORM-QRY-X4`).
- `synchronize: true` вне одноразовых unit-тестов (`R-TYPEORM-MIG-X1`); несколько `save()` без общей транзакции (`R-TYPEORM-TX-X2`).

После работы скилла — обязательно `ucp-node-typeorm-review`.

$ARGUMENTS
