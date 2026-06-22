---
name: ucp-node-typeorm-review
lang: node
description: Ревью persistence-слоя на TypeORM 0.3 (DataSource API) по UCP (коды R-TYPEORM-*) — порт/маппер Entity↔domain, граница TX на Handler, Data Mapper без ActiveRecord, relations явно, ViewRepository, деньги string+decimal, миграции.
when_to_use: Изменения в adapters/out/persistence (*.entity.ts, *.repository.ts, *.mapper.ts) или в миграциях TypeORM.
paths: "**/adapters/out/persistence/**, **/migrations/**"
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью persistence (Node / TypeORM 0.3 DataSource API)

Ты ревьюишь persistence-слой на соответствие `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-*`). Репозиторий
реализует порт из `core/`, маппит Entity↔domain, граница транзакции — на Handler. Механический слой
(импорт-границы, типы) ловит CI-стек (`eslint`, `tsc --noEmit` strict); здесь — семантика.

## Зависимости

- **`.claude/docs/backend/node/typeorm/typeorm-rules.md`** — правила `R-TYPEORM-*` (код-примеры включены).
- Парные: `backend/usecase-pattern/node/...` (порт/слои, `R-LAY-*`/`R-HEX-*`), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-6/8/9`), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (locks/bulk, `PG-W-*`), `backend/cqrs/cqrs-rules.md` (`R-CQRS-4` read-проекции).

## Инструкции

1. **Прочти** `typeorm-rules.md`. Цитируй конкретные коды (`R-TYPEORM-REPO-X1`), не префикс.

2. **Скоп.** `adapters/out/persistence/**` (`*.entity.ts`, `*.repository.ts`, `*.mapper.ts`, `*view*.ts`), каталог миграций TypeORM (`migrations/**`), порт-интерфейс в `core/<bc>/port/`, `git diff` на `.ts`.

3. **Прогон.**
   - **Repository:** реализует порт из `core/`, в `adapters/out/persistence/`, биндится через DI-токен (`NESTBOOT-6`)? Public-методы принимают/возвращают доменные объекты, не Entity/raw row? `EntityManager`/`Repository<T>` инжектится, не создаётся внутри? Покрыт интеграционным тестом против Testcontainers без моков `EntityManager` (`R-TYPEORM-REPO-1..4`). Возврат Entity наружу → `R-TYPEORM-REPO-X1`. Бизнес-логика в репозитории (`if (order.status === ...)`) → `R-TYPEORM-REPO-X2`. `DataSource`/`createQueryBuilder` в `core/` → `R-TYPEORM-REPO-X3` (cross-ref `R-HEX-X1`).
   - **Entity:** `@Entity`+`@Column` в `adapters/out/persistence/`, не в `core/`; relations `eager: false`, без lazy-Promise; Data Mapper — не наследует `BaseEntity` (`R-TYPEORM-ENT-1/3`). Типы: деньги `numeric(p,s)` → `string` + Big.js/decimal.js, время `timestamptz` → `Date`, идентификаторы `uuid` (`R-TYPEORM-ENT-2`, cross-ref `PG-T-013/030/040`). Entity ≠ domain ≠ DTO (`R-TYPEORM-REPO-2`). Доменная логика/инварианты на Entity → `R-TYPEORM-ENT-X1`. ActiveRecord (`extends BaseEntity`, `order.save()`) → `R-TYPEORM-ENT-X2`. `number` для money через `parseFloat`-transformer → `R-TYPEORM-ENT-X3`.
   - **Маппинг:** явные `toDomain`/`toEntity` рядом с репозиторием, сборка агрегата из Entity-графа в маппере (`R-TYPEORM-MAP-1/2`). «Универсальный» `Object.assign`/spread Entity → domain → `R-TYPEORM-MAP-X1`.
   - **Транзакции:** граница на Handler — `dataSource.transaction(async (em) => ...)` или CLS-обёртка (`typeorm-transactional`); внутри — репозитории через транзакционный `EntityManager`, не глобальный DataSource; read-методы без транзакции (`R-TYPEORM-TX-1/2/3`). `queryRunner.commitTransaction()`/`startTransaction()` в репозитории → `R-TYPEORM-TX-X1`. Несколько `save()` без общей транзакции в одной операции → `R-TYPEORM-TX-X2`.
   - **Запросы:** `find*` с явным `relations: [...]` или QueryBuilder с `leftJoinAndSelect` — против N+1 (`R-TYPEORM-QRY-1`); update агрегата — load → мутация домена → `save` полного агрегата, точечный — `update().set().where()` (`R-TYPEORM-QRY-2`); пагинация `take/skip`/keyset, `count` отдельно (`R-TYPEORM-QRY-3`); read-проекции — `TypeOrm<X>ViewRepository` с raw `select` → read-DTO (`R-TYPEORM-QRY-4`, cross-ref `R-CQRS-4`); именованные bind-параметры (`R-TYPEORM-QRY-5`). Lazy relations → `R-TYPEORM-QRY-X1`. `save()` подмножества полей без load → `R-TYPEORM-QRY-X2`. `find()` без `take` на больших таблицах → `R-TYPEORM-QRY-X3`. Сырой SQL конкатенацией → `R-TYPEORM-QRY-X4`.
   - **Миграции:** схема через `migration:generate` + вычитка руками, запуск `migration:run` отдельной командой (`R-TYPEORM-MIG-1`, cross-ref `NESTBOOT-9`); безопасность по `PG-M-*` (`R-TYPEORM-MIG-2`). `synchronize: true` вне одноразовых unit-тестов → `R-TYPEORM-MIG-X1` (cross-ref `NESTBOOT-X4`). Правка применённой миграции → `R-TYPEORM-MIG-X2`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); транзакции/блокировки под нагрузкой — `ucp-pg-runtime-review`; CQRS-разделение — `ucp-cqrs-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — возврат Entity наружу (`R-TYPEORM-REPO-X1`), `DataSource`/QueryBuilder в `core/` (`R-TYPEORM-REPO-X3`), `commitTransaction` в репозитории (`R-TYPEORM-TX-X1`), `save()` частичного объекта без load (`R-TYPEORM-QRY-X2`), сырой SQL конкатенацией (`R-TYPEORM-QRY-X4`), money `number` (`R-TYPEORM-ENT-X3`), `synchronize: true` в проде (`R-TYPEORM-MIG-X1`).
   - **Предупреждение** — бизнес-логика в репозитории (`R-TYPEORM-REPO-X2`), доменная логика на Entity (`R-TYPEORM-ENT-X1`), ActiveRecord-паттерн (`R-TYPEORM-ENT-X2`), `Object.assign`-маппинг (`R-TYPEORM-MAP-X1`), несколько `save()` без транзакции (`R-TYPEORM-TX-X2`), lazy relations (`R-TYPEORM-QRY-X1`), `find()` без `take` (`R-TYPEORM-QRY-X3`), правка применённой миграции (`R-TYPEORM-MIG-X2`).
   - **Замечание** — маппинг размазан по репозиторию (`R-TYPEORM-MAP-2`), `(await find()).length` вместо `count`, нет интеграционного теста на репозиторий (`R-TYPEORM-REPO-4`), generate-миграция не вычитана (`R-TYPEORM-MIG-1`).

## Что не входит

- Бизнес-операции — `ucp-node-pattern-review`. Доменные инварианты — `ucp-node-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.

$ARGUMENTS
