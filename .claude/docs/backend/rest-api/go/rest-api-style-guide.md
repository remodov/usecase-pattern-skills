# REST API — Go Style Guide (net/http + chi)

Реализация контракта `../rest-api-rules.md` (коды `R-PRIN/URL/RES/MTH/NEST/ALIAS/ACT/VER/QRY/FLD/RSP/HDR/ERR/RATE/FILE/DEP/BATCH/ASYNC/LOC/OAS-*`).

**Ключевая инверсия: code-first.** Go не имеет встроенного OpenAPI-генератора уровня Spring/FastAPI.
Стандартный подход — писать chi-роутер + request/response-структуры вручную и генерировать OpenAPI
постфактум (через `swaggo/swag` или `ogen`) либо вести спеку рядом с кодом. Поэтому принцип:
**структуры Go = источник контракта**; OpenAPI синхронизируется, а не дублирует.

Стек: `net/http` + `github.com/go-chi/chi/v5`; валидация — `go-playground/validator/v10`;
логирование — `log/slog`; метрики — `promauto`; ошибки — `apperr.Kind + errors.As + %w`
(cross-ref `backend/error-handling/go/error-handling-style-guide.md`).

---

## 1. Общие принципы (`R-PRIN-*`)

`R-PRIN-1..4` — предсказуемость, единообразие, читаемость URL, стабильность контракта — идентичны.

`R-PRIN-X1` ❌ HATEOAS-ссылки в теле ответа. Заголовок `Location` при создании — `w.Header().Set("Location", ...)` — единственное исключение.

**Специфика Go:** никакого «middleware-магии» нет — все правила явно выражаются в коде; это плюс (прозрачность) и ответственность (дисциплина с нулём уровня).

---

## 2. Формат URL-пути (`R-URL-*`)

`R-URL-1..3` — строчные, kebab-case, служебные вне `/api/v1`.

В chi путь задаётся строкой в `r.Route` / `r.Get`:

```go
r.Route("/api/v1", func(r chi.Router) {
    r.Route("/orders", func(r chi.Router) {
        r.Get("/", listOrders)
        r.Post("/", createOrder)
        r.Route("/{id}", func(r chi.Router) {
            r.Get("/", getOrder)
            r.Put("/", updateOrder)
            r.Delete("/", deleteOrder)
            r.Post("/confirm", confirmOrder)
            r.Route("/items", func(r chi.Router) {
                r.Get("/", listOrderItems)
            })
        })
    })
})
```

`R-URL-X1` ❌ Заглавные буквы или snake_case в пути.
`R-URL-X2` ❌ Trailing slash — chi по умолчанию не редиректит; не добавлять.
`R-URL-X3` ❌ Расширения (`.json`, `.xml`) в пути.
`R-URL-X4` ❌ Глаголы в пути для CRUD; action-эндпоинты — отдельно (§7).

---

## 3. Ресурсы (`R-RES-*`)

`R-RES-1` — коллекция — существительное во множественном числе (`/orders`, `/products`, `/customers`).
`R-RES-2` — singleton в контексте родителя — единственное число (`/orders/{id}/summary`).
`R-RES-3` — доменный термин из Ubiquitous Language; не переименовывать без изменения контракта.

`R-RES-X1/X2` ❌ единственное число для коллекции; смешение числа в одном дереве.

---

## 4. HTTP-методы и семантика (`R-MTH-*`)

`R-MTH-1..6` — семантика методов + коды успешных ответов идентичны протоколу.

| Метод  | Успешный код | chi-декоратор |
|--------|--------------|---------------|
| GET    | 200          | `r.Get`       |
| POST   | 201 (create) / 200 (action) | `r.Post` |
| PUT    | 200          | `r.Put`       |
| PATCH  | 200          | `r.Patch`     |
| DELETE | 204          | `r.Delete`    |

Коды выставляются явно: `w.WriteHeader(http.StatusCreated)`.

`R-MTH-X1` ❌ `GET` с побочным эффектом.

