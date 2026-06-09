# SQLAlchemy — индекс правил (Python persistence)

> **Что это.** Persistence-слой на async SQLAlchemy 2.0 + Alembic по UCP. Языко-специфичный concern (аналог
> Java `jooq` / `R-JOOQ-*`) — **только Python**, префикс `R-SQLA-*`. Скиллы читают этот файл; код-примеры включены.
> Коды: `R-SQLA-<N>` — обязательно, `R-SQLA-X<N>` — антипаттерн (запрещено).
> PostgreSQL-правила (типы/индексы/миграции/runtime) — язык-нейтральны, см. `pg-*-rules.md`.

Суть: репозиторий реализует **порт из `core/`**, принимает/возвращает **доменные объекты** (не ORM-модели); ORM-модель — деталь persistence; граница транзакции — на Handler через Unit of Work; async-сессия per-request.

## 1. Repository-pattern
**MUST:**
- **R-SQLA-REPO-1.** Доменный порт — `Protocol` в `core/<bc>/port/`; реализация — `SqlAlchemy<X>Repository` в `adapters/out/persistence/`.
- **R-SQLA-REPO-2.** Public-методы принимают/возвращают **доменные объекты** (Aggregate/VO/read-DTO), не ORM-модели и не `Row` (cross-ref `R-LAY-2`).
- **R-SQLA-REPO-3.** `AsyncSession` инжектится (через DI/UoW), не создаётся внутри репозитория.
- **R-SQLA-REPO-4.** Каждый репозиторий покрыт интеграционным тестом против Testcontainers Postgres, без моков сессии (cross-ref test-strategy).

**MUST NOT:**
- **R-SQLA-REPO-X1.** Возврат ORM-модели наружу из репозитория — ORM-модель внутренняя.
- **R-SQLA-REPO-X2.** Бизнес-логика в репозитории (`if order.status == ...`).
- **R-SQLA-REPO-X3.** Прямой `AsyncSession`/`select(...)` в `core/` (домен/хендлер) — только через порт (cross-ref `R-HEX-X1`).

## 2. ORM-модели
**MUST:**
- **R-SQLA-MODEL-1.** ORM-модели (`DeclarativeBase` + `Mapped`/`mapped_column`) живут в `adapters/out/persistence/`, не в `core/`.
- **R-SQLA-MODEL-2.** Типы: деньги — `Numeric(p, s)` → `Decimal` (не `Float`); время — `DateTime(timezone=True)` → aware `datetime`; UUID — `UUID(as_uuid=True)` (cross-ref `pg-types` `PG-T-013/030/040`).
- **R-SQLA-MODEL-3.** ORM-модель ≠ доменный объект ≠ Pydantic-DTO — три разных типа (cross-ref `R-LAY-X1`).

**MUST NOT:**
- **R-SQLA-MODEL-X1.** Доменная логика/инварианты на ORM-модели — она анемичная persistence-структура; инварианты — в доменном агрегате.

## 3. Маппинг ORM ↔ domain
**MUST:**
- **R-SQLA-MAP-1.** Явный маппер (функции/класс) `to_domain(model) -> Aggregate` и `to_model(aggregate) -> Model`, рядом с репозиторием.
- **R-SQLA-MAP-2.** Сборка агрегата из строк — в маппере, не размазана по репозиторию.

**MUST NOT:**
- **R-SQLA-MAP-X1.** «Универсальный» маппинг через `__dict__`/`vars()`; ORM-модель напрямую как domain.

## 4. Сессия и транзакции
**MUST:**
- **R-SQLA-SESS-1.** Граница транзакции — на Handler через Unit of Work (`async with uow: ... await uow.commit()`), не в репозитории (cross-ref `R-TX-1`).
- **R-SQLA-SESS-2.** Async-сессия per-request (через `Depends`/контейнер); не глобальная, не на уровне модуля (cross-ref `PYBOOT-X2`).
- **R-SQLA-SESS-3.** Read-методы (запросы) — read-only сессия/без `commit`; запись — через UoW команды.

**MUST NOT:**
- **R-SQLA-SESS-X1.** `commit()`/`rollback()` внутри репозитория — граница TX на Handler.
- **R-SQLA-SESS-X2.** `session.expire_on_commit=True` + использование ORM-объекта после commit в async — `MissingGreenlet`/detached; маппи в домен до commit.

## 5. Запросы
**MUST:**
- **R-SQLA-QRY-1.** SQLAlchemy 2.0-style: `select(...)` + `await session.execute(...)`, не legacy `session.query(...)`.
- **R-SQLA-QRY-2.** Eager-load связей под доступ — `selectinload`/`joinedload`, чтобы избежать N+1; в async ленивая загрузка не работает — `lazy="raise"` на relationship по умолчанию.
- **R-SQLA-QRY-3.** Bulk-вставка — `session.execute(insert(...), rows)` / `add_all`, не цикл с `add`+`flush` (cross-ref `pg-runtime` `PG-W-010`).
- **R-SQLA-QRY-4.** Пагинация — `limit/offset` или keyset; `count(*)` отдельным запросом, не `len(all())`.
- **R-SQLA-QRY-5.** Read-проекции (CQRS-запрос) — отдельный `<X>ViewRepository`, возвращает read-DTO (`model_validate`), не полный агрегат (cross-ref `R-CQRS-4`).

**MUST NOT:**
- **R-SQLA-QRY-X1.** `session.query(...)` (legacy 1.x style) в новом коде.
- **R-SQLA-QRY-X2.** Ленивая загрузка связей в async (`lazy="select"` по умолчанию) — N+1 / `MissingGreenlet`. Явный eager-load или `lazy="raise"`.
- **R-SQLA-QRY-X3.** `fetchall()` без `LIMIT` на больших таблицах.
- **R-SQLA-QRY-X4.** Сырой SQL строками с конкатенацией (`text(f"... {x}")`) — SQL-injection; параметры через bind (`text("... :x").bindparams(...)` / Core-выражения).

## 6. Миграции (Alembic)
**MUST:**
- **R-SQLA-MIG-1.** Схема — через **Alembic** (`alembic revision --autogenerate` + ручная ревизия diff), не `Base.metadata.create_all()` в проде (cross-ref `PYBOOT-X4`).
- **R-SQLA-MIG-2.** Безопасность миграций (expand-contract, CONCURRENTLY, lock_timeout) — по `pg-migrations-rules.md` (`PG-M-*`, язык-нейтральны).
- **R-SQLA-MIG-3.** Autogenerate-ревизию всегда вычитывать руками (Alembic не ловит всё: тип-changes, индексы).

**MUST NOT:**
- **R-SQLA-MIG-X1.** Править применённую ревизию — добавлять новую.
