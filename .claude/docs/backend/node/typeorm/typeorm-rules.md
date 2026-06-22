# TypeORM — индекс правил (Node persistence)

> **Что это.** Persistence-слой на TypeORM 0.3+ (DataSource API) + PostgreSQL по UCP. Языко-специфичный concern
> Node-биндинга (аналог Java `jooq` / `R-JOOQ-*` и Python `sqlalchemy` / `R-SQLA-*`) — **только Node**, префикс
> `R-TYPEORM-*`. Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет).
> Коды: `R-TYPEORM-<GRP>-<N>` — обязательно, `R-TYPEORM-<GRP>-X<N>` — антипаттерн (запрещено).
> PostgreSQL-правила (типы/индексы/миграции/runtime) — язык-нейтральны, см. `pg-*-rules.md` (`PG-T-*`, `PG-M-*`).

Суть: репозиторий реализует **порт из `core/`**, принимает/возвращает **доменные объекты** (не Entity); ORM-Entity — деталь persistence; граница транзакции — на Handler; только DataSource API, не legacy ActiveRecord.

## 1. Repository-pattern
**MUST:**
- **R-TYPEORM-REPO-1.** Доменный порт — интерфейс в `core/<bc>/port/`; реализация — `TypeOrm<X>Repository` в `adapters/out/persistence/`, биндится через DI-токен (cross-ref `NESTBOOT-6`).
- **R-TYPEORM-REPO-2.** Public-методы принимают/возвращают **доменные объекты** (Aggregate/VO/read-DTO), не Entity и не raw row (cross-ref `R-LAY-2`). ORM-Entity ≠ domain ≠ DTO — три разных типа.
- **R-TYPEORM-REPO-3.** `EntityManager`/`Repository<T>` инжектится (из DataSource или транзакционного контекста Handler'а), не создаётся внутри методов.
- **R-TYPEORM-REPO-4.** Каждый репозиторий покрыт интеграционным тестом против Testcontainers Postgres, без моков `EntityManager`.

**MUST NOT:**
- **R-TYPEORM-REPO-X1.** Возврат Entity наружу из репозитория — Entity внутренняя.
- **R-TYPEORM-REPO-X2.** Бизнес-логика в репозитории (`if (order.status === ...)`).
- **R-TYPEORM-REPO-X3.** Прямой `DataSource`/`createQueryBuilder` в `core/` (домен/хендлер) — только через порт (cross-ref `R-HEX-X1`).

## 2. Entity
**MUST:**
- **R-TYPEORM-ENT-1.** Entity (`@Entity` + `@Column`, Data Mapper-стиль) живут в `adapters/out/persistence/`, не в `core/`; relations с `eager: false` везде, `lazy`-Promise-relations не используются.
- **R-TYPEORM-ENT-2.** Типы: деньги — `numeric(p, s)` → **`string` + Big.js/decimal.js, НЕ `number`** (TypeORM отдаёт numeric строкой — это правильно, не приводить через `parseFloat`); время — `timestamptz` → `Date` (UTC-инстант; локальную интерпретацию — на edge); идентификаторы — `uuid` (cross-ref `pg-types` `PG-T-013/030/040`).
- **R-TYPEORM-ENT-3.** Только DataSource API (Data Mapper): Entity не наследует `BaseEntity`.

```ts
@Column({ type: 'numeric', precision: 19, scale: 4 }) amount: string;   // Big(amount) в маппере
@Column({ type: 'timestamptz' }) createdAt: Date;
```

**MUST NOT:**
- **R-TYPEORM-ENT-X1.** Доменная логика/инварианты на Entity — она анемичная persistence-структура; инварианты — в доменном агрегате.
- **R-TYPEORM-ENT-X2.** ActiveRecord-паттерн (`extends BaseEntity`, `order.save()`) — persistence размазывается по домену, граница транзакции теряется.
- **R-TYPEORM-ENT-X3.** `number` для money-колонок (`transformer` с `parseFloat`) — потеря точности на binary float.

## 3. Маппинг Entity ↔ domain
**MUST:**
- **R-TYPEORM-MAP-1.** Явный маппер `toDomain(entity): Aggregate` и `toEntity(aggregate): Entity`, рядом с репозиторием.
- **R-TYPEORM-MAP-2.** Сборка агрегата из Entity-графа — в маппере, не размазана по репозиторию.

**MUST NOT:**
- **R-TYPEORM-MAP-X1.** «Универсальный» маппинг через `Object.assign`/spread Entity → domain; Entity напрямую как domain.

## 4. Транзакции
**MUST:**
- **R-TYPEORM-TX-1.** Граница транзакции — на Handler: `dataSource.transaction(async (em) => ...)` или transactional-обёртка (`typeorm-transactional` CLS-hooked), не в репозитории (cross-ref `R-JOOQ-TX-1`).
- **R-TYPEORM-TX-2.** Внутри транзакции репозитории работают через транзакционный `EntityManager` (передаётся/резолвится из CLS-контекста), не через глобальный DataSource — иначе запросы уходят мимо транзакции.
- **R-TYPEORM-TX-3.** Read-методы (запросы) — без транзакции/без записи; запись — только через Handler-границу.

**MUST NOT:**
- **R-TYPEORM-TX-X1.** `queryRunner.commitTransaction()`/`startTransaction()` внутри репозитория — граница TX на Handler.
- **R-TYPEORM-TX-X2.** Несколько последовательных `save()` без общей транзакции в одной бизнес-операции — частичная запись при сбое.

## 5. Запросы
**MUST:**
- **R-TYPEORM-QRY-1.** Запросы — через `Repository<T>.find*` с явным `relations: [...]` или QueryBuilder с явным `leftJoinAndSelect`; нужные связи перечисляются явно — против N+1.
- **R-TYPEORM-QRY-2.** Update существующего агрегата — load → мутация домена → `save(toEntity(...))` полного агрегата в транзакции; точечный апдейт полей — `update().set().where()` явно, без `save()` частичного объекта.
- **R-TYPEORM-QRY-3.** Пагинация — `take/skip` (limit/offset) или keyset по `(createdAt, id)`; `count` — отдельным запросом (`getManyAndCount` ок для offset-страниц), не `(await find()).length`.
- **R-TYPEORM-QRY-4.** Read-проекции (CQRS-запрос) — отдельный `TypeOrm<X>ViewRepository`: raw `select` (`getRawMany` / `dataSource.query` с bind-параметрами) в read-DTO, не полный агрегат (cross-ref `R-CQRS-4`, `R-JOOQ-VIEW-*`).
- **R-TYPEORM-QRY-5.** Bind-параметры — именованные (`where('o.status = :status', { status })`), не интерполяция в строку.

**MUST NOT:**
- **R-TYPEORM-QRY-X1.** Lazy relations (`Promise<Ticket[]>` в Entity) — скрытые запросы из маппера/сериализатора, N+1.
- **R-TYPEORM-QRY-X2.** `save()` объекта с подмножеством полей без предварительного load — TypeORM делает partial update молча, затирая/пропуская поля непредсказуемо.
- **R-TYPEORM-QRY-X3.** `find()` без `take` на больших таблицах.
- **R-TYPEORM-QRY-X4.** Сырой SQL с конкатенацией (`query(\`... ${x}\`)`) — SQL-injection; только bind-параметры.

## 6. Миграции
**MUST:**
- **R-TYPEORM-MIG-1.** Схема — только через миграции: `typeorm migration:generate` + **обязательная вычитка руками** (generate не ловит всё: переименования видит как drop+create, типы/индексы). Запуск — `migration:run` отдельной командой (cross-ref `NESTBOOT-9`).
- **R-TYPEORM-MIG-2.** Безопасность миграций (expand-contract, CONCURRENTLY, lock_timeout) — по `pg-migrations-rules.md` (`PG-M-*`, язык-нейтральны).

**MUST NOT:**
- **R-TYPEORM-MIG-X1.** `synchronize: true` где-либо кроме одноразовых unit-тестов без миграций — в проде запрещён (cross-ref `NESTBOOT-X4`).
- **R-TYPEORM-MIG-X2.** Править применённую миграцию — добавлять новую.