---

## 5. Вложенность ресурсов (`R-NEST-*`)

`R-NEST-1` — не более двух уровней вложенности. Третий уровень — ресурс на верхний уровень с фильтром:

```go
// PREFER: /api/v1/orders/{id}/items  (два уровня — ок)
// PREFER: /api/v1/items?orderId=...  (вместо /orders/{id}/items/{id}/shipments — третий уровень)
```

`R-NEST-2` — вложенность отражает принадлежность: `OrderItem` не существует без `Order`.
`R-NEST-3` — идентификатор родителя — в пути (`/orders/{id}/items`), не в теле запроса.
`R-NEST-4` — в дизайне URL path-параметр называется `{id}` (контекст из сегмента устраняет неоднозначность).
В chi-обработчике читается как `chi.URLParam(r, "id")`; в OpenAPI параметры именуются уникально (`orderId`, `itemId`).

`R-NEST-X1` ❌ Глубина более двух уровней.
`R-NEST-X2` ❌ ID в теле вместо пути.
`R-NEST-X3` ❌ Избыточное именование `{orderId}` там, где контекст уже дан сегментом.

---

## 6. Alias-сегменты (`R-ALIAS-*`)

`R-ALIAS-1..3` — `me` только для эндпоинтов, способных принять и чужой ID; временные alias (`latest`, `current`) — для singleton-выборки:

```go
r.Get("/users/me/profile", getMyProfile)       // admin может обратиться и по userId — me нужен
r.Get("/products/{id}/latest-review", ...)     // временной alias
```

`R-ALIAS-X1` ❌ `me` там, где токен — единственный источник (`/profile` singleton, не `/users/me/profile`).
`R-ALIAS-X2` ❌ `/me` без `users/`-префикса как самостоятельный путь.

---

## 7. Action-эндпоинты (`R-ACT-*`)

`R-ACT-1..4` — формат `POST /{resource}/{id}/{action}`, действие — глагол-инфинитив:

```go
r.Post("/orders/{id}/confirm", confirmOrder)
r.Post("/orders/{id}/cancel", cancelOrder)
r.Post("/customers/{id}/verify", verifyCustomer)
```

Параметры действия — в теле запроса; если параметров нет — тело пустое или `{}`.

`R-ACT-X1` ❌ Существительное или причастие в имени действия (`/cancellation`, `/confirmed`).
`R-ACT-X2` ❌ Любой метод кроме `POST` для action-эндпоинта.

---

## 8. Версионирование (`R-VER-*`)

`R-VER-1..3` — версия в URL-пути, формат `v<N>`, обязательный префикс `/api`:

```go
chi.NewRouter()  // базовый роутер
r.Route("/api/v1", func(r chi.Router) { ... })
// При breaking change:
r.Route("/api/v2", func(r chi.Router) { ... })
```

`R-VER-4..6` — новая версия только при breaking change; клиент обязан игнорировать неизвестные поля enum-значения.

`R-VER-X1` ❌ Минорная или дата-версия (`/api/v1.2`, `/api/2024-01`).
`R-VER-X2` ❌ Версия в query-параметре (`?version=2`).
`R-VER-X3` ❌ Эндпоинт без `/api` или без версии.
`R-VER-X4` ❌ Новая версия ради добавления необязательного поля.

---

## 9. Query-параметры (`R-QRY-*`)

`R-QRY-1..9` — camelCase-имена, page 1-based, cursor opaque, массивы повтором параметра:

