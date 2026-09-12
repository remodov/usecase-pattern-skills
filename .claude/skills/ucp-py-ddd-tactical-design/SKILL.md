---
name: ucp-py-ddd-tactical-design
lang: python
description: Спроектировать доменную модель на чистом Python в core/ по UCP DDD Tactical Patterns (требования ddd-tactical/*) — Entity, VO как frozen dataclass, AggregateRoot с событиями, DomainEvent, порт-Protocol, деньги Decimal, без фреймворка.
when_to_use: Триггеры — «агрегат X на питоне», «доменная модель для Y», «value object Money». При моделировании BC или агрегата на Уровне 3.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# DDD Tactical Patterns — проектирование (Python / чистый core)

Ты проектируешь доменную модель согласно **общему контракту** `backend/ddd-tactical/spec.md`
(`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`) и его **Python-реализации** `backend/ddd-tactical/references/python/implementation.md`.
Домен живёт в `core/` **без фреймворка** (ни FastAPI, ни SQLAlchemy, ни Pydantic) — чистый Python + stdlib.

## Инструкции

1. **Прочитай** контракт `backend/ddd-tactical/spec.md` + требования `python-style/*` `backend/ddd-tactical/references/python/implementation.md`. Коды `R-*` обязательны; цитируй их в **design-обосновании**, не в комментариях кода. Связанные: `backend/usecase-pattern/python/...` (Handler/UoW/порты), `backend/python/sqlalchemy/spec.md` (реализация репозитория).

2. **Базовые типы.** Если в `core/shared/building_blocks.py` нет `Entity`/`AggregateRoot`/`DomainEvent` — создай тонкие ручные (в Python нет `ddd-building-blocks`); образец — в справочнике реализации. Не тащи их из adapter-слоя.

3. **Уточни модель:** Bounded Context и пакет (`core/<bc>/`); корень агрегата и защищаемый инвариант; внутренние Entity; Value Objects (бьём primitive obsession — `Money`/`Email`/`OrderId`); доменные события (прошедшее время); ссылки на другие агрегаты — по id; оправданы ли Factory/Domain Service/Specification (по умолчанию нет).

4. **Произведи код** (Python 3.12+, тайп-хинты; без комментариев; коды правил не цитируй):
   - **Value Object** — `@dataclass(frozen=True)`, инварианты в `__post_init__`, мутация → новый экземпляр (`replace`); коллекции `tuple`/`frozenset` (`R-VO-*`). Деньги — `Decimal`.
   - **Entity** — обычный класс, наследует `Entity[ID]`, id неизменяем, бизнес-методы (без сеттеров), `__eq__`/`__hash__` не переопределять (`R-ENT-*`). **Не** делать Entity через `@dataclass(eq=True)` — это VO-семантика.
   - **Aggregate Root** — наследует `AggregateRoot[ID]`, мутирующие методы держат инварианты и зовут `self._register_event(...)`; наружу — копии/view (`tuple(...)`) (`R-AGG-*`).
   - **Domain Event** — `@dataclass(frozen=True)`, наследует `DomainEvent`, имя в прошедшем времени, только примитивы/VO (`R-EVT-*`).
   - **Repository** — `Protocol` в `core/<bc>/port/`, методы в доменных терминах, возвращает домен (`R-REP-*`); реализация — отдельно через `ucp-py-sqlalchemy-design`.
   - **Domain Service / Factory / Specification** — только если оправдано; укажи обоснование.

5. **Раскладка по домену** (`R-MOD-*`): `core/<bc>/{aggregate,entity,value_object,event,port,service,specification,usecase}/`. `core/` не импортирует фреймворк — предложи контракт `import-linter` (`hexagonal/core-free-of-framework`).

6. **Самопроверка** (чек-лист §10 справочник) + предложи `ucp-py-ddd-tactical-review`. Persistence агрегата — `ucp-py-sqlalchemy-design`.

## Антипаттерны, которые НЕ генерировать

- Entity как `@dataclass` с equality по всем полям (`ddd-tactical/entity-equality-by-identity`); публичные сеттеры на всё (`ddd-tactical/entity-constructor-validates`); анемичная модель (`ddd-tactical/model-is-not-anemic`).
- VO с id/жизненным циклом (`ddd-tactical/value-has-no-identity`); primitive obsession (`ddd-tactical/no-primitive-obsession`); `list`/`set` внутри frozen-VO (`ddd-tactical/collections-in-values-are-protected`); деньги `float`.
- Регистрация события вне корня (`ddd-tactical/events-registered-by-root`); возврат мутабельной коллекции наружу (`ddd-tactical/aggregate-root-is-single-entry`); ссылка на агрегат объектом (`ddd-tactical/no-object-references-across-aggregates`/`ddd-tactical/no-object-references-across-aggregates`).
- Событие со ссылкой на агрегат (`ddd-tactical/event-carries-business-context`); фреймворк в `core/` (`ddd-tactical/packages-grouped-by-domain`); порт-репозиторий вне домена (`ddd-tactical/repository-port-in-domain`).

После работы скилла — обязательно `ucp-py-ddd-tactical-review`.

$ARGUMENTS
