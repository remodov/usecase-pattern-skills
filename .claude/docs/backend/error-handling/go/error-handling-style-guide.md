# Error Handling — Go Style Guide (net/http + chi)

Реализация язык-нейтрального контракта `../error-handling-rules.md` (`R-ERR-*`) на Go-стеке (stdlib `net/http` + chi).
Коды правил — общие с Java/Python/Node; здесь — как они выглядят в Go-сервисе.

> **Парадигма.** В Go **нет исключений**: ошибки — это значения (`func() (T, error)`), классифицируются через
> `errors.Is`/`errors.As`, контекст добавляется обёрткой `fmt.Errorf("...: %w", err)`. `panic`/`recover` — **не**
> для нормального потока, только для невосстановимых программистских ошибок (+ recover-middleware как catch-all).
> Поэтому контракт читается так: «throw» → `return err`; «edge-handler» → middleware, мапящий ошибку в ответ;
> «иерархия исключений» → типизированные ошибки + категория (`Kind`), распознаваемая на edge через `errors.As`.

Структура слоёв UCP: `core/` (домен), `adapters/out/*` (HTTP-клиенты), edge (chi-роутер + error-middleware).

---

## 1. Иерархия ошибок — `R-ERR-HIER-*`

`R-ERR-HIER-1` / `R-ERR-HIER-2` — 4 категории. Идиоматично: маркер-метод `Kind()` + типизированные структуры
(вместо иерархии классов). Базовая категория и хелпер классификации:

```go
// core/apperr/apperr.go
package apperr

type Kind int

const (
	Domain Kind = iota + 1 // 409/422, no-retry
	Validation             // 400, no-retry
	Integration            // 502/503/504, retry-safe
	Technical              // 500, retry-возможно
)

// Категорийный маркер; доменные/интеграционные ошибки его реализуют.
type Categorized interface{ Kind() Kind }

// KindOf разворачивает цепочку %w и достаёт категорию; по умолчанию — Technical.
func KindOf(err error) Kind {
	var c Categorized
	if errors.As(err, &c) {
		return c.Kind()
	}
	return Technical
}

// FieldError — одна невалидная позиция в запросе.
type FieldError struct {
	Field   string // имя поля (JSON-нотация)
	Code    string // машинный код правила (required, min, uuid4, …)
	Message string // читаемый текст на языке сервиса
}

// ValidationError — ошибка валидации входного контракта; Kind() == Validation → HTTP 400.
type ValidationError struct {
	Message string
	Fields  []FieldError
}

func (e *ValidationError) Error() string  { return e.Message }
func (e *ValidationError) Kind() Kind     { return Validation }

// NewValidation создаёт ValidationError без детализации по полям (некорректный JSON и т.п.).
func NewValidation(msg string) *ValidationError {
	return &ValidationError{Message: msg}
}
```

`R-ERR-HIER-3` — имя по бизнес-смыслу; типизированная структура с контекстом (`R-ERR-HIER-5`):

```go
// core/order/errors.go
type InsufficientFundsError struct {
	CustomerID         string
	Requested, Available int64 // деньги — минорные единицы (int64) или shopspring/decimal, не float64
}

func (e *InsufficientFundsError) Error() string {
	return fmt.Sprintf("insufficient funds: customer=%s requested=%d available=%d",
		e.CustomerID, e.Requested, e.Available)
}
func (e *InsufficientFundsError) Kind() apperr.Kind { return apperr.Domain }
```

`R-ERR-HIER-4` — интеграционные ошибки с префиксом системы, в своём адаптере:

```go
// adapters/out/payment/errors.go
type GatewayError struct{ Op string; Err error }
func (e *GatewayError) Error() string      { return "payment gateway: " + e.Op + ": " + e.Err.Error() }
func (e *GatewayError) Unwrap() error       { return e.Err }
func (e *GatewayError) Kind() apperr.Kind   { return apperr.Integration }
```

`R-ERR-HIER-X1` ❌ Возврат «голой» строки-ошибки туда, где edge ждёт категорию: `errors.New("oops")` / `fmt.Errorf("oops")` без типа/категории → попадёт в Technical/500. Для бизнес-правила — типизированная ошибка с `Kind() Domain`.

`R-ERR-HIER-X2` ❌ `panic(...)` для бизнес-правила. panic — только невосстановимое (programmer error); бизнес-правило → доменная ошибка-значение; нарушение инварианта агрегата → ловит unit-тест.

---

## 2. Где возвращать, где обрабатывать — `R-ERR-WHERE-*`

`R-ERR-WHERE-1` — `return err` где нужно; добавляй контекст обёрткой (`fmt.Errorf("load order %s: %w", id, err)`), сохраняя `%w` для `errors.As`. domain handler → доменная ошибка, out-adapter → интеграционная.

`R-ERR-WHERE-2` — обработка только в трёх местах:

**a) Edge — chi error-middleware + единый renderer.** Хендлеры возвращают ошибку «вверх» (через тонкий адаптер), middleware мапит:

