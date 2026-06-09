---
name: ucp-py-ddd-tactical-design
lang: python
description: Спроектировать доменную модель на чистом Python в core/ по UCP DDD Tactical Patterns (коды R-ENT/VO/AGG/EVT/REP-*) — Entity, VO как frozen dataclass, AggregateRoot с событиями, DomainEvent, порт-Protocol, деньги Decimal, без фреймворка.
when_to_use: Триггеры — «агрегат X на питоне», «доменная модель для Y», «value object Money». При моделировании BC или агрегата на Уровне 3.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# DDD Tactical Patterns — проектирование (Python / чистый core)

Ты проектируешь доменную модель согласно **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md`
(`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`) и его **Python-реализации** `backend/ddd-tactical/python/ddd-tactical-style-guide.md`.
Домен живёт в `core/` **без фреймворка** (ни FastAPI, ни SQLAlchemy, ни Pydantic) — чистый Python + stdlib.

## Инструкции

1. **Прочитай** контракт `backend/ddd-tactical/ddd-tactical-rules.md` + Python-style-guide `backend/ddd-tactical/python/ddd-tactical-style-guide.md`. Коды `R-*` обязательны; цитируй их в **design-обосновании**, не в комментариях кода. Связанные: `backend/usecase-pattern/python/...` (Handler/UoW/порты), `backend/python/sqlalchemy/sqlalchemy-rules.md` (реализация репозитория).

2. **Базовые типы.** Если в `core/shared/building_blocks.py` нет `Entity`/`AggregateRoot`/`DomainEvent` — создай тонкие ручные (в Python нет `ddd-building-blocks`); образец — в style-guide. Не тащи их из adapter-слоя.

3. **Уточни модель:** Bounded Context и пакет (`core/<bc>/`); корень агрегата и защищаемый инвариант; внутренние Entity; Value Objects (бьём primitive obsession — `Money`/`Email`/`OrderId`); доменные события (прошедшее время); ссылки на другие агрегаты — по id; оправданы ли Factory/Domain Service/Specification (по умолчанию нет).

4. **Произведи код** (Python 3.12+, тайп-хинты; без комментариев; коды правил не цитируй):
   - **Value Object** — `@dataclass(frozen=True)`, инварианты в `__post_init__`, мутация → новый экземпляр (`replace`); коллекции `tuple`/`frozenset` (`R-VO-*`). Деньги — `Decimal`.
   - **Entity** — обычный класс, наследует `Entity[ID]`, id неизменяем, бизнес-методы (без сеттеров), `__eq__`/`__hash__` не переопределять (`R-ENT-*`). **Не** делать Entity через `@dataclass(eq=True)` — это VO-семантика.
   - **Aggregate Root** — наследует `AggregateRoot[ID]`, мутирующие методы держат инварианты и зовут `self._register_event(...)`; наружу — копии/view (`tuple(...)`) (`R-AGG-*`).
   - **Domain Event** — `@dataclass(frozen=True)`, наследует `DomainEvent`, имя в прошедшем времени, только примитивы/VO (`R-EVT-*`).
   - **Repository** — `Protocol` в `core/<bc>/port/`, методы в доменных терминах, возвращает домен (`R-REP-*`); реализация — отдельно через `ucp-py-sqlalchemy-design`.
   - **Domain Service / Factory / Specification** — только если оправдано; укажи обоснование.

5. **Раскладка по домену** (`R-MOD-*`): `core/<bc>/{aggregate,entity,value_object,event,port,service,specification,usecase}/`. `core/` не импортирует фреймворк — предложи контракт `import-linter` (`R-HEX-2`).

6. **Самопроверка** (чек-лист §10 style-guide) + предложи `ucp-py-ddd-tactical-review`. Persistence агрегата — `ucp-py-sqlalchemy-design`.

## Антипаттерны, которые НЕ генерировать

- Entity как `@dataclass` с equality по всем полям (`R-ENT-X2`); публичные сеттеры на всё (`R-ENT-X3`); анемичная модель (`R-ENT-X5`).
- VO с id/жизненным циклом (`R-VO-X1`); primitive obsession (`R-VO-X2`); `list`/`set` внутри frozen-VO (`R-VO-X3`); деньги `float`.
- Регистрация события вне корня (`R-AGG-X4`); возврат мутабельной коллекции наружу (`R-AGG-X2`); ссылка на агрегат объектом (`R-ENT-X4`/`R-AGG-5`).
- Событие со ссылкой на агрегат (`R-EVT-X2`); фреймворк в `core/` (`R-MOD-2`); порт-репозиторий вне домена (`R-REP-1`).

После работы скилла — обязательно `ucp-py-ddd-tactical-review`.

$ARGUMENTS