```go
type ListOrdersQuery struct {
    Status    []string `query:"status"`
    CreatedFrom string `query:"createdFrom"`
    CreatedTo   string `query:"createdTo"`
    Page        int    `query:"page" validate:"min=1"`
    Size        int    `query:"size" validate:"min=1,max=100"`
    Sort        string `query:"sort"`
    Q           string `query:"q"`
}

func parseListQuery(r *http.Request) (ListOrdersQuery, error) {
    q := ListOrdersQuery{Page: 1, Size: 20}
    r.ParseForm()
    // повтор параметра: r.Form["status"] — slice из коробки
    q.Status = r.Form["status"]
    if v := r.URL.Query().Get("page"); v != "" {
        page, err := strconv.Atoi(v)
        if err != nil || page < 1 {
            return q, apperr.NewValidation("page must be >= 1")
        }
        q.Page = page
    }
    // ...аналогично для остальных
    return q, nil
}
```

Сложный поиск — `POST /api/v1/orders/search` с JSON-телом (`R-QRY-9`):

```go
r.Post("/orders/search", searchOrders)
```

`R-QRY-X1` ❌ snake_case или PascalCase в именах параметров.
`R-QRY-X2` ❌ `page=0` или 0-based нумерация.
`R-QRY-X3` ❌ Comma-separated значения для массивов (`?status=NEW,PAID`) — ручной парсинг, ломается при значении с запятой.
`R-QRY-X4` ❌ Бизнес-логика в query-параметре вместо action-эндпоинта.
`R-QRY-X5` ❌ Парсинг cursor на стороне клиента — cursor всегда непрозрачный токен.

---

## 10. Именование полей в JSON (`R-FLD-*`)

`R-FLD-1` — camelCase: теги `json:"fieldName"` на каждом поле структуры.
`R-FLD-2` — ISO 8601: `time.Time` с тегом `json:"createdAt"` сериализуется через кастомный маршаллер или обёртку.
`R-FLD-3` — enum-значения UPPER_SNAKE_CASE: тип `string` с константами или `iota`-подобный с `MarshalJSON`.
`R-FLD-4` — коллекции — множественное число (`"items": [...]`).
`R-FLD-5` — идентификаторы — суффикс `Id` (`"orderId"`, `"customerId"`).
`R-FLD-6` — JSON Merge Patch (RFC 7396): явный `null` в PATCH-теле — команда удалить поле; реализуется через `*T`-указатели в структуре запроса, не в ответе.
`R-FLD-7` — boolean-префиксы `is`/`has`/`can` — опционально, главное единообразие.

```go
type OrderResponse struct {
    OrderID   string    `json:"orderId"`
    Status    string    `json:"status"`       // "NEW", "CONFIRMED", "SHIPPED"
    CreatedAt time.Time `json:"createdAt"`
    Items     []Item    `json:"items"`
    Total     int64     `json:"total"`        // минорные единицы; не float64
}

type PatchOrderRequest struct {
    Note *string `json:"note"` // nil = поле не трогать; explicit null = удалить
}
```

---

## 11. Формат ответов (`R-RSP-*`)

`R-RSP-1` — единичный ресурс — плоский JSON без обёртки.
`R-RSP-2` — коллекция — `{"content": [...], "page": 1, "size": 20, "total": 150}`:

