---
name: ucp-go-api-design
lang: go
description: Спроектировать REST API-эндпоинт/ресурс на Go code-first (net/http + chi) по контракту (коды R-URL/MTH/RSP/ERR/OAS-*) — kebab-case URL + /api/v1, query camelCase, JSON без null в 2xx, go-playground/validator + violations, problem+json (RFC 9457).
when_to_use: Триггеры — «спроектируй эндпоинт X», «REST-ресурс Y на Go/chi», «OpenAPI для Z на Go». При создании chi-роутеров, request/response-структур, error-renderer.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# REST API — проектирование (Go / net/http + chi, code-first)

Ты проектируешь REST-контракт по **общему контракту** `backend/rest-api/rest-api-rules.md` и **Go-реализации**
`backend/rest-api/go/rest-api-style-guide.md`. Go **code-first**: структуры + chi-роутер → OpenAPI генерируется
постфактум (`swaggo/swag`) или синхронизируется ревью. Принцип: **структуры Go = источник контракта**.

## Инструкции

1. **Прочитай** контракт + Go-style-guide (большинство правил — протокольного уровня, общие для всех языков).
   Коды правил — в обосновании, **не** в комментариях кода. Смежные доки: `backend/validation/go/...` (validator + violations),
   `backend/error-handling/go/...` (apperr + httperr.Write + problem+json), `backend/usecase-pattern/go/...` (роутер → UseCase).

2. **URL/методы/версии** (`R-URL/MTH/NEST/ACT/VER-*`): kebab-case, без trailing slash, `r.Route("/api/v1", ...)`;
   метод = chi-декоратор + явный `w.WriteHeader`; action всегда `r.Post` (`/orders/{id}/confirm`);
   не более двух уровней вложенности; параметр пути — `chi.URLParam(r, "id")`.

3. **Query-параметры** (`R-QRY-*`): имена camelCase; `page` 1-based + `size`; массивы — `r.Form["key"]`
   (повтор параметра, не CSV); сложный поиск — `r.Post("/resources/search", ...)`.

4. **JSON/ответы** (`R-FLD/RSP-*`): теги `json:"fieldName"`, enum UPPER_SNAKE, `time.Time` ISO 8601,
   деньги `int64` (не `float64`); **нет `null` в 2xx** — `omitempty` на необязательных полях, не `*T` в response-структурах;
   коллекция `{"content": [...], "page": 1, "size": 20, "total": N}`; `201 Created` + `Location` при создании;
   `204 No Content` при удалении; пустая коллекция `"content": []`.

5. **Ошибки** (`R-ERR-*`): единый `httperr.Write(w, r, err)` во всех хендлерах — делегируй реализацию
   `ucp-go-error-handling-design`; `Content-Type: application/problem+json`; `code` UPPER_SNAKE из enum;
   валидация — `400 VALIDATION_ERROR` + `violations` через `go-playground/validator` → маппинг `ValidationErrors`;
   не светить stack/SQL в 500.

6. **Заголовки/OpenAPI** (`R-HDR/OAS-*`): кастомные без `X-`; `Idempotency-Key` на неидемпотентных POST;
   `traceparent` через OTel middleware (`otelhttp.NewMiddleware`); `operationId` camelCase + `tags` + `summary`
   на каждом маршруте в аннотациях `swaggo/swag` или в ручной OpenAPI-спеке.

7. **Самопроверка** (§чек-лист из `go/rest-api-style-guide.md`) + предложи `ucp-go-api-review`.
   Валидация входа — `ucp-go-validation-design`. Обработка ошибок — `ucp-go-error-handling-design`.

## Антипаттерны, которые НЕ генерировать

- trailing slash / заглавные / snake_case / глаголы в CRUD-пути (`R-URL-X1/X2`/`R-MTH-X1`); >2 уровня вложенности (`R-NEST-X1`); версия в query (`R-VER-X2`).
- comma-separated query-массивы (`R-QRY-X3`); `page=0` (`R-QRY-X2`); бизнес-логика в query (`R-QRY-X4`).
- `null`-поля / `*T`-указатели в response-структурах в 2xx (`R-RSP-X1/X2`); envelope для единичного ресурса (`R-RSP-X4`); `nullable: true` (`R-RSP-X3`).
- `Content-Type: application/json` для ошибки (`R-ERR-X1`); HTTP 422 вместо 400 для валидации (`R-ERR-X3`); stack/SQL в 500 (`R-ERR-X4`); `X-`-префикс заголовка (`R-HDR-X1`).
- разные структуры ошибок в разных хендлерах вместо единого `httperr.Write` (`R-PRIN-2`).
- `float64` для денег; `json.Marshal` без `omitempty` на response-полях.

После работы скилла — обязательно `ucp-go-api-review`.

$ARGUMENTS
