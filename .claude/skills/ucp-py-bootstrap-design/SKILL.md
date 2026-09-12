---
name: ucp-py-bootstrap-design
lang: python
description: Спроектировать или починить bootstrap FastAPI-сервиса по UCP (требования python-bootstrap/*) — профили на pydantic-settings, app factory с lifespan, явный DI, async SQLAlchemy + Liquibase, health live/ready.
when_to_use: Старт сервиса либо uvicorn не поднимается: missing config, ресурсы в глобале. Триггеры — «настрой bootstrap», «app factory», «почему сервис не стартует».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(uvicorn*) Bash(liquibase*) Bash(docker compose*) Bash(uv*)
---

# Проектирование bootstrap (Python / FastAPI)

Ты настраиваешь bootstrap-слой FastAPI-сервиса по UCP согласно `backend/python/python-bootstrap/spec.md`
(`PYBOOT-*`). Цель — сервис стартует локально одной командой, конфиг валидируется fail-fast, ресурсы в lifespan,
DI явный, раскладка core/adapters/app соблюдена.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/python-bootstrap/spec.md` (`PYBOOT-*`). Связанные: `backend/validation/references/python/implementation.md` (`BaseSettings`), `backend/usecase-pattern/references/python/implementation.md` (Dispatcher/DI), `backend/error-handling/references/python/implementation.md` (exception-handlers в фабрике).

2. **Диагноз: починка или с нуля.** Для починки сначала воспроизведи ошибку (`uvicorn app.main:app`); пройди Quickstart-чеклист (§ конец rules) — missing env / ресурс в глобале / нет Liquibase.

3. **Произведи код** (без комментариев; коды правил НЕ цитируй в коде):
   - `app/settings.py` — `Settings(BaseSettings)` с `APP_ENV`, required без default, nested, `.env`-оверрайды (`PYBOOT-2/4`).
   - `app/main.py` — `create_app(settings) -> FastAPI` фабрика + `lifespan` (engine/sessionmaker/клиенты открываются и закрываются здесь); регистрация роутеров/exception-handlers/middleware (`PYBOOT-5/6/7`).
   - `app/container.py` — DI: репозитории, handlers, dispatcher, `Clock`/`IdGenerator`-реализации (`PYBOOT-8/9`).
   - persistence: `create_async_engine` + `async_sessionmaker` в lifespan, сессия per-request через `Depends`; Liquibase-конфиг (`python-bootstrap/persistence-wiring`), миграции вне старта приложения.
   - health: `/health/live`, `/health/ready` (`python-bootstrap/liveness-and-readiness-split`).
   - bootstrap логирования/метрик/трейсинга в фабрике (`python-bootstrap/observability-configured-in-factory`).
   - README quickstart (`python-bootstrap/local-quickstart-documented`).

4. **Самопроверка** — Quickstart-чеклист из rules.

5. **Финальный шаг:** предложи `ucp-py-bootstrap-review`; для бизнес-операций — `ucp-py-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `os.getenv(...)` россыпью вместо `Settings` (`python-bootstrap/single-settings-object`); engine/клиент на уровне модуля (`python-bootstrap/resources-in-lifespan`).
- `datetime.now()`/`uuid4()` напрямую в домене вместо `Clock`/`IdGenerator` (`python-bootstrap/clock-and-ids-behind-protocols`).
- `Base.metadata.create_all()` для прод-схемы вместо Liquibase (`python-bootstrap/persistence-wiring`).
- блокирующие sync-вызовы в async без executor (`python-bootstrap/no-blocking-in-async-handlers`); импорт `app/`/`adapters` из `core/` (`python-bootstrap/layout-directs-dependencies-inward`).

После работы скилла — обязательно `ucp-py-bootstrap-review`.

$ARGUMENTS

## Гейты проекта

Каталог — `.claude/docs/_meta/project-gates.md`. Эти проверки методология
определяет сама, и генерируешь их **ты**: пока их нет в проекте, требования,
которые на них ссылаются, фактически держатся ревью.

Сгенерируй четыре скрипта и привяжи их к общей задаче проверки и в конвейер:

| Скрипт | Что читает | Что делает |
| --- | --- | --- |
| `ddl-check` | файлы миграций | разбирает объявления таблиц, колонок, индексов и ограничений; проверяет типы, именование, безопасность изменений |
| `config-check` | конфигурацию по профилям | сверяет значения, от которых зависит поведение под отказом: брокер, кеш, пул, обслуживание, остановка, устойчивость |
| `manifest-check` | манифесты развёртывания | сверяет бюджет остановки, паузу перед ней, раздельные пробы, правила обновления, запуск не от суперпользователя |
| `test-lint` | исходники тестов | ловит ожидания, обращения к настоящим часам, контейнеры брокера в подготовке, подмену портов в интеграционных тестах |

Полный перечень проверок каждого скрипта — таблицы каталога. Каждая строка
таблицы называет требование, которое проверка закрывает: **проверка без
требования не заводится**, требование без проверки остаётся с гейтом `ревью`.

Структурные правила этого трека — контракт импортов и запреты зависимостей;
их набор перечислен в полях «Гейт» самих требований. Правила, названные
в каталоге для Java, здесь остаются на ревью — это записано в поле «Не ловит»
соответствующих требований, выдумывать им аналоги не нужно.

Проверка, которую сервис не может пройти сразу, заводится **с файлом
исключений** — по образцу подавлений анализаторов: причина и срок. Отключать
проверку целиком нельзя.
