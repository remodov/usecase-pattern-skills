---
name: ucp-py-hexagonal-design
lang: python
description: Сгенерировать или реструктурировать Python-сервис под Hexagonal Architecture (коды R-HEX-*) — пакеты core/adapters/app, import-linter в pyproject.toml, порты-Protocol в core/<bc>/port/out/, FastAPI-роутеры через Dispatcher, app/ composition root.
when_to_use: Старт сервиса Уровня 3 или upgrade 2→3. Триггеры — «hexagonal layout на питоне», «реструктурируй под core/adapters».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(lint-imports*) Bash(ruff*)
---

# Hexagonal Architecture — проектирование (Python / пакеты + import-linter)

Ты генерируешь раскладку сервиса по **общему контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Python-реализации** `backend/hexagonal/python/hexagonal-style-guide.md`. Изоляция границ — через `import-linter`, не gradle-модули.

## Инструкции

1. **Прочитай** контракт `backend/hexagonal/hexagonal-rules.md` + Python-style-guide. Коды `R-HEX-*` в design-обосновании, не в коде. Связанные: `backend/usecase-pattern/python/...` (Dispatcher/UseCase/порты), `backend/ddd-tactical/python/...` (домен в core/), `backend/python/sqlalchemy/sqlalchemy-rules.md` (out-persistence).

2. **Реши уровень** (`R-HEX-WHEN-*`): Уровень 3 (DDD + ports/adapters) → полная раскладка; Уровень 1–2 → плоский `app/`, не плоди ceremony. Назови выбор в начале.

3. **Произведи дерево пакетов** (`R-HEX-MOD-*`):
   ```
   src/<service>/core/<bc>/{aggregate,entity,value_object,event,port,usecase,service}/
   src/<service>/adapters/in/http/
   src/<service>/adapters/out/{persistence,<system>}/
   src/<service>/app/   # create_app, container, lifespan, settings
   ```
   `core/` — без FastAPI/SQLAlchemy/Pydantic; стрелка `app → adapters → core`.

4. **Контракт import-linter** в `pyproject.toml` (`[tool.importlinter]`, type=`layers`: `app` > `adapters` > `core`; при user/admin-разделении — `forbidden`/`independence`). Это обязательный enforcement (`R-HEX-TEST-1`), не опционально.

5. **Порты** (`R-HEX-PORT-*`) — `Protocol` в `core/<bc>/port/out/`, domain-типы в сигнатурах, исключения базового типа в `core/`. **In-adapter** (`R-HEX-AIN-*`) — роутер через `Dispatcher`, маппер REST-DTO↔command/response. **Out-adapter** (`R-HEX-AOUT-*`) — реализует порт, маппер domain↔DTO, per-system пакет. **app/** (`R-HEX-BOOT-*`) — только композиция.

6. **Placeholder-файлы**: `app/main.py` (`create_app`), `core/<bc>/__init__.py`, `pyproject.toml` (deps + import-linter), пустой контракт-тест в CI. Самопроверка по §9 + предложи `ucp-py-hexagonal-review`.

## Антипаттерны, которые НЕ генерировать

- Отсутствие import-linter-контракта (`R-HEX-MOD-X1`); `core/` импортит фреймворк (`R-HEX-CORE-X1/X2`); ORM/Pydantic-DTO как domain в core (`R-HEX-CORE-X4/X5`).
- Порт в out-adapter (`R-HEX-PORT-X1`); порт-класс вместо Protocol (`R-HEX-PORT-X4`); роутер зовёт репозиторий (`R-HEX-AIN-X2`); адаптеры зависят друг от друга (`R-HEX-AIN-X4`/`R-HEX-AOUT-X4`).
- Бизнес-логика в адаптере (`R-HEX-AIN-X1`/`R-HEX-AOUT-X2`) или в `app/` (`R-HEX-BOOT-X1`).

После работы скилла — обязательно `ucp-py-hexagonal-review`.

$ARGUMENTS
