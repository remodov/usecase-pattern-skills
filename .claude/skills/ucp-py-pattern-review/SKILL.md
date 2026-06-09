---
name: ucp-py-pattern-review
lang: python
description: Ревью UseCase + Handler в Python/FastAPI-сервисе по UCP (коды R-UC-*, R-HND-*, R-DSP-*, R-LAY-*) — frozen-dataclass UseCase, stateless Handler с UoW, Dispatcher, тонкий роутер, порты-Protocol в core/, разделение DTO/домен/ORM.
when_to_use: Изменения в usecases.py, handlers.py, роутерах, app/dispatcher или портах core/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью UseCase + Handler (Python / FastAPI)

Ты ревьюишь FastAPI-сервис на соответствие **общему контракту** `backend/usecase-pattern/usecase-pattern-rules.md`
(`R-*`, коды едины с Java) и его **Python-реализации** `backend/usecase-pattern/python/usecase-pattern-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/python/usecase-pattern-style-guide.md`** — Python-реализация.
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/ddd-tactical-rules.md`, `backend/pg-types/pg-types-rules.md`.

## Инструкции

1. **Прочти** контракт (коды) и Python-style-guide (реализация). Цитируй конкретные коды (`R-HND-X2`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/usecases.py`, `**/*usecase*.py` — `R-UC-*`.
   - `**/handlers.py`, `**/*handler*.py` — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**`, `**/*router*.py` — `R-DSP-*`.
   - `app/**dispatcher*.py`, DI-контейнер — `R-DSP-1/2`.
   - `core/**/port/**` — `R-HEX-3`.
   - `git diff` на изменённые `.py`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — `@dataclass(frozen=True)`, без логики, имя-операция? — `R-UC-1/2/3`. Mutable/сеттеры → `R-UC-X3`. Логика в UseCase → `R-UC-X1`. Один dataclass на 2 операции → `R-UC-X2`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — класс с `async def handle`, один UseCase, deps через `__init__`, приватные поля? — `R-HND-1/4/5`.
   - Граница транзакции на Handler (`async with uow` для команды, read-only для запроса), не на репозитории? — `R-HND-3`, `R-TX-1`.
   - Handler зовёт другой Handler напрямую — `R-HND-X1`.
   - Наружу летит `sqlalchemy.exc.*`/`httpx`-ошибка (не мапится в доменную) — `R-HND-X2` (cross-ref `R-ERR-WHERE-2b`).
   - State между вызовами — `R-HND-X3`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.dispatch(uc)`, не Handler напрямую? — `R-DSP-1`.
   - Endpoint тонкий (Request→UseCase, dispatch, Response, код)? Логика/БД в endpoint → `R-DSP-X1`.
   - `Request`/`Principal`/`Depends`-объекты протекают в UseCase вместо `user_id`/`tenant_id` — `R-DSP-X2`.

   ### `R-CQRS-*`
   - Команда — глагол + read-write UoW; запрос — `Find/Get/Search` + read-only + ViewRepository? — `R-CQRS-1/2/3/4`.
   - Команда возвращает тяжёлый read-DTO — `R-CQRS-X1`. Запрос пишет (last-seen/counter) — `R-CQRS-X2`.

   ### `R-LAY-*`
   - Pydantic-DTO на edge, домен в core, SQLAlchemy-модель в persistence; явный маппинг? — `R-LAY-1/2/3`.
   - SQLAlchemy-модель уходит в JSON-ответ / один класс на API и БД — `R-LAY-X1`.
   - `dict(**vars(obj))`/`__dict__`-копирование как маппер — `R-LAY-X3`.
   - Доменный объект (Aggregate/VO) в API-ответе — `R-LAY-DDD`.

   ### `R-HEX-*`
   - Порты — `Protocol` в `core/<bc>/port/`; `core/` без `import fastapi`/`import sqlalchemy`/`httpx`? — `R-HEX-2/3`. Нарушение импорта → `R-HEX-X2`; `AsyncSession` в core → `R-HEX-X1`. (Рекомендуй `import-linter`.)

4. **Cross-check:** инфра→домен в адаптере → `ucp-py-error-handling-review` (`R-ERR-WHERE-2b`); DDL → `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — логика в UseCase (`R-UC-X1`), Handler→Handler (`R-HND-X1`), endpoint с БД/логикой (`R-DSP-X1`), `core/` импортит фреймворк/ORM (`R-HEX-X2`), TX на репозитории (`R-TX-1`), SQLAlchemy-модель в ответе (`R-LAY-X1`).
   - **Предупреждение** — mutable UseCase (`R-UC-X3`), `Request` в UseCase (`R-DSP-X2`), запрос пишет (`R-CQRS-X2`), `__dict__`-маппинг (`R-LAY-X3`).
   - **Замечание** — нет явного read-DTO для запроса, Step-кандидат не выделен, имя не выражает операцию.

## Что не входит

- Обработка ошибок (иерархия, problem+json) — `ucp-py-error-handling-review`.
- Валидация входа (Pydantic constraints) — `ucp-py-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-py-ddd-tactical-review`.

$ARGUMENTS
