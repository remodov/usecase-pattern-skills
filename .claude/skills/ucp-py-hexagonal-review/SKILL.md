---
name: ucp-py-hexagonal-review
lang: python
description: Ревью Hexagonal Architecture Python-сервиса (требования hexagonal/*) — пакеты core/adapters/app, layered-контракт import-linter, core без FastAPI/SQLAlchemy/Pydantic, порты-Protocol в core/<bc>/port, роутеры через Dispatcher, app только композиция.
when_to_use: Ревью раскладки сервиса Уровня 3 — core/, adapters/, app/, конфиг import-linter.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(lint-imports*)
---

# Ревью Hexagonal (Python / пакеты + import-linter)

Ты ревьюишь раскладку сервиса на соответствие **контракту** `backend/hexagonal/spec.md` (`R-HEX-*`) и
**Python-реализации** `backend/hexagonal/references/python/implementation.md`. Изоляция — через `import-linter`.

## Зависимости

- **`.claude/docs/backend/hexagonal/spec.md`** + **`backend/hexagonal/references/python/implementation.md`**.
- Парные: `backend/usecase-pattern/python/...` (`hexagonal/outbound-port-interface-in-core`/Dispatcher), `backend/ddd-tactical/python/...` (rich domain), `backend/python/sqlalchemy/spec.md` (out-persistence).

## Инструкции

0. **Проверь, что гейты, обещанные требованиями, включены.** Поле **Гейт** в `spec.md` называет механизм — убедись, что он есть в проекте: контракты import-linter в `pyproject.toml` (`[tool.importlinter]`) и их прогон в CI. Обещанный, но не включённый гейт — **отдельная находка**, и она важнее отдельного нарушения: без него граница держится только на внимательности.
   Требования с гейтом `ревью` (богатый домен, адаптер мапит а не решает, раздельные in-adapter'ы по аудиториям) не поймает никто, кроме тебя — смотри их внимательнее остальных.

1. **Прочти** требования `python-style/*`. Цитируй коды (`hexagonal/core-free-of-framework`, `hexagonal/adapters-do-not-know-each-other`), не префикс.

2. **Скоп.** `src/<service>/{core,adapters,app}/**`, `pyproject.toml` (`[tool.importlinter]`), CI-конфиг, `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-MOD-*`):** дерево core/adapters/app; контракт import-linter present (`hexagonal/module-per-part` если нет); `core/` не импортит `adapters/*` (`hexagonal/core-free-of-framework`); user/admin разделены (`hexagonal/in-adapter-per-audience`).
   - **Core (`R-HEX-CORE-*`):** без FastAPI (`hexagonal/core-free-of-framework`)/SQLAlchemy (`hexagonal/core-free-of-framework`)/Pydantic-REST-DTO (`hexagonal/no-generated-types-in-core`); ORM-модель не используется как domain (`hexagonal/no-generated-types-in-core`); rich domain, не анемия (`hexagonal/rich-domain-model`).
   - **Ports (`R-HEX-PORT-*`):** `Protocol` в `core/<bc>/port/out/`, domain-типы в сигнатурах; не в out-adapter (`hexagonal/outbound-port-interface-in-core`); не DTO внешней системы (`hexagonal/port-speaks-domain-types`); не `X|None` где отсутствие=ошибка (`hexagonal/absence-is-not-error`); не класс (`hexagonal/outbound-port-interface-in-core`).
   - **In (`R-HEX-AIN-*`):** роутер через `Dispatcher` (`hexagonal/controller-dispatches-only`), не возвращает domain наружу (`hexagonal/rest-mapping-in-adapter`), без бизнес-логики (`hexagonal/controller-dispatches-only`), не импортит `adapters/out/*` (`hexagonal/adapters-do-not-know-each-other`).
   - **Out (`R-HEX-AOUT-*`):** реализует порт, мапит domain↔DTO, per-system пакет; не возвращает DTO внешней системы (`hexagonal/port-speaks-domain-types`), без бизнес-логики (`hexagonal/adapter-maps-not-decides`), не реализует порты разных доменов (`hexagonal/out-adapter-per-system`), не инжектит другой адаптер (`hexagonal/adapters-do-not-know-each-other`).
   - **app/ (`R-HEX-BOOT-*`):** только композиция/конфиг (`hexagonal/bootstrap-composition-only`); `create_app`/wiring не в core/adapters (`hexagonal/bootstrap-composition-only`).
   - **Тесты (`R-HEX-TEST-*`):** `import-linter` в CI как required check (`hexagonal/architecture-tests-required` если enforcement только через review).

4. **Cross-check:** домен/агрегаты — `ucp-py-ddd-tactical-review`; Dispatcher/UoW — `ucp-py-pattern-review`; per-system resilience — `ucp-py-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `core/` импортит фреймворк (`R-HEX-CORE-X1/X2`), нет import-linter-контракта (`hexagonal/module-per-part`), `core/`→`adapters` (`hexagonal/core-free-of-framework`), роутер зовёт репозиторий (`hexagonal/controller-dispatches-only`), порт-метод возвращает/принимает DTO внешней системы (`hexagonal/port-speaks-domain-types`/`hexagonal/port-speaks-domain-types`).
   - **Предупреждение** — анемичный домен (`hexagonal/rich-domain-model`), порт-класс (`hexagonal/outbound-port-interface-in-core`), бизнес-логика в адаптере (`hexagonal/controller-dispatches-only`/`hexagonal/adapter-maps-not-decides`), адаптеры зависят друг от друга, import-linter не в CI (`hexagonal/architecture-tests-required`).
   - **Замечание** — user/admin не разделены (`hexagonal/in-adapter-per-audience`), domain наружу как ответ (`hexagonal/rest-mapping-in-adapter`).

## Что не входит

- Бизнес-операции/Dispatcher — `ucp-py-pattern-review`. DDD-инварианты — `ucp-py-ddd-tactical-review`.
- Persistence — `ucp-py-sqlalchemy-review`. Resilience внешних вызовов — `ucp-py-resilience-review`.

$ARGUMENTS