```go
// edge/httperr/render.go
func Write(w http.ResponseWriter, r *http.Request, err error) {
	status, title := mapKind(apperr.KindOf(err))                 // R-ERR-MAP-1..4
	logByKind(r.Context(), err)                                  // R-ERR-LOG-* (один раз, здесь)
	appErrorsTotal.WithLabelValues(kindLabel(err), typeName(err)).Inc() // R-ERR-OBS-1
	writeProblem(w, status, title, sanitize(err), traceID(r))    // application/problem+json
}

// edge/middleware/recover.go — catch-all для panic → 500 (R-ERR-MAP-5)
func Recoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if v := recover(); v != nil {
				slog.ErrorContext(r.Context(), "panic recovered", "panic", v, "stack", string(debug.Stack()))
				appErrorsTotal.WithLabelValues("unexpected", "panic").Inc()
				writeProblem(w, 500, "Internal Server Error", "internal error", traceID(r))
			}
		}()
		next.ServeHTTP(w, r)
	})
}
```

**b) Integration boundary — HTTP-клиент** мапит низкоуровневое в port-specific:

```go
// adapters/out/payment/client.go
func (c *Client) Register(ctx context.Context, cmd RegisterCommand) (RegisterResult, error) {
	resp, err := c.do(ctx, cmd)
	if err != nil {                                              // транспорт/timeout
		return RegisterResult{}, &GatewayError{Op: "register", Err: err}
	}
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {         // 4xx → domain, R-ERR-RETRY-2
		return RegisterResult{}, &InvalidPaymentRequestError{OrderID: cmd.OrderID}
	}
	if resp.StatusCode >= 500 {
		return RegisterResult{}, &GatewayError{Op: "register", Err: fmt.Errorf("status %d", resp.StatusCode)}
	}
	return toDomain(resp), nil
}
```

**c) Резильянс-обёртка** — retry/CB вокруг adapter-вызова (см. §5).

`R-ERR-WHERE-3` — в UseCase Handler / Domain Service / Aggregate **никакого `recover()`**; ошибки только возвращаются вверх.

`R-ERR-WHERE-X1` ❌ Проглатывание: `if err != nil { slog.Error(...); return nil }`, пустой `if err != nil {}`, или `_ = doThing()` (игнор возвращённой ошибки). Главный силент-фейл (линтер `errcheck` это ловит).

`R-ERR-WHERE-X2` ❌ `return errors.New(err.Error())` / `fmt.Errorf("%v", err)` — теряется цепочка и тип (нельзя `errors.As`). Всегда `%w`: `fmt.Errorf("...: %w", err)`.

`R-ERR-WHERE-X3` ❌ `return SomeStruct{}, nil` при фактической ошибке — возврат zero-value с `nil`-ошибкой прячет проблему.

---

## 3. Mapping в ProblemDetails — `R-ERR-MAP-*`

RFC 9457 вручную. Renderer ставит `Content-Type: application/problem+json`:

```go
func writeProblem(w http.ResponseWriter, status int, title, detail, traceID string) {
	body := map[string]any{"type": "about:blank", "title": title, "status": status, "detail": detail}
	if traceID != "" { body["traceId"] = traceID }
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func mapKind(k apperr.Kind) (int, string) {
	switch k {
	case apperr.Domain:      return 422, "Operation cannot be completed" // или 409, R-ERR-MAP-1
	case apperr.Validation:  return 400, "Validation failed"             // R-ERR-MAP-2
	case apperr.Integration: return 502, "Upstream error"                // 503/504 по подтипу, R-ERR-MAP-3
	default:                 return 500, "Internal Server Error"         // Technical, R-ERR-MAP-4
	}
}
```

`R-ERR-MAP-1` — Domain → 409/422; `type` = URL на код ошибки в `docs/spec/errors/`; контекст — extension-поля (из типизированной ошибки через `errors.As`).
`R-ERR-MAP-2` — Validation → 400 + `errors`-массив (ошибки `go-playground/validator` привести к этой форме).
`R-ERR-MAP-3` — Integration → 502/503/504 (503 при CB-open, 504 при timeout — по подтипу/`errors.Is(err, context.DeadlineExceeded)`). Сырое тело внешки в `detail` не вкладывать (PII).
`R-ERR-MAP-4` — Technical/unknown → 500, минимум в response (`AUTH-18`).
`R-ERR-MAP-5` — recover-middleware (panic) → 500, ERROR-лог + stack.

`R-ERR-MAP-X1` ❌ HTTP 200 при ошибке с `{"success": false}`.
`R-ERR-MAP-X2` ❌ stack/`%+v` в `detail` — утечка; только в логи.
`R-ERR-MAP-X3` ❌ `err.Error()` низкоуровневой ошибки в `detail` без санитизации (`pq: relation "orders" does not exist`) — раскрытие схемы.

---

## 4. Логирование ошибок — `R-ERR-LOG-*`

Логгер — `log/slog` (stdlib, JSON-handler в проде), correlation через `context.Context`.

