---
name: ucp-node-typeorm-review
lang: node
description: Ревью persistence-слоя на TypeORM 0.3 (DataSource API) по UCP (требования typeorm/*) — порт/маппер Entity↔domain, граница TX на Handler, Data Mapper без ActiveRecord, relations явно, ViewRepository, деньги string+decimal, миграции.
when_to_use: Изменения в adapters/out/persistence (*.entity.ts, *.repository.ts, *.mapper.ts) или в миграциях TypeORM.
paths: "**/adapters/out/persistence/**, **/migrations/**"
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью persistence (Node / TypeORM 0.3 DataSource API)

Ты ревьюишь persistence-слой на соответствие `backend/node/typeorm/spec.md` (`R-TYPEORM-*`). Репозиторий
реализует порт из `core/`, маппит Entity↔domain, граница транзакции — на Handler. Механический слой
(импорт-границы, типы) ловит CI-стек (`eslint`, `tsc --noEmit` strict); здесь — семантика.

## Зависимости

- **`.claude/docs/backend/node/typeorm/spec.md`** — правила `R-TYPEORM-*` (код-примеры включены).
- Парные: `backend/usecase-pattern/node/...` (порт/слои, `R-LAY-*`/`R-HEX-*`), `backend/node/nest-bootstrap/spec.md` (`NESTBOOT-6/8/9`), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (locks/bulk, `PG-W-*`), `backend/cqrs/spec.md` (`usecase-pattern/reads-via-read-model` read-проекции).

## Инструкции

1. **Прочти** `typeorm/spec.md`. Цитируй конкретные коды (`typeorm/repository-speaks-domain-types`), не префикс.

2. **Скоп.** `adapters/out/persistence/**` (`*.entity.ts`, `*.repository.ts`, `*.mapper.ts`, `*view*.ts`), каталог миграций TypeORM (`migrations/**`), порт-интерфейс в `core/<bc>/port/`, `git diff` на `.ts`.

3. **Прогон.**
   - **Repository:** реализует порт из `core/`, в `adapters/out/persistence/`, биндится через DI-токен (`nest-bootstrap/inject-by-port-tokens`)? Public-методы принимают/возвращают доменные объекты, не Entity/raw row? `EntityManager`/`Repository<T>` инжектится, не создаётся внутри? Покрыт интеграционным тестом против Testcontainers без моков `EntityManager` (`R-TYPEORM-REPO-1..4`). Возврат Entity наружу → `typeorm/repository-speaks-domain-types`. Бизнес-логика в репозитории (`if (order.status === ...)`) → `typeorm/no-business-logic-in-repository`. `DataSource`/`createQueryBuilder` в `core/` → `typeorm/port-in-core-implementation-in-adapter` (cross-ref `hexagonal/outbound-port-interface-in-core`).
   - **Entity:** `@Entity`+`@Column` в `adapters/out/persistence/`, не в `core/`; relations `eager: false`, без lazy-Promise; Data Mapper — не наследует `BaseEntity` (`R-TYPEORM-ENT-1/3`). Типы: деньги `numeric(p,s)` → `string` + Big.js/decimal.js, время `timestamptz` → `Date`, идентификаторы `uuid` (`typeorm/precise-column-types`, cross-ref `PG-T-013/030/040`). Entity ≠ domain ≠ DTO (`typeorm/repository-speaks-domain-types`). Доменная логика/инварианты на Entity → `typeorm/entities-are-anemic-data-mapper`. ActiveRecord (`extends BaseEntity`, `order.save()`) → `typeorm/entities-are-anemic-data-mapper`. `number` для money через `parseFloat`-transformer → `typeorm/precise-column-types`.
   - **Маппинг:** явные `toDomain`/`toEntity` рядом с репозиторием, сборка агрегата из Entity-графа в маппере (`R-TYPEORM-MAP-1/2`). «Универсальный» `Object.assign`/spread Entity → domain → `typeorm/explicit-mapper`.
   - **Транзакции:** граница на Handler — `dataSource.transaction(async (em) => ...)` или CLS-обёртка (`typeorm-transactional`); внутри — репозитории через транзакционный `EntityManager`, не глобальный DataSource; read-методы без транзакции (`R-TYPEORM-TX-1/2/3`). `queryRunner.commitTransaction()`/`startTransaction()` в репозитории → `typeorm/transaction-on-handler`. Несколько `save()` без общей транзакции в одной операции → `typeorm/transaction-on-handler`.
   - **Запросы:** `find*` с явным `relations: [...]` или QueryBuilder с `leftJoinAndSelect` — против N+1 (`typeorm/relations-are-explicit`); update агрегата — load → мутация домена → `save` полного агрегата, точечный — `update().set().where()` (`typeorm/update-full-aggregate-or-explicit`); пагинация `take/skip`/keyset, `count` отдельно (`typeorm/pagination-and-counting`); read-проекции — `TypeOrm<X>ViewRepository` с raw `select` → read-DTO (`typeorm/view-repository-for-projections`, cross-ref `usecase-pattern/reads-via-read-model`); именованные bind-параметры (`typeorm/bind-parameters-only`). Lazy relations → `typeorm/relations-are-explicit`. `save()` подмножества полей без load → `typeorm/update-full-aggregate-or-explicit`. `find()` без `take` на больших таблицах → `typeorm/pagination-and-counting`. Сырой SQL конкатенацией → `typeorm/bind-parameters-only`.
   - **Миграции:** схема через `migration:generate` + вычитка руками, запуск `migration:run` отдельной командой (`typeorm/schema-via-reviewed-migrations`, cross-ref `nest-bootstrap/datasource-and-migrations`); безопасность по `PG-M-*` (`typeorm/schema-via-reviewed-migrations`). `synchronize: true` вне одноразовых unit-тестов → `typeorm/schema-via-reviewed-migrations` (cross-ref `nest-bootstrap/datasource-and-migrations`). Правка применённой миграции → `typeorm/schema-via-reviewed-migrations`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); транзакции/блокировки под нагрузкой — `ucp-pg-runtime-review`; CQRS-разделение — `ucp-cqrs-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — возврат Entity наружу (`typeorm/repository-speaks-domain-types`), `DataSource`/QueryBuilder в `core/` (`typeorm/port-in-core-implementation-in-adapter`), `commitTransaction` в репозитории (`typeorm/transaction-on-handler`), `save()` частичного объекта без load (`typeorm/update-full-aggregate-or-explicit`), сырой SQL конкатенацией (`typeorm/bind-parameters-only`), money `number` (`typeorm/precise-column-types`), `synchronize: true` в проде (`typeorm/schema-via-reviewed-migrations`).
   - **Предупреждение** — бизнес-логика в репозитории (`typeorm/no-business-logic-in-repository`), доменная логика на Entity (`typeorm/entities-are-anemic-data-mapper`), ActiveRecord-паттерн (`typeorm/entities-are-anemic-data-mapper`), `Object.assign`-маппинг (`typeorm/explicit-mapper`), несколько `save()` без транзакции (`typeorm/transaction-on-handler`), lazy relations (`typeorm/relations-are-explicit`), `find()` без `take` (`typeorm/pagination-and-counting`), правка применённой миграции (`typeorm/schema-via-reviewed-migrations`).
   - **Замечание** — маппинг размазан по репозиторию (`typeorm/explicit-mapper`), `(await find()).length` вместо `count`, нет интеграционного теста на репозиторий (`typeorm/repository-integration-tested`), generate-миграция не вычитана (`typeorm/schema-via-reviewed-migrations`).

## Что не входит

- Бизнес-операции — `ucp-node-pattern-review`. Доменные инварианты — `ucp-node-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.

$ARGUMENTS
