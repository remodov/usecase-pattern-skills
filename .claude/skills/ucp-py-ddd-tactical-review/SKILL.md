---
name: ucp-py-ddd-tactical-review
lang: python
description: Ревью доменного кода на чистом Python (core/) по UCP DDD Tactical Patterns (требования ddd-tactical/*) — Entity с identity-equality, frozen VO, события в корне агрегата, порт-Protocol, деньги Decimal, core/ без фреймворка.
when_to_use: Ревью агрегатов, VO, доменных событий, портов-репозиториев в core/ Python-сервиса.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тактических паттернов DDD (Python / чистый core)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/spec.md` (`R-*`)
и **Python-реализации** `backend/ddd-tactical/references/python/implementation.md`. Домен в `core/` — чистый Python без фреймворка.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/spec.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/references/python/implementation.md`** — Python-идиомы (frozen dataclass, identity-Entity, import-linter).
- Парные: `backend/usecase-pattern/python/...` (граница TX/UoW/события), `backend/python/sqlalchemy/spec.md` (реализация репозитория).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй конкретные коды (`ddd-tactical/events-registered-by-root`, `ddd-tactical/collections-in-values-are-protected`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,value_object,event,port,service,specification}/**`, `core/shared/building_blocks.py`, `git diff` на `.py` в `core/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** наследует `Entity[ID]`; id неизменяем (`@property`, без сеттера); `__eq__`/`__hash__` не переопределены в наследнике; состояние меняется бизнес-методами, не сеттерами; ссылки на другие агрегаты по id. `@dataclass(eq=True)` на Entity (equality по всем полям) → `ddd-tactical/entity-equality-by-identity`. Публичные сеттеры на всё → `ddd-tactical/entity-constructor-validates`. Анемичная модель → `ddd-tactical/model-is-not-anemic`. Ссылка-объект на чужой агрегат → `ddd-tactical/no-object-references-across-aggregates`.
   - **Value Object (`R-VO-*`):** `@dataclass(frozen=True)`; инварианты в `__post_init__`; мутация возвращает новый экземпляр; коллекции `tuple`/`frozenset`. VO с id/жизненным циклом → `ddd-tactical/value-has-no-identity`. Primitive obsession (`str`/`Decimal` вместо `Email`/`Money`) → `ddd-tactical/no-primitive-obsession`. `list`/`set`/`dict` внутри frozen-VO → `ddd-tactical/collections-in-values-are-protected` (unhashable + мутируемое содержимое). Деньги `float` → нарушение (Decimal обязателен).
   - **Aggregate Root (`R-AGG-*`):** наследует `AggregateRoot[ID]`; события через `self._register_event(...)` в корне; наружу — копии/view (`tuple(...)`); один use case = один агрегат; ссылки по id. Регистрация события вне корня → `ddd-tactical/events-registered-by-root`. Возврат внутренней `list` наружу → `ddd-tactical/aggregate-root-is-single-entry`. God aggregate → `ddd-tactical/aggregate-stays-small`.
   - **Domain Event (`R-EVT-*`):** `@dataclass(frozen=True)`, наследует `DomainEvent`; имя в прошедшем времени (`OrderConfirmed`); только примитивы/VO; публикация после сохранения + `pull_events()`. Ссылка на агрегат/Entity в событии → `ddd-tactical/event-carries-business-context`. Публикация из Handler/контроллера → `ddd-tactical/events-published-after-save`. After-commit фоном для критичных эффектов → `ddd-tactical/no-after-commit-for-critical-effects` (Outbox).
   - **Repository (`R-REP-*`):** порт — `Protocol` в `core/<bc>/port/`, методы в доменных терминах, возвращает домен; реализация в `adapters/out/`. Возврат ORM/`Row` наружу → `ddd-tactical/repository-speaks-domain` (cross-ref `sqlalchemy/repository-speaks-domain-types`). Методы под одну таблицу → `ddd-tactical/repository-speaks-domain`. SQL-Specification в репозитории → `ddd-tactical/specification-is-not-a-query-builder`.
   - **Domain Service (`R-DS-*`):** только для логики на ≥2 агрегатах, stateless, доменные объекты. Оркестрация (репозиторий/TX/публикация) в Domain Service → `ddd-tactical/domain-service-only-across-aggregates`. Свалка-сервис при анемичных агрегатах → `ddd-tactical/domain-service-only-across-aggregates`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory только когда конструктора мало, возвращает валидный агрегат с начальными событиями (`ddd-tactical/factory-only-when-needed` — Factory ради Factory). Specification только при переиспользовании/композиции, не для SQL (`ddd-tactical/specification-is-not-a-query-builder`/`X2`).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (нет корневых `entity/`/`service/`/`repository/`); `core/` не импортирует FastAPI/SQLAlchemy/Pydantic/`adapters/*`. Фреймворк в `core/` → `ddd-tactical/packages-grouped-by-domain` (проверь `import-linter`-контракт).

4. **Cross-check:** граница TX/UoW и публикация событий — `ucp-py-pattern-review` (`usecase-pattern/publish-events-after-save`); реализация репозитория — `ucp-py-sqlalchemy-review`; типы колонок — `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — мутабельный VO / `list` в frozen-VO (`ddd-tactical/collections-in-values-are-protected`), события вне корня (`ddd-tactical/events-registered-by-root`), equality по полям на Entity (`ddd-tactical/entity-equality-by-identity`), ссылка-объект между агрегатами (`ddd-tactical/no-object-references-across-aggregates`), фреймворк в `core/` (`ddd-tactical/packages-grouped-by-domain`), ссылка на агрегат в событии (`ddd-tactical/event-carries-business-context`), деньги `float`.
   - **Предупреждение** — анемичная модель (`ddd-tactical/model-is-not-anemic`), публичные сеттеры (`ddd-tactical/entity-constructor-validates`), порт-репозиторий вне домена (`ddd-tactical/repository-port-in-domain`), after-commit для критичных эффектов (`ddd-tactical/no-after-commit-for-critical-effects`), возврат внутренней коллекции (`ddd-tactical/aggregate-root-is-single-entry`).
   - **Замечание** — primitive obsession (`ddd-tactical/no-primitive-obsession`), Factory/Specification ради абстракции (`ddd-tactical/factory-only-when-needed`/`ddd-tactical/specification-for-reuse`), нейминг события не в прошедшем времени (`ddd-tactical/event-named-in-past-tense`).

## Что не входит

- Граница транзакции/UoW и бизнес-операции — `ucp-py-pattern-review`. Реализация репозитория — `ucp-py-sqlalchemy-review`.
- Валидация входа (Pydantic) — `ucp-py-validation-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
