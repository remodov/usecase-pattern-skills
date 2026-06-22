---
name: ucp-py-new-service
lang: python
description: Оркестратор создания нового FastAPI-сервиса с нуля по UCP. Запускает полную цепочку ucp-py-* скиллов в правильном порядке (спека → DDD → codegen-контракты с чекпоинтами → persistence → bootstrap → error/obs/auth → usecase/api → integration/scheduler → tests). Не пишет код от руки — вызывает downstream-скиллы. Триггер-фразы — «сделай FastAPI-сервис», «новый питон-сервис», «напиши сервис на FastAPI», «начнём сервис».
when_to_use: Старт нового Python/FastAPI-сервиса. Для contract/DB-first проектов с OpenAPI+DBML как источниками истины.
allowed-tools: Read Glob Grep Bash(find*) Skill(ucp-spec-design) Skill(ucp-py-ddd-tactical-design) Skill(ucp-py-codegen-design) Skill(ucp-py-sqlalchemy-design) Skill(ucp-py-bootstrap-design) Skill(ucp-py-error-handling-design) Skill(ucp-py-observability-design) Skill(ucp-py-auth-design) Skill(ucp-py-pattern-design) Skill(ucp-py-api-design) Skill(ucp-py-integration-design) Skill(ucp-py-resilience-design) Skill(ucp-py-scheduler-design) Skill(ucp-py-test-design) Skill(superpowers:*)
---

# UCP New Service (Python / FastAPI) — оркестратор цепочки

Ты не пишешь код сам. Ты собираешь контекст и вызываешь downstream `ucp-py-*` скиллы в правильном порядке.
Каждый следующий шаг читает артефакты предыдущего. Выполняй **последовательно**, не параллельно.

## Перед запуском цепочки

1. **Определи уровень зрелости** (единая ось 0–3) — спроси, если не задан:
   - **Уровень 1** — router → service → repository (без usecase-pattern).
   - **Уровень 2** — UseCase + Handler + Dispatcher (usecase-pattern), опционально CQRS.
   - **Уровень 3** — DDD + Hexagonal (агрегаты, события, ports/adapters). Дефолт для новых доменных сервисов.

2. **Собери бизнес-описание.** Минимум: акторы, операции, глоссарий. Без него `ucp-spec-design` не стартует — не выдумывай факты, попроси текст/документ.

3. **Определи подход к контрактам.** Дефолт команды — **contract/DB-first codegen**: OpenAPI (`doc/openapi.yaml`) и DBML (`doc/schema.dbml`) — источники истины, код генерируется (`ucp-py-codegen-*`, миграции Liquibase). Если проект code-first — пропусти codegen-шаги, схемы/ORM пишутся в рамках api/sqlalchemy-скиллов.

4. **Проверь стартовую точку** — что уже есть:
   ```bash
   find . -maxdepth 4 -name "*.md" -path "*/spec/*" | head -10
   ls src 2>/dev/null || ls app 2>/dev/null || echo "(исходники пусто)"
   find . -maxdepth 3 -name "*.dbml" -o -name "openapi*.y*ml" 2>/dev/null | head
   ```

## Цепочка скиллов

### Шаг 1 — Спека
`Skill("ucp-spec-design", "<уровень> + <бизнес-описание>")` — спека с глоссарием, use-cases, ролями, ошибками, NFR.
Пропусти, если `docs/spec/<service>-spec.md` актуален.

### Шаг 2 — DDD-слой (только Уровень 3)
`Skill("ucp-py-ddd-tactical-design")` — агрегаты, VO, события, порты. На Уровнях 1–2 пропусти, сообщи об этом.

### Шаг 3 — Контракты через codegen (contract/DB-first) — ДВА ЧЕКПОИНТА
- **3a. Схема БД:** `Skill("ucp-py-codegen-design", "DBML из доменной модели спеки")` — сгенерируй `doc/schema.dbml`.
- **3b. [CHECKPOINT DBML]** — покажи DBML пользователю, внеси правки, дождись явного подтверждения. **Не продолжай без него.**
- **3c.** Продолжи codegen: `dbml2sql --postgres` → Liquibase changelog → `sqlacodegen` (ORM-черновик).
- **3d. API-контракт:** `Skill("ucp-py-codegen-design", "OpenAPI из §API спеки")` — сгенерируй `doc/openapi.yaml`.
- **3e. [CHECKPOINT OpenAPI]** — покажи контракт, внеси правки, дождись подтверждения.
- **3f.** Продолжи codegen: `datamodel-codegen` → Pydantic v2-схемы (StrEnum, snake+alias, `ApiBaseModel`).

### Шаг 4 — Persistence
`Skill("ucp-py-sqlalchemy-design")` — репозиторий (реализует порт), маппер ORM↔domain, UoW поверх ORM-черновика из шага 3c.

### Шаг 5 — Bootstrap
`Skill("ucp-py-bootstrap-design")` — app factory `create_app`, `lifespan`, DI-контейнер, `pydantic-settings`-профили. Пропусти, если рабочий скелет уже есть.

### Шаг 6 — Обработка ошибок
`Skill("ucp-py-error-handling-design")` — иерархия `AppError`, exception-handlers, problem+json (RFC 9457).

### Шаг 7 — Наблюдаемость
`Skill("ucp-py-observability-design")` — structlog (correlation-id), Prometheus-метрики, OTel.

### Шаг 8 — Авторизация
`Skill("ucp-py-auth-design")` — JWT/JWKS, RBAC/ABAC. Пропусти, если в спеке доступ `permitAll`.

### Шаг 9 — UseCase / Handler / Endpoints (по операции)
- `Skill("ucp-py-pattern-design", "<операция из §Use Cases>")` — UseCase (frozen dataclass) + Handler + Dispatcher.
- `Skill("ucp-py-api-design", "<эндпоинт операции>")` — роутер + DTO.
Вызывай по одной операции; при нескольких — уточни порядок у пользователя.

### Шаг 10 — Внешние интеграции (если есть)
`Skill("ucp-py-integration-design")` + `Skill("ucp-py-resilience-design")` — httpx-клиент per-system, retry/CB/timeout. Пропусти, если внешних систем нет.

### Шаг 11 — Фоновые задачи (если есть периодика/очереди)
`Skill("ucp-py-scheduler-design")` — БД-as-queue (SKIP LOCKED) и/или Celery-beat→HTTP-тик. Пропусти, если фоновой обработки нет.

### Шаг 12 — Тесты
`Skill("ucp-py-test-design")` — pytest + testcontainers, AAA по критериям приёмки спеки.

## После каждого шага

- Коротко резюмируй произведённое (файлы, ключевые решения) и сверь сквозную нумерацию из спеки (BR-/UC-/AC-).
- Спрашивай подтверждение перед следующим шагом.
- Если шаг вернул вопрос — ответь, потом продолжи цепочку.

## Если что-то пропущено или сломано

- `ucp-spec-design` без бизнес-описания → собери и передай.
- codegen-чекпоинт не подтверждён → стой, не запускай генерацию артефактов.
- `ucp-py-bootstrap-design` падает на профилях/missing config → передай ошибку в аргументах.

## Структура вывода

После завершения цепочки:
1. Список созданных файлов по шагам.
2. Команда первого запуска:
   ```bash
   docker compose up -d postgres
   uvicorn app.main:app --reload
   ```
3. Следующие шаги: ревью каждого слоя парными `ucp-py-*-review`, доп. операции, деплой.

$ARGUMENTS