`R-ERR-LOG-1` — Domain → `slog.WarnContext` (ожидаемо, не баг).
`R-ERR-LOG-2` — Integration → `Warn` если CB закрыт, `Error` если CB открылся.
`R-ERR-LOG-3` — Technical и panic → `Error` + stack + контекст.
`R-ERR-LOG-4` — логируем один раз — в edge-renderer/recover-middleware.

`R-ERR-LOG-X1` ❌ `slog.Error(...); return err` — двойное логирование (залогируют ещё раз на edge). Либо обработай, либо проброс.
`R-ERR-LOG-X2` ❌ `slog.Error(err.Error())` строкой — потеря структуры; передавай ошибку атрибутом: `slog.ErrorContext(ctx, "msg", "error", err)`.

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Retry — `avast/retry-go` или ручной цикл с backoff; CB — `sony/gobreaker`. На out-adapter, не в домене.

`R-ERR-RETRY-1` — по категории: Domain/Validation — никогда; Integration — retry-safe при идемпотентности (`AUTH-19`); Technical — обычно retry после latency.

```go
err := retry.Do(
	func() error { return c.payment.Register(ctx, cmd) },
	retry.RetryIf(func(err error) bool {                         // только Integration, R-ERR-RETRY-1/3
		var g *GatewayError
		return errors.As(err, &g)                                // InvalidPaymentRequestError (4xx) НЕ ретраится
	}),
	retry.Attempts(3), retry.DelayType(retry.BackOffDelay),
)
```

`R-ERR-RETRY-2` — HTTP 4xx от внешней системы — не retry; → port-specific (`InvalidPaymentRequestError`), edge отдаёт 422.
`R-ERR-RETRY-3` — 5xx и timeout — retry-safe только при идемпотентности; без `Idempotency-Key` на write — `R-RES-RE-X1`.

`R-ERR-RETRY-X1` ❌ retry вокруг edge-хендлера — он вне retry-цикла.

---

## 6. Errors-as-values vs panic — `R-ERR-RESULT-*`

В Go возврат `(T, error)` — **норма языка**, а не «Result-обёртка». Поэтому раздел читается инверсно:

`R-ERR-RESULT-1` — ошибки как значения — обязательны; `panic` допустим только для невосстановимых программистских ошибок (nil-map write, индекс за границей в инварианте), не для ожидаемых сбоев.
`R-ERR-RESULT-2` — в цепочке UseCase Handler → Domain → Adapter — возврат `error`, не `panic` как «исключение» через границы пакетов.
`R-ERR-RESULT-X1` ❌ `panic/recover` как механизм control-flow между слоями (имитация try/catch) — нарушение идиомы; recover — только в edge-middleware как backstop.

---

## 7. Observability — `R-ERR-OBS-*`

`R-ERR-OBS-1` — метрика `app_errors_total` через `prometheus/client_golang`:

```go
var appErrorsTotal = promauto.NewCounterVec(
	prometheus.CounterOpts{Name: "app_errors_total", Help: "Application errors"},
	[]string{"type", "exception"},
)
```

`R-ERR-OBS-2` — span на ошибку помечается `Error` (OpenTelemetry):

```go
span.RecordError(err)
span.SetStatus(codes.Error, err.Error())
```

`R-ERR-OBS-3` — алёрты на необычные паттерны (рост `unexpected` → баг; `integration` → деградация внешки; `domain` для одного кода → изменилось бизнес-условие; `validation` рост → клиент сломал контракт).

`R-ERR-OBS-X1` ❌ алёрт «любая ошибка в логах» — Domain нормально частая; алёртить только на `unexpected`/`technical`.

---

## Чеклист подключения к новому сервису (Go / net/http + chi)

- [ ] `core/apperr` с `Kind` + `Categorized`-маркером + `KindOf(err)` + `ValidationError{Message,Fields []FieldError}` + `NewValidation(msg)`
- [ ] Доменные ошибки — типизированные структуры с контекстом и `Kind() Domain`, имена по бизнес-смыслу
- [ ] Единый edge-renderer (`httperr.Write`) + `Recoverer`-middleware (panic → 500)
- [ ] Integration: HTTP-клиент мапит транспорт/4xx/5xx → port-specific (`%w`-обёртка)
- [ ] Никаких `recover()` в core; ошибки возвращаются вверх с `%w`-контекстом
- [ ] `errcheck` + `errorlint` в линтере (ловят проглоченные ошибки и `%v` вместо `%w`)
- [ ] `retry-go` только на идемпотентных Integration-вызовах; `RetryIf` по `errors.As` на Integration-типе
- [ ] `app_errors_total{type,exception}` (client_golang); `span.RecordError` на ошибке
- [ ] `slog`: domain=Warn, technical/panic=Error; PII не в логах (`AUTH-16`)
- [ ] `application/problem+json` на всех error-response
- [ ] Деньги — `int64` (минорные единицы) или `shopspring/decimal`, не `float64`
- [ ] Spec в `docs/spec/errors/` — каждое доменное правило имеет карточку
```