```go
type PageResponse[T any] struct {
    Content []T `json:"content"`
    Page    int `json:"page"`
    Size    int `json:"size"`
    Total   int `json:"total"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(v)
}
```

`R-RSP-3` — создание: `201 Created` + `Location` + тело ресурса:

```go
func createOrder(w http.ResponseWriter, r *http.Request) {
    // ... handle ...
    w.Header().Set("Location", "/api/v1/orders/"+order.ID)
    writeJSON(w, http.StatusCreated, toOrderResponse(order))
}
```

`R-RSP-4` — PUT/PATCH → `200 OK` + обновлённый ресурс.
`R-RSP-5` — DELETE → `204 No Content`, пустое тело: `w.WriteHeader(http.StatusNoContent)`.
`R-RSP-6` — action → `200 OK` + обновлённый ресурс; async → `202 Accepted` (§18).
`R-RSP-7` — пустая коллекция — `"content": []`, никогда `null`.
`R-RSP-8` — поля, которые могут отсутствовать, не попадают в ответ: используй `omitempty` или явную построк-конструкцию:

```go
type ProductResponse struct {
    ProductID   string  `json:"productId"`
    Name        string  `json:"name"`
    Description string  `json:"description,omitempty"` // отсутствует, если пусто
}
```

`R-RSP-X1` ❌ `null`-поля в 2xx-ответе. PREFER `omitempty` на необязательных полях; AVOID `*string` в response-структурах (указатели тянут `null`).
`R-RSP-X2` ❌ Пустая строка вместо отсутствия поля.
`R-RSP-X3` ❌ `nullable: true` в OpenAPI — поле либо есть, либо отсутствует.
`R-RSP-X4` ❌ Envelope-обёртка для единичного ресурса (`{"data": {...}}`).

---

## 12. Заголовки (`R-HDR-*`)

`R-HDR-1` — стандартные заголовки по назначению: `Content-Type`, `Authorization`, `Accept-Language`, `Location`.
`R-HDR-2` — кастомные с доменным префиксом (пример — `Shop-`); значение фиксируется в стандартах команды:

```go
w.Header().Set("Shop-Request-Id", requestID)
```

`R-HDR-3` — `Idempotency-Key` для неидемпотентных POST:

```go
func idempotencyKey(r *http.Request) string {
    return r.Header.Get("Idempotency-Key")
}
```

`R-HDR-4` — W3C Trace Context (`traceparent`); интеграция через OTel SDK:

```go
import "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

// otelhttp.NewMiddleware прокидывает traceparent в context и проставляет заголовки W3C Trace Context
r.Use(otelhttp.NewMiddleware("order-service"))
```

`R-HDR-X1` ❌ Префикс `X-` в кастомных заголовках (RFC 6648 устарел).

---

## 13. Формат ошибок — RFC 9457 Problem Details (`R-ERR-*`)

Полная реализация — в `backend/error-handling/go/error-handling-style-guide.md`. Здесь — REST-специфика.

`R-ERR-1..4` — Problem Details structure: `type`, `title`, `status`, `detail`, `traceId`, `code` UPPER_SNAKE:

```go
type ProblemDetails struct {
    Type     string `json:"type"`
    Title    string `json:"title"`
    Status   int    `json:"status"`
    Detail   string `json:"detail"`
    Code     string `json:"code"`
    TraceID  string `json:"traceId,omitempty"`
}

func writeProblem(w http.ResponseWriter, status int, code, title, detail, traceID string) {
    p := ProblemDetails{
        Type:    "urn:problem:order-service:" + strings.ToLower(strings.ReplaceAll(code, "_", "-")),
        Title:   title,
        Status:  status,
        Detail:  detail,
        Code:    code,
        TraceID: traceID,
    }
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(status)
    json.NewEncoder(w).Encode(p)
}
```

`R-ERR-5..6` — ошибки валидации: `400 VALIDATION_ERROR` + `violations`:

```go
type ValidationProblem struct {
    ProblemDetails
    Violations []Violation `json:"violations"`
}

type Violation struct {
    Field   string `json:"field"`
    Code    string `json:"code"`
    Message string `json:"message"`
}

