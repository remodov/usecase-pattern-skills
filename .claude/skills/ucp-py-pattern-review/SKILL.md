---
name: ucp-py-pattern-review
lang: python
description: Ревью UseCase + Handler в Python/FastAPI-сервисе по UCP (требования usecase-pattern/*) — frozen-dataclass UseCase, stateless Handler с UoW, Dispatcher, тонкий роутер, порты-Protocol в core/, разделение DTO/домен/ORM.
when_to_use: Изменения в usecases.py, handlers.py, роутерах, app/dispatcher или портах core/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью UseCase + Handler (Python / FastAPI)

Ты ревьюишь FastAPI-сервис на соответствие **общему контракту** `backend/usecase-pattern/spec.md`
(`R-*`, коды едины с Java) и его **Python-реализации** `backend/usecase-pattern/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/spec.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/references/python/implementation.md`** — Python-реализация.
- Парные: `backend/error-handling/spec.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/spec.md`, `backend/pg-types/spec.md`.

## Инструкции

1. **Прочти** контракт и `references/python/implementation.md` (реализация). Цитируй конкретные коды (`usecase-pattern/infrastructure-errors-become-domain`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/usecases.py`, `**/*usecase*.py` — `R-UC-*`.
   - `**/handlers.py`, `**/*handler*.py` — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**`, `**/*router*.py` — `R-DSP-*`.
   - `app/**dispatcher*.py`, DI-контейнер — `R-DSP-1/2`.
   - `core/**/port/**` — `hexagonal/outbound-port-interface-in-core`.
   - `git diff` на изменённые `.py`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — `@dataclass(frozen=True)`, без логики, имя-операция? — `R-UC-1/2/3`. Mutable/сеттеры → `usecase-pattern/usecase-is-immutable-carrier`. Логика в UseCase → `usecase-pattern/usecase-is-immutable-carrier`. Один dataclass на 2 операции → `usecase-pattern/one-usecase-one-operation`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — класс с `async def handle`, один UseCase, deps через `__init__`, приватные поля? — `R-HND-1/4/5`.
   - Граница транзакции на Handler (`async with uow` для команды, read-only для запроса), не на репозитории? — `usecase-pattern/transaction-boundary-on-handler`, `usecase-pattern/transaction-boundary-on-handler`.
   - Handler зовёт другой Handler напрямую — `usecase-pattern/handlers-do-not-call-handlers`.
   - Наружу летит `sqlalchemy.exc.*`/`httpx`-ошибка (не мапится в доменную) — `usecase-pattern/infrastructure-errors-become-domain` (cross-ref `R-ERR-WHERE-2b`).
   - State между вызовами — `usecase-pattern/handler-is-stateless`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.dispatch(uc)`, не Handler напрямую? — `usecase-pattern/entry-calls-dispatcher`.
   - Endpoint тонкий (Request→UseCase, dispatch, Response, код)? Логика/БД в endpoint → `usecase-pattern/controller-maps-and-dispatches`.
   - `Request`/`Principal`/`Depends`-объекты протекают в UseCase вместо `user_id`/`tenant_id` — `usecase-pattern/no-transport-objects-in-usecase`.

   ### `R-CQRS-*`
   - Команда — глагол + read-write UoW; запрос — `Find/Get/Search` + read-only + ViewRepository? — `R-CQRS-1/2/3/4`.
   - Команда возвращает тяжёлый read-DTO — `usecase-pattern/command-returns-minimum`. Запрос пишет (last-seen/counter) — `usecase-pattern/query-does-not-mutate`.

   ### `R-LAY-*`
   - Pydantic-DTO на edge, домен в core, SQLAlchemy-модель в persistence; явный маппинг? — `R-LAY-1/2/3`.
   - SQLAlchemy-модель уходит в JSON-ответ / один класс на API и БД — `usecase-pattern/layer-models-do-not-leak`.
   - `dict(**vars(obj))`/`__dict__`-копирование как маппер — `usecase-pattern/explicit-mapper-between-layers`.
   - Доменный объект (Aggregate/VO) в API-ответе — `usecase-pattern/layer-models-do-not-leak`.

   ### `R-HEX-*`
   - Порты — `Protocol` в `core/<bc>/port/`; `core/` без `import fastapi`/`import sqlalchemy`/`httpx`? — `R-HEX-2/3`. Нарушение импорта → `hexagonal/core-free-of-framework`; `AsyncSession` в core → `hexagonal/outbound-port-interface-in-core`. (Рекомендуй `import-linter`.)

4. **Cross-check:** инфра→домен в адаптере → `ucp-py-error-handling-review` (`R-ERR-WHERE-2b`); DDL → `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — логика в UseCase (`usecase-pattern/usecase-is-immutable-carrier`), Handler→Handler (`usecase-pattern/handlers-do-not-call-handlers`), endpoint с БД/логикой (`usecase-pattern/controller-maps-and-dispatches`), `core/` импортит фреймворк/ORM (`hexagonal/core-free-of-framework`), TX на репозитории (`usecase-pattern/transaction-boundary-on-handler`), SQLAlchemy-модель в ответе (`usecase-pattern/layer-models-do-not-leak`).
   - **Предупреждение** — mutable UseCase (`usecase-pattern/usecase-is-immutable-carrier`), `Request` в UseCase (`usecase-pattern/no-transport-objects-in-usecase`), запрос пишет (`usecase-pattern/query-does-not-mutate`), `__dict__`-маппинг (`usecase-pattern/explicit-mapper-between-layers`).
   - **Замечание** — нет явного read-DTO для запроса, Step-кандидат не выделен, имя не выражает операцию.

## Что не входит

- Обработка ошибок (иерархия, problem+json) — `ucp-py-error-handling-review`.
- Валидация входа (Pydantic constraints) — `ucp-py-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-py-ddd-tactical-review`.

$ARGUMENTS
