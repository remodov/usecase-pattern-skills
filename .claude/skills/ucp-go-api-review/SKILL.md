---
name: ucp-go-api-review
lang: go
description: Ревью REST API-контракта/кода Go-сервиса (net/http + chi) по UCP (коды R-URL-*, R-MTH-*, R-RSP-*, R-ERR-*) — URL/методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operationId; стек chi/validator/apperr/slog.
when_to_use: Изменения в chi-роутерах, request/response-структурах, httperr-рендерере, OpenAPI-аннотациях или ProblemDetails-маппинге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью REST API (Go / net/http + chi)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/rest-api-rules.md` и **Go-реализации**
`backend/rest-api/go/rest-api-style-guide.md`. Go code-first: структуры Go — источник контракта; OpenAPI
синхронизируется постфактум через `swaggo/swag` или ручные аннотации.

## Зависимости

- **`.claude/docs/backend/rest-api/rest-api-rules.md`** + **`backend/rest-api/go/rest-api-style-guide.md`**.
- Парные: `backend/validation/go/...` (go-playground/validator, violations), `backend/error-handling/go/...` (apperr.Kind, problem+json), `backend/usecase-pattern/go/...` (chi-handler → UseCase/Handler).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-RSP-X1`, `R-ERR-X1`, `R-URL-X2`), не префикс. Помни Go-специфику: нет магии фреймворка — каждое правило явно выражено в коде; это ответственность разработчика.

2. **Скоп.** chi-роутер (`r.Get/Post/Put/Patch/Delete/Route`), request/response-структуры с `json:`-тегами, `httperr.Write` / `writeProblem`, `writeValidationProblem`, OpenAPI-аннотации swaggo; `git diff`.

3. **Прогон.**

   ### URL / методы (`R-URL/MTH/NEST/ACT/VER-*`)
   - kebab-case, строчные, без trailing-slash, `/api/v1`-префикс (`r.Route("/api/v1", ...)`).
   - Trailing-slash или заглавные → `R-URL-X1/X2`; глагол в CRUD-пути → `R-URL-X4`; >2 уровня → `R-NEST-X1`.
   - Action не через `r.Post` → `R-ACT-X2`; версия в query → `R-VER-X2`; путь без `/api`+версии → `R-VER-X3`.
   - `w.WriteHeader(http.StatusCreated)` при POST-create, `http.StatusNoContent` при DELETE — проверь соответствие `R-MTH-6`.
   - В chi `{id}` в дизайне пути допустим; в OpenAPI-аннотациях параметры именуются уникально (`{orderId}`, `{itemId}`) — `R-OAS-3`.

   ### Query (`R-QRY-*`)
   - camelCase-имена в тегах `query:` / парсинге `r.URL.Query()`.
   - CSV-массивы (`?status=NEW,PAID` вместо повтора `r.Form["status"]`) → `R-QRY-X3`.
   - `page` проверяется `>= 1` (`page=0` → `R-QRY-X2`); бизнес-логика в query → `R-QRY-X4`.

   ### JSON / ответы (`R-FLD/RSP-*`)
   - camelCase `json:"fieldName"` на каждом поле; `time.Time` ISO 8601; enum UPPER_SNAKE_CASE; деньги `int64` (не `float64`).
   - `null`-поля в 2xx: `*T`-указатели без `omitempty` в response-структурах → `R-RSP-X1`; пустая строка вместо отсутствия поля → `R-RSP-X2`.
   - Envelope `{"data": {...}}` для единичного ресурса → `R-RSP-X4`; коллекция без `{"content": [...], "page": ..., "size": ..., "total": ...}` → `R-RSP-2`; пустая коллекция как `null` или отсутствующее поле → `R-RSP-7`.
   - `Location`-заголовок при создании: `w.Header().Set("Location", ...)` + `201 Created` — `R-RSP-3`.

   ### Ошибки (`R-ERR-*`)
   - `Content-Type: application/problem+json` на всех error-response; `application/json` → `R-ERR-X1`.
   - Единый `httperr.Write` (не разные структуры в каждом хендлере) — `R-PRIN-2`.
   - Валидационные ошибки: `400 VALIDATION_ERROR` + `violations` через `go-playground/validator`; `422` → `R-ERR-X3`.
   - `code` UPPER_SNAKE_CASE, `type` URN (`urn:problem:<service>:<code>`); `type: "about:blank"` → `R-ERR-X2`.
   - Stack, `err.Error()` низкоуровневых ошибок / SQL в теле 500 → `R-ERR-X4`.

   ### Заголовки (`R-HDR-*`)
   - Кастомные с доменным префиксом; `X-`-префикс → `R-HDR-X1`.
   - `Idempotency-Key` для неидемпотентных POST (финансовые операции, создание с побочным эффектом).
   - `traceparent` через OTel middleware (`otelhttp.NewMiddleware`) — `R-HDR-4`.

   ### OpenAPI (`R-OAS-*`)
   - `operationId` camelCase, `tags` (множественное число, заглавная), `summary` ≤ 80 символов — `R-OAS-1/2/4`.
   - Нет `operationId` → swaggo генерирует длинный авто-имя, не соответствует `R-OAS-1`.

4. **Go-антипаттерны** (специфика стека):
   - `json.Marshal(v)` без `omitempty` на response-полях → `null` в 2xx (`R-RSP-X1`).
   - `r.URL.Query().Get("page")` без проверки `< 1` → `R-QRY-X2`.
   - Сырой `err.Error()` в `detail` ответа → раскрытие схемы БД (`R-ERR-X4`).
   - Разные `ProblemDetails`-структуры в разных хендлерах вместо `httperr.Write` → `R-PRIN-2`.

5. **Cross-check:** go-playground/validator-constraints и маппинг `ValidationErrors` → `violations` — `ucp-go-validation-review`; `apperr.Kind`/edge-renderer — `ucp-go-error-handling-review`; chi-handler → UseCase-слой — `ucp-go-pattern-review`; rate-limit — `ucp-go-resilience-review`.

6. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

7. **Серьёзность** (`RFF-12`):
   - **Критично** — `null`-поля в 2xx (`R-RSP-X1`), `application/json` вместо problem+json (`R-ERR-X1`), stack/SQL в 500 (`R-ERR-X4`), путь без `/api`+версии (`R-VER-X3`), CSV-массивы (`R-QRY-X3`), `w.WriteHeader(200)` при ошибке.
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), `422` вместо `400`+violations (`R-ERR-X3`), `X-`-заголовок (`R-HDR-X1`), envelope единичного (`R-RSP-X4`), action не-POST (`R-ACT-X2`), `type: "about:blank"` (`R-ERR-X2`).
   - **Замечание** — нет `operationId`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`R-NEST-X1`), `float64` для денег, boolean без `is/has`-префикса.

## Что не входит

- go-playground/validator-constraints / cross-field — `ucp-go-validation-review`.
- apperr.Kind-иерархия / edge-renderer / recover-middleware — `ucp-go-error-handling-review`.
- chi-handler → UseCase/Handler/слои — `ucp-go-pattern-review`.
- Rate-limit реализация — `ucp-go-resilience-review`.

$ARGUMENTS
