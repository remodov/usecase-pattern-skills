---
name: ucp-py-pattern-design
lang: python
description: Спроектировать бизнес-операцию как UseCase + Handler в FastAPI-сервисе на Python (требования usecase-pattern/*) — frozen-dataclass UseCase, stateless Handler с UoW, Dispatcher-реестр, тонкий роутер, порты-Protocol, разделение слоёв DTO/домен/ORM.
when_to_use: Триггеры — «добавь команду X в FastAPI», «новый UseCase на питоне», «эндпоинт создания Y». При новом эндпоинте/команде/запросе.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Проектирование UseCase + Handler (Python / FastAPI)

Ты проектируешь бизнес-операцию как **UseCase + Handler** согласно **общему контракту**
`backend/usecase-pattern/spec.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-TX-*`)
и его **Python-реализации** `backend/usecase-pattern/references/python/implementation.md` (FastAPI + frozen-dataclass + dispatcher-реестр; роль java-библиотеки `usecase-pattern` играют лёгкие протоколы).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/usecase-pattern/spec.md` — общий контракт, коды `R-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/usecase-pattern/references/python/implementation.md` — Python-реализация (протоколы `Command`/`Query`/`Handler`, `Dispatcher`, UoW, тонкий роутер), открывай точечно.
   - На Уровне 3 — `.claude/docs/backend/ddd-tactical/spec.md` (домен).
   - Если есть новая таблица — `.claude/docs/backend/pg-types/spec.md` (типы; PostgreSQL-правила язык-нейтральны).

2. **Идентифицируй сервис и слой.** Структура UCP на Python: `core/<bc>/` (usecases, handlers, domain, port/), `adapters/in/http/` (роутеры), `adapters/out/` (репозитории), `app/` (DI + dispatcher).

3. **Спроектируй операцию.** Для команды/запроса определи: имя (бизнес-операция), вход (поля), результат `R`, командой или запросом.

4. **Произведи код** (полные `.py`; Python 3.11+, тайп-хинты; без комментариев — соответствие через имена/типы/структуру; коды правил НЕ цитируй в коде).

   ### 4.1 UseCase — `@dataclass(frozen=True)`
   Имя-операция; поля — вход; без логики (`R-UC-1..4`). Команда / запрос по смыслу (`R-CQRS-1/3`).

   ### 4.2 Handler — класс с `async def handle(uc) -> R`
   Deps через `__init__` (репозитории, UoW, clock, порты); граница транзакции на Handler через `async with self._uow` для команды (read-write), read-only для запроса (`usecase-pattern/transaction-boundary-on-handler`, `usecase-pattern/transaction-boundary-on-handler`). Один Handler — один UseCase (`usecase-pattern/one-handler-one-usecase`). Инфра-ошибки → доменные (`usecase-pattern/infrastructure-errors-become-domain`).

   ### 4.3 Регистрация в DI + Dispatcher
   Handler — в DI-контейнере (dependency-injector/punq); добавить в реестр `type→handler`, который собирает `Dispatcher` (`usecase-pattern/handler-registered-in-container`, `R-DSP-1/2`).

   ### 4.4 Тонкий FastAPI-роутер
   Pydantic-Request → UseCase (`user_id` из principal, не из Request — `usecase-pattern/no-transport-objects-in-usecase`) → `dispatcher.dispatch(uc)` → Pydantic-Response + HTTP-код. Без логики/БД в endpoint (`usecase-pattern/controller-maps-and-dispatches`, `usecase-pattern/controller-maps-and-dispatches`).

   ### 4.5 Слои и порты
   Pydantic-DTO на edge ≠ домен ≠ SQLAlchemy-модель; явный маппинг (`R-LAY-1/2/3`). Внешнее — за `Protocol`-портом в `core/<bc>/port/`; `core/` без FastAPI/SQLAlchemy (`R-HEX-2/3`).

5. **Самопроверка** — чеклист из `python/implementation.md`.

6. **Финальный шаг:** предложи «запусти `ucp-py-pattern-review`», а для обработки ошибок — `ucp-py-error-handling-design`.

## Антипаттерны, которые НЕ генерировать

- Логика в UseCase / mutable-dataclass (`usecase-pattern/usecase-is-immutable-carrier`/`X3`).
- Handler зовёт Handler напрямую (`usecase-pattern/handlers-do-not-call-handlers`); endpoint с БД/логикой (`usecase-pattern/controller-maps-and-dispatches`); `Request`/`Principal` в UseCase (`usecase-pattern/no-transport-objects-in-usecase`).
- SQLAlchemy-модель в JSON-ответе / один класс на API и БД (`usecase-pattern/layer-models-do-not-leak`).
- `import sqlalchemy`/`from fastapi` в `core/` (`hexagonal/core-free-of-framework`); прямой `AsyncSession` в core (`hexagonal/outbound-port-interface-in-core`).
- `@Transactional`-аналог на репозитории вместо Handler (`usecase-pattern/transaction-boundary-on-handler`).

После работы скилла — обязательно `ucp-py-pattern-review` для верификации.

$ARGUMENTS
