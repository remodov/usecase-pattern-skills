---
name: ucp-py-ddd-tactical-review
lang: python
description: Ревью доменного кода на чистом Python (core/) по UCP DDD Tactical Patterns (коды R-ENT/VO/AGG/EVT/REP-*) — Entity с identity-equality, frozen VO, события в корне агрегата, порт-Protocol, деньги Decimal, core/ без фреймворка.
when_to_use: Ревью агрегатов, VO, доменных событий, портов-репозиториев в core/ Python-сервиса.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тактических паттернов DDD (Python / чистый core)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md` (`R-*`)
и **Python-реализации** `backend/ddd-tactical/python/ddd-tactical-style-guide.md`. Домен в `core/` — чистый Python без фреймворка.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/python/ddd-tactical-style-guide.md`** — Python-идиомы (frozen dataclass, identity-Entity, import-linter).
- Парные: `backend/usecase-pattern/python/...` (граница TX/UoW/события), `backend/python/sqlalchemy/sqlalchemy-rules.md` (реализация репозитория).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй конкретные коды (`R-AGG-X4`, `R-VO-X3`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,value_object,event,port,service,specification}/**`, `core/shared/building_blocks.py`, `git diff` на `.py` в `core/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** наследует `Entity[ID]`; id неизменяем (`@property`, без сеттера); `__eq__`/`__hash__` не переопределены в наследнике; состояние меняется бизнес-методами, не сеттерами; ссылки на другие агрегаты по id. `@dataclass(eq=True)` на Entity (equality по всем полям) → `R-ENT-X2`. Публичные сеттеры на всё → `R-ENT-X3`. Анемичная модель → `R-ENT-X5`. Ссылка-объект на чужой агрегат → `R-ENT-X4`.
   - **Value Object (`R-VO-*`):** `@dataclass(frozen=True)`; инварианты в `__post_init__`; мутация возвращает новый экземпляр; коллекции `tuple`/`frozenset`. VO с id/жизненным циклом → `R-VO-X1`. Primitive obsession (`str`/`Decimal` вместо `Email`/`Money`) → `R-VO-X2`. `list`/`set`/`dict` внутри frozen-VO → `R-VO-X3` (unhashable + мутируемое содержимое). Деньги `float` → нарушение (Decimal обязателен).
   - **Aggregate Root (`R-AGG-*`):** наследует `AggregateRoot[ID]`; события через `self._register_event(...)` в корне; наружу — копии/view (`tuple(...)`); один use case = один агрегат; ссылки по id. Регистрация события вне корня → `R-AGG-X4`. Возврат внутренней `list` наружу → `R-AGG-X2`. God aggregate → `R-AGG-X1`.
   - **Domain Event (`R-EVT-*`):** `@dataclass(frozen=True)`, наследует `DomainEvent`; имя в прошедшем времени (`OrderConfirmed`); только примитивы/VO; публикация после сохранения + `pull_events()`. Ссылка на агрегат/Entity в событии → `R-EVT-X2`. Публикация из Handler/контроллера → `R-EVT-X3`. After-commit фоном для критичных эффектов → `R-EVT-X4` (Outbox).
   - **Repository (`R-REP-*`):** порт — `Protocol` в `core/<bc>/port/`, методы в доменных терминах, возвращает домен; реализация в `adapters/out/`. Возврат ORM/`Row` наружу → `R-REP-X1` (cross-ref `R-SQLA-REPO-X1`). Методы под одну таблицу → `R-REP-X2`. SQL-Specification в репозитории → `R-REP-X3`.
   - **Domain Service (`R-DS-*`):** только для логики на ≥2 агрегатах, stateless, доменные объекты. Оркестрация (репозиторий/TX/публикация) в Domain Service → `R-DS-X1`. Свалка-сервис при анемичных агрегатах → `R-DS-X2`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory только когда конструктора мало, возвращает валидный агрегат с начальными событиями (`R-FAC-X1` — Factory ради Factory). Specification только при переиспользовании/композиции, не для SQL (`R-SPEC-X1`/`X2`).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (нет корневых `entity/`/`service/`/`repository/`); `core/` не импортирует FastAPI/SQLAlchemy/Pydantic/`adapters/*`. Фреймворк в `core/` → `R-MOD-2` (проверь `import-linter`-контракт).

4. **Cross-check:** граница TX/UoW и публикация событий — `ucp-py-pattern-review` (`R-TX-3`); реализация репозитория — `ucp-py-sqlalchemy-review`; типы колонок — `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — мутабельный VO / `list` в frozen-VO (`R-VO-X3`), события вне корня (`R-AGG-X4`), equality по полям на Entity (`R-ENT-X2`), ссылка-объект между агрегатами (`R-ENT-X4`), фреймворк в `core/` (`R-MOD-2`), ссылка на агрегат в событии (`R-EVT-X2`), деньги `float`.
   - **Предупреждение** — анемичная модель (`R-ENT-X5`), публичные сеттеры (`R-ENT-X3`), порт-репозиторий вне домена (`R-REP-1`), after-commit для критичных эффектов (`R-EVT-X4`), возврат внутренней коллекции (`R-AGG-X2`).
   - **Замечание** — primitive obsession (`R-VO-X2`), Factory/Specification ради абстракции (`R-FAC-X1`/`R-SPEC-X2`), нейминг события не в прошедшем времени (`R-EVT-2`).

## Что не входит

- Граница транзакции/UoW и бизнес-операции — `ucp-py-pattern-review`. Реализация репозитория — `ucp-py-sqlalchemy-review`.
- Валидация входа (Pydantic) — `ucp-py-validation-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
