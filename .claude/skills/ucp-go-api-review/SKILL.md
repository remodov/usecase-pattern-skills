---
name: ucp-go-api-review
lang: go
description: Ревью REST API-контракта/кода Go-сервиса (net/http + chi) по UCP (требования rest-api/*, error-handling/*) — URL/методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operationId; стек chi/validator/apperr/slog.
when_to_use: Изменения в chi-роутерах, request/response-структурах, httperr-рендерере, OpenAPI-аннотациях или ProblemDetails-маппинге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью REST API (Go / net/http + chi)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/spec.md` и **Go-реализации**
`backend/rest-api/references/go/implementation.md`. Go code-first: структуры Go — источник контракта; OpenAPI
синхронизируется постфактум через `swaggo/swag` или ручные аннотации.

## Зависимости

- **`.claude/docs/backend/rest-api/spec.md`** + **`backend/rest-api/references/go/implementation.md`**.
- Парные: `backend/validation/go/...` (go-playground/validator, violations), `backend/error-handling/go/...` (apperr.Kind, problem+json), `backend/usecase-pattern/go/...` (chi-handler → UseCase/Handler).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`rest-api/no-nulls-in-successful-response`, `rest-api/error-body-follows-standard`, `rest-api/path-lowercase-kebab-case`), не префикс. Помни Go-специфику: нет магии фреймворка — каждое правило явно выражено в коде; это ответственность разработчика.

2. **Скоп.** chi-роутер (`r.Get/Post/Put/Patch/Delete/Route`), request/response-структуры с `json:`-тегами, `httperr.Write` / `writeProblem`, `writeValidationProblem`, OpenAPI-аннотации swaggo; `git diff`.

3. **Прогон.**

   ### URL / методы (`R-URL/MTH/NEST/ACT/VER-*`)
   - kebab-case, строчные, без trailing-slash, `/api/v1`-префикс (`r.Route("/api/v1", ...)`).
   - Trailing-slash или заглавные → `R-URL-X1/X2`; глагол в CRUD-пути → `R-URL-X4`; >2 уровня → `rest-api/nesting-max-two-levels`.
   - Action не через `r.Post` → `rest-api/action-endpoints-shape`; версия в query → `rest-api/version-in-path`; путь без `/api`+версии → `rest-api/version-in-path`.
   - `w.WriteHeader(http.StatusCreated)` при POST-create, `http.StatusNoContent` при DELETE — проверь соответствие `rest-api/methods-match-semantics`.
   - В chi `{id}` в дизайне пути допустим; в OpenAPI-аннотациях параметры именуются уникально (`{orderId}`, `{itemId}`) — `rest-api/unique-path-parameter-names`.

   ### Query (`R-QRY-*`)
   - camelCase-имена в тегах `query:` / парсинге `r.URL.Query()`.
   - CSV-массивы (`?status=NEW,PAID` вместо повтора `r.Form["status"]`) → `rest-api/arrays-as-repeated-parameters`.
   - `page` проверяется `>= 1` (`page=0` → `rest-api/pagination-forms`); бизнес-логика в query → `rest-api/filters-ranges-and-search`.

   ### JSON / ответы (`R-FLD/RSP-*`)
   - camelCase `json:"fieldName"` на каждом поле; `time.Time` ISO 8601; enum UPPER_SNAKE_CASE; деньги `int64` (не `float64`).
   - `null`-поля в 2xx: `*T`-указатели без `omitempty` в response-структурах → `rest-api/no-nulls-in-successful-response`; пустая строка вместо отсутствия поля → `rest-api/no-nulls-in-successful-response`.
   - Envelope `{"data": {...}}` для единичного ресурса → `rest-api/single-resource-is-flat`; коллекция без `{"content": [...], "page": ..., "size": ..., "total": ...}` → `rest-api/collection-response-shape`; пустая коллекция как `null` или отсутствующее поле → `rest-api/no-nulls-in-successful-response`.
   - `Location`-заголовок при создании: `w.Header().Set("Location", ...)` + `201 Created` — `rest-api/status-codes-and-bodies`.

   ### Ошибки (`R-ERR-*`)
   - `Content-Type: application/problem+json` на всех error-response; `application/json` → `rest-api/error-body-follows-standard`.
   - Единый `httperr.Write` (не разные структуры в каждом хендлере) — `rest-api/contract-is-predictable`.
   - Валидационные ошибки: `400 VALIDATION_ERROR` + `violations` через `go-playground/validator`; `422` → `rest-api/error-status-codes-limited`.
   - `code` UPPER_SNAKE_CASE, `type` URN (`urn:problem:<service>:<code>`); `type: "about:blank"` → `rest-api/error-type-is-stable-category`.
   - Stack, `err.Error()` низкоуровневых ошибок / SQL в теле 500 → `rest-api/no-internals-in-error-body`.

   ### Заголовки (`R-HDR-*`)
   - Кастомные с доменным префиксом; `X-`-префикс → `rest-api/headers-standard-and-prefixed`.
   - `Idempotency-Key` для неидемпотентных POST (финансовые операции, создание с побочным эффектом).
   - `traceparent` через OTel middleware (`otelhttp.NewMiddleware`) — `rest-api/trace-context-header`.

   ### OpenAPI (`R-OAS-*`)
   - `operationId` camelCase, `tags` (множественное число, заглавная), `summary` ≤ 80 символов — `R-OAS-1/2/4`.
   - Нет `operationId` → swaggo генерирует длинный авто-имя, не соответствует `rest-api/operation-id-and-tags`.

4. **Go-антипаттерны** (специфика стека):
   - `json.Marshal(v)` без `omitempty` на response-полях → `null` в 2xx (`rest-api/no-nulls-in-successful-response`).
   - `r.URL.Query().Get("page")` без проверки `< 1` → `rest-api/pagination-forms`.
   - Сырой `err.Error()` в `detail` ответа → раскрытие схемы БД (`rest-api/no-internals-in-error-body`).
   - Разные `ProblemDetails`-структуры в разных хендлерах вместо `httperr.Write` → `rest-api/contract-is-predictable`.

5. **Cross-check:** go-playground/validator-constraints и маппинг `ValidationErrors` → `violations` — `ucp-go-validation-review`; `apperr.Kind`/edge-renderer — `ucp-go-error-handling-review`; chi-handler → UseCase-слой — `ucp-go-pattern-review`; rate-limit — `ucp-go-resilience-review`.

6. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

7. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `null`-поля в 2xx (`rest-api/no-nulls-in-successful-response`), `application/json` вместо problem+json (`rest-api/error-body-follows-standard`), stack/SQL в 500 (`rest-api/no-internals-in-error-body`), путь без `/api`+версии (`rest-api/version-in-path`), CSV-массивы (`rest-api/arrays-as-repeated-parameters`), `w.WriteHeader(200)` при ошибке.
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), `422` вместо `400`+violations (`rest-api/error-status-codes-limited`), `X-`-заголовок (`rest-api/headers-standard-and-prefixed`), envelope единичного (`rest-api/single-resource-is-flat`), action не-POST (`rest-api/action-endpoints-shape`), `type: "about:blank"` (`rest-api/error-type-is-stable-category`).
   - **Замечание** — нет `operationId`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`rest-api/nesting-max-two-levels`), `float64` для денег, boolean без `is/has`-префикса.

## Что не входит

- go-playground/validator-constraints / cross-field — `ucp-go-validation-review`.
- apperr.Kind-иерархия / edge-renderer / recover-middleware — `ucp-go-error-handling-review`.
- chi-handler → UseCase/Handler/слои — `ucp-go-pattern-review`.
- Rate-limit реализация — `ucp-go-resilience-review`.

$ARGUMENTS