func writeValidationProblem(w http.ResponseWriter, violations []Violation, traceID string) {
    p := ValidationProblem{
        ProblemDetails: ProblemDetails{
            Type:    "urn:problem:order-service:validation-error",
            Title:   "Validation failed",
            Status:  http.StatusBadRequest,
            Detail:  "Request contains invalid fields",
            Code:    "VALIDATION_ERROR",
            TraceID: traceID,
        },
        Violations: violations,
    }
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(http.StatusBadRequest)
    json.NewEncoder(w).Encode(p)
}
```

Маппинг `go-playground/validator` в `Violation`:

```go
func toViolations(errs validator.ValidationErrors) []Violation {
    out := make([]Violation, 0, len(errs))
    for _, e := range errs {
        out = append(out, Violation{
            Field:   toSnakeField(e.Namespace()),
            Code:    strings.ToUpper(e.Tag()),
            Message: e.Translate(trans),
        })
    }
    return out
}
```

`R-ERR-7..9` — все коды ошибок — константы/enum в коде; каждый эндпоинт документирует возможные ошибки.

`R-ERR-X1` ❌ `Content-Type: application/json` для ошибок.
`R-ERR-X2` ❌ `type: "about:blank"` — теряется машиночитаемая категория; используй URN.
`R-ERR-X3` ❌ HTTP 422 (не в разрешённом списке); валидация → 400.
`R-ERR-X4` ❌ Stack traces, SQL, внутренние пути в теле 500.

---

## 14. Rate limiting (`R-RATE-*`)

`R-RATE-1..3` — `429 Too Many Requests` + `Retry-After` + `RateLimit-*` заголовки.

Rate limiting реализуется в middleware (через gateway, Redis или in-process `golang.org/x/time/rate`):

```go
func RateLimitMiddleware(limiter *rate.Limiter) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            if !limiter.Allow() {
                w.Header().Set("Retry-After", "1")
                w.Header().Set("RateLimit-Limit", "100")
                w.Header().Set("RateLimit-Remaining", "0")
                w.Header().Set("RateLimit-Reset", strconv.FormatInt(time.Now().Add(time.Second).Unix(), 10))
                writeProblem(w, 429, "RATE_LIMIT_EXCEEDED", "Too Many Requests",
                    "Rate limit exceeded, retry after 1 second", traceIDFromCtx(r.Context()))
                return
            }
            next.ServeHTTP(w, r)
        })
    }
}
```

`R-RATE-X1` ❌ `429` без `Retry-After` и `RateLimit-*`.

---

## 15. Загрузка файлов (`R-FILE-*`)

`R-FILE-1..5` — файлы через `POST` с `multipart/form-data`; скачивание через `GET` с `Content-Disposition`:

```go
func uploadProductImage(w http.ResponseWriter, r *http.Request) {
    if err := r.ParseMultipartForm(32 << 20); err != nil { // 32 MB
        httperr.Write(w, r, apperr.NewValidation("invalid multipart form"))
        return
    }
    file, header, err := r.FormFile("file")
    if err != nil {
        httperr.Write(w, r, apperr.NewValidation("missing file field"))
        return
    }
    defer file.Close()

    // validate content type
    buf := make([]byte, 512)
    if _, err := file.Read(buf); err != nil {
        httperr.Write(w, r, apperr.NewValidation("cannot read file"))
        return
    }
    contentType := http.DetectContentType(buf)
    _ = header
    // ... save and return 201 with metadata
}

func downloadProductImage(w http.ResponseWriter, r *http.Request) {
    imageID := chi.URLParam(r, "id")
    // fetch file content ...
    w.Header().Set("Content-Type", "image/jpeg")
    w.Header().Set("Content-Disposition", `attachment; filename="`+imageID+`.jpg"`)
    http.ServeContent(w, r, imageID+".jpg", time.Now(), bytes.NewReader(content))
}
```

---

## 16. Deprecation (`R-DEP-*`)

`R-DEP-1..3` — устаревший эндпоинт помечается в OpenAPI `deprecated: true` + `description` с датой и альтернативой;
в middleware добавляются заголовки `Sunset`, `Deprecation`, `Link`:

```go
func deprecatedMiddleware(sunsetDate string, successorURL string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            w.Header().Set("Sunset", sunsetDate)             // RFC 8594: "Sat, 01 Jan 2026 00:00:00 GMT"
            w.Header().Set("Deprecation", "true")
            w.Header().Set("Link", `<`+successorURL+`>; rel="successor-version"`)
            next.ServeHTTP(w, r)
        })
    }
}

// применение
r.With(deprecatedMiddleware("Sat, 01 Jan 2026 00:00:00 GMT", "/api/v2/orders")).
    Get("/api/v1/orders", listOrdersV1)
