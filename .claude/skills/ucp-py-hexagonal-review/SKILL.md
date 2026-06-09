---
name: ucp-py-hexagonal-review
lang: python
description: Ревью Hexagonal Architecture Python-сервиса (коды R-HEX-*) — пакеты core/adapters/app, layered-контракт import-linter, core без FastAPI/SQLAlchemy/Pydantic, порты-Protocol в core/<bc>/port, роутеры через Dispatcher, app только композиция.
when_to_use: Ревью раскладки сервиса Уровня 3 — core/, adapters/, app/, конфиг import-linter.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(lint-imports*)
---

# Ревью Hexagonal (Python / пакеты + import-linter)

Ты ревьюишь раскладку сервиса на соответствие **контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Python-реализации** `backend/hexagonal/python/hexagonal-style-guide.md`. Изоляция — через `import-linter`.

## Зависимости

- **`.claude/docs/backend/hexagonal/hexagonal-rules.md`** + **`backend/hexagonal/python/hexagonal-style-guide.md`**.
- Парные: `backend/usecase-pattern/python/...` (`R-HEX-3`/Dispatcher), `backend/ddd-tactical/python/...` (rich domain), `backend/python/sqlalchemy/sqlalchemy-rules.md` (out-persistence).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-HEX-CORE-X1`, `R-HEX-AOUT-X4`), не префикс.

2. **Скоп.** `src/<service>/{core,adapters,app}/**`, `pyproject.toml` (`[tool.importlinter]`), CI-конфиг, `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-MOD-*`):** дерево core/adapters/app; контракт import-linter present (`R-HEX-MOD-X1` если нет); `core/` не импортит `adapters/*` (`R-HEX-MOD-X2`); user/admin разделены (`R-HEX-MOD-X3`).
   - **Core (`R-HEX-CORE-*`):** без FastAPI (`R-HEX-CORE-X1`)/SQLAlchemy (`R-HEX-CORE-X2`)/Pydantic-REST-DTO (`R-HEX-CORE-X5`); ORM-модель не используется как domain (`R-HEX-CORE-X4`); rich domain, не анемия (`R-HEX-CORE-X3`).
   - **Ports (`R-HEX-PORT-*`):** `Protocol` в `core/<bc>/port/out/`, domain-типы в сигнатурах; не в out-adapter (`R-HEX-PORT-X1`); не DTO внешней системы (`R-HEX-PORT-X2`); не `X|None` где отсутствие=ошибка (`R-HEX-PORT-X3`); не класс (`R-HEX-PORT-X4`).
   - **In (`R-HEX-AIN-*`):** роутер через `Dispatcher` (`R-HEX-AIN-X2`), не возвращает domain наружу (`R-HEX-AIN-X3`), без бизнес-логики (`R-HEX-AIN-X1`), не импортит `adapters/out/*` (`R-HEX-AIN-X4`).
   - **Out (`R-HEX-AOUT-*`):** реализует порт, мапит domain↔DTO, per-system пакет; не возвращает DTO внешней системы (`R-HEX-AOUT-X1`), без бизнес-логики (`R-HEX-AOUT-X2`), не реализует порты разных доменов (`R-HEX-AOUT-X3`), не инжектит другой адаптер (`R-HEX-AOUT-X4`).
   - **app/ (`R-HEX-BOOT-*`):** только композиция/конфиг (`R-HEX-BOOT-X1`); `create_app`/wiring не в core/adapters (`R-HEX-BOOT-X2`).
   - **Тесты (`R-HEX-TEST-*`):** `import-linter` в CI как required check (`R-HEX-TEST-X1` если enforcement только через review).

4. **Cross-check:** домен/агрегаты — `ucp-py-ddd-tactical-review`; Dispatcher/UoW — `ucp-py-pattern-review`; per-system resilience — `ucp-py-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `core/` импортит фреймворк (`R-HEX-CORE-X1/X2`), нет import-linter-контракта (`R-HEX-MOD-X1`), `core/`→`adapters` (`R-HEX-MOD-X2`), роутер зовёт репозиторий (`R-HEX-AIN-X2`), порт-метод возвращает/принимает DTO внешней системы (`R-HEX-PORT-X2`/`R-HEX-AOUT-X1`).
   - **Предупреждение** — анемичный домен (`R-HEX-CORE-X3`), порт-класс (`R-HEX-PORT-X4`), бизнес-логика в адаптере (`R-HEX-AIN-X1`/`R-HEX-AOUT-X2`), адаптеры зависят друг от друга, import-linter не в CI (`R-HEX-TEST-X1`).
   - **Замечание** — user/admin не разделены (`R-HEX-MOD-X3`), domain наружу как ответ (`R-HEX-AIN-X3`).

## Что не входит

- Бизнес-операции/Dispatcher — `ucp-py-pattern-review`. DDD-инварианты — `ucp-py-ddd-tactical-review`.
- Persistence — `ucp-py-sqlalchemy-review`. Resilience внешних вызовов — `ucp-py-resilience-review`.

$ARGUMENTS