```

`R-DEP-X1` ❌ `deprecated: true` в OpenAPI без `Sunset` и даты.

---

## 17. Batch-операции (`R-BATCH-*`)

`R-BATCH-1..5` — `POST /resources/batch` / `POST /resources/batch/{action}`; тело `{"items": [...]}`;
ответ `200 OK` с результатом по каждому элементу + `summary`:

```go
type BatchUpdateOrdersRequest struct {
    Items []BatchOrderItem `json:"items" validate:"required,min=1,max=100"`
}

type BatchOrderItem struct {
    OrderID string `json:"orderId" validate:"required"`
    Status  string `json:"status"  validate:"required"`
}

type BatchResponse[T any] struct {
    Results []BatchResult[T] `json:"results"`
    Summary BatchSummary     `json:"summary"`
}

type BatchResult[T any] struct {
    ID      string          `json:"id"`
    Success bool            `json:"success"`
    Data    *T              `json:"data,omitempty"`
    Error   *ProblemDetails `json:"error,omitempty"`
}

type BatchSummary struct {
    Total   int `json:"total"`
    Success int `json:"success"`
    Failed  int `json:"failed"`
}

func batchUpdateOrders(w http.ResponseWriter, r *http.Request) {
    var req BatchUpdateOrdersRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        httperr.Write(w, r, apperr.NewValidation("invalid request body"))
        return
    }
    if len(req.Items) > 100 {
        writeValidationProblem(w, []Violation{{
            Field: "items", Code: "BATCH_SIZE_EXCEEDED",
            Message: "batch size must not exceed 100",
        }}, traceIDFromCtx(r.Context()))
        return
    }
    // ... process each item
}
```

---

## 18. Длительные операции (async) (`R-ASYNC-*`)

`R-ASYNC-1..4` — паттерн polling: `202 Accepted` + `Location` + `taskId`/`statusUrl`; опрос `GET /api/v1/tasks/{id}`:

```go
type TaskAccepted struct {
    TaskID    string `json:"taskId"`
    Status    string `json:"status"`    // "PENDING"
    StatusURL string `json:"statusUrl"`
}

func exportOrders(w http.ResponseWriter, r *http.Request) {
    taskID := uuid.New().String()
    // launch background goroutine or enqueue job
    go runExport(context.Background(), taskID)

    resp := TaskAccepted{
        TaskID:    taskID,
        Status:    "PENDING",
        StatusURL: "/api/v1/tasks/" + taskID,
    }
    w.Header().Set("Location", resp.StatusURL)
    writeJSON(w, http.StatusAccepted, resp)
}

type TaskStatus struct {
    TaskID    string  `json:"taskId"`
    Status    string  `json:"status"` // PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    ResultURL *string `json:"resultUrl,omitempty"`
    Error     *string `json:"error,omitempty"`
}

// r.Get("/api/v1/tasks/{id}", getTaskStatus)
```

---

## 19. Локализация (`R-LOC-*`)

`R-LOC-1..3` — клиент указывает `Accept-Language`; сервер использует язык по умолчанию (`ru`) если заголовок отсутствует:

```go
func acceptLanguage(r *http.Request) string {
    lang := r.Header.Get("Accept-Language")
    if lang == "" {
        return "ru"
    }
    // разбор BCP 47 тегов: берём первый
    parts := strings.Split(lang, ",")
    if len(parts) > 0 {
        return strings.TrimSpace(strings.Split(parts[0], ";")[0])
    }
    return "ru"
}
```

Локализуются: `detail`/`message` в Problem Details и поле `message` в `Violation`.

`R-LOC-X1` ❌ Локализация enum-кодов (`status`, `code`) и URI — эти поля машиночитаемы, всегда на английском.

---

## 20. OpenAPI-метаданные (`R-OAS-*`)

`R-OAS-1..4` — `operationId` camelCase, `tags` с тегом родительского ресурса, `summary` до 80 символов.

В Go OpenAPI ведётся либо аннотациями `swaggo/swag`, либо отдельным `openapi.yaml`/`openapi.json` рядом с кодом.
Вариант аннотаций:

```go
// createOrder godoc
// @Summary      Create order
// @Tags         Orders
// @Accept       json
// @Produce      json
// @Param        body body CreateOrderRequest true "Order payload"
// @Success      201 {object} OrderResponse
// @Failure      400 {object} ValidationProblem
// @Failure      409 {object} ProblemDetails
// @Failure      500 {object} ProblemDetails
// @Router       /api/v1/orders [post]
// @operationId  createOrder
func createOrder(w http.ResponseWriter, r *http.Request) { ... }
```

При ручном ведении спеки: структуры Go — источник контракта; OpenAPI синхронизируется через ревью до мержа.

`R-OAS-3` — в chi `{id}` в пути допустим для дизайна; в OpenAPI-спеке параметры именуются уникально
(`orderId`, `itemId`) — инструмент требует уникальности имён в рамках операции.

---

## 21. Антипаттерны (`R-*-X*`)

Все `X`-коды выше. Дополнительно специфичные для Go:

| Антипаттерн | Почему плохо | Вместо |
|---|---|---|
| `json.Marshal(v)` без `omitempty` на response-полях | `null` в 2xx-ответе (`R-RSP-X1`) | `omitempty` или явная конструкция ответа |
| `r.URL.Query().Get("page")` без проверки `< 1` | `page=0` нарушает `R-QRY-X2` | парсить с валидацией >= 1 |
| Возврат сырого `err.Error()` из адаптера в `detail` | раскрытие схемы БД (`R-ERR-X4`) | санитизировать через `apperr.KindOf` |
| Разные структуры ошибок в разных хендлерах | нарушение `R-PRIN-2` | единый `httperr.Write` |
| `float64` для денег | потеря точности | `int64` (минорные единицы) |
| Comma-separated query-массивы | `R-QRY-X3` | повтор параметра (`r.Form["status"]`) |

---

## Чеклист подключения к новому сервису (Go)

- [ ] Роутер chi; базовый path — `/api/v1`; kebab-case URL, без trailing slash, action = POST.
- [ ] Единый `httperr.Write` + `Recoverer`-middleware; `apperr.Kind` + типизированные доменные ошибки.
- [ ] `writeJSON` хелпер для всех успешных ответов; `writeProblem` + `writeValidationProblem` для ошибок.
- [ ] Статусы: `201 Created` + `Location` при создании; `204 No Content` при удалении; `202 Accepted` при async.
- [ ] Response-структуры: `omitempty` на необязательных полях; нет `null` в 2xx; коллекция `content`+метаданные.
- [ ] Query-параметры: camelCase, page >= 1, массивы через `r.Form["key"]` (повтор, не CSV).
- [ ] JSON-поля: camelCase `json:"fieldName"`, enum UPPER_SNAKE, `time.Time` ISO 8601, деньги `int64`.
- [ ] `Content-Type: application/problem+json` на всех ошибочных ответах; `code` UPPER_SNAKE, `type` URN.
- [ ] Валидация через `go-playground/validator`; маппинг `ValidationErrors` → `violations`; HTTP 400, не 422.
- [ ] Кастомные заголовки без `X-`; `Idempotency-Key` на неидемпотентных POST; `traceparent` через OTel middleware.
- [ ] Rate limiting: `429` + `Retry-After` + `RateLimit-*` (middleware уровня router или gateway).
- [ ] Deprecation: `Sunset` + `Deprecation` + `Link` заголовки через middleware; `deprecated: true` в OpenAPI.
- [ ] OpenAPI: `operationId` camelCase, `tags`, `summary` на каждой операции; в chi-path `{id}`, в OpenAPI-спеке `{orderId}`.
- [ ] Batch: max 100 задокументировано; `400 BATCH_SIZE_EXCEEDED` при превышении.
- [ ] Async: `202` + `Location` + `taskId`/`statusUrl`; опрос `GET /api/v1/tasks/{id}`.
