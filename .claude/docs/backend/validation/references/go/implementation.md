# Validation — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (коды `R-VLD-WHERE-*`, `R-VLD-STD-*`, `R-VLD-CC-*`, `R-VLD-GRP-*`, `R-VLD-XF-*`, `R-VLD-OAS-*`, `R-VLD-CFG-*`, `R-VLD-MSG-*`).

> **Парадигма.** В Go нет фреймворк-декоратора, который валидирует до входа в хендлер автоматически.
> Граница — chi-middleware или явный вызов `validator.Struct(req)` в начале хендлера до бизнес-логики.
> Библиотека — `github.com/go-playground/validator/v10` (`v10`) — декларативные теги на struct-полях.
> Ошибки валидации → `apperr.Validation` → 400 `application/problem+json` с массивом `errors`
> (cross-ref `error-handling/domain-and-validation-mapping`, `error-handling/references/go/implementation.md`).
> OpenAPI-контракт — **code-first**: struct-теги + godoc → OpenAPI генерируется (напр. `ogen` / `oapi-codegen`).
> Конфиг — `github.com/kelseyhightower/envconfig`, fail-fast при запуске.

---

## 1. Где валидируем — `R-VLD-WHERE-*`

`validation/input-validated-at-edge` — входной DTO валидируется на границе, до Handler. Декодирование + валидация выносятся в хелпер или middleware; хендлер получает уже чистую структуру:

```go
// edge/httpreq/decode.go
func Decode[T any](r *http.Request) (T, error) {
    var req T
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        return req, apperr.NewValidation("некорректный JSON")
    }
    if err := validate.Struct(&req); err != nil {
        return req, toValidationError(err)
    }
    return req, nil
}

// edge/order/handler.go
func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    req, err := httpreq.Decode[CreateOrderRequest](r)
    if err != nil {
        httperr.Write(w, r, err)
        return
    }
    // Handler — только бизнес-логика
    result, err := h.uc.Handle(r.Context(), toCommand(req))
    if err != nil {
        httperr.Write(w, r, err)
        return
    }
    render.JSON(w, http.StatusCreated, result)
}
```

`validation/config-validated-at-startup` — конфиг валидируется fail-fast на старте через `envconfig.Process` + `validate.Struct`:

```go
// config/config.go
type Config struct {
    DatabaseURL string        `envconfig:"DATABASE_URL" required:"true"`
    HTTPTimeout time.Duration `envconfig:"HTTP_TIMEOUT" default:"5s"`
    Payment     PaymentConfig
}

func Load() (*Config, error) {
    var cfg Config
    if err := envconfig.Process("APP", &cfg); err != nil {
        return nil, fmt.Errorf("config: %w", err)
    }
    if err := validate.Struct(&cfg); err != nil {
        return nil, fmt.Errorf("config validate: %w", err)
    }
    return &cfg, nil
}
```

`validation/domain-invariants-in-aggregate` — доменные инварианты — в агрегате (`Order.Create(...)` возвращает `*InsufficientFundsError`), не в `validator`-тегах (cross-ref `R-AGG-*`, `error-handling/domain-exception-named-by-meaning`).

`validation/nested-validated-recursively` — nested-struct валидируется рекурсивно тегом `validate:"required,dive"` или через `validate.Struct` на вложенном поле; `validator/v10` рекурсивно обходит `dive` для слайсов:

```go
type CreateOrderRequest struct {
    CustomerID string             `json:"customer_id" validate:"required,uuid4"`
    Items      []OrderItemRequest `json:"items"       validate:"required,min=1,dive"`
}

type OrderItemRequest struct {
    ProductID string `json:"product_id" validate:"required,uuid4"`
    Qty       int    `json:"qty"        validate:"required,min=1"`
}
```

`validation/input-validated-at-edge` ❌ ручные if-проверки в Handler вместо struct-тегов или хелпера:

```go
// AVOID
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateOrderRequest
    json.NewDecoder(r.Body).Decode(&req)
    if req.CustomerID == "" {
        http.Error(w, "customer_id required", 400)
        return
    }
    // ...
}
```

`validation/no-revalidation-after-edge` ❌ повторный `validate.Struct` UseCase-команды после того, как DTO уже провалидирован — команда уже чистая.

`validation/domain-invariants-in-aggregate` ❌ `validator`-теги на полях доменного агрегата — агрегат гарантирует инвариант в конструкторе/методах, не через struct-теги.

---

## 2. Стандартные constraints — `R-VLD-STD-*`

`validation/standard-constraints-preferred` — required vs optional через теги. Pointer-тип (`*string`) — допускает отсутствие поля; `validate:"required"` — не-пустое:

```go
type UpdateProductRequest struct {
    Name  string  `json:"name"  validate:"required,min=1,max=200"` // обязательно
    Note  *string `json:"note"`                                     // опционально, nil = не задан
}
```

`validation/standard-constraints-preferred` — размеры строк — `min=N,max=M`; числа — `min=N,max=M` (для int) или `gt=0,lte=1000000`:

```go
type CreateProductRequest struct {
    Name     string `json:"name"   validate:"required,min=1,max=200"`
    PriceCop int64  `json:"price"  validate:"required,gt=0,lte=100000000"` // в копейках
    Stock    int    `json:"stock"  validate:"min=0,max=999999"`
}
```

`validation/standard-constraints-preferred` — формат через встроенные теги `validator/v10`, не самописный regex для известных форматов:

```go
type CustomerRequest struct {
    Email string `json:"email" validate:"required,email"`
    Phone string `json:"phone" validate:"required,e164"`    // E.164 — встроен в v10
    Site  string `json:"site"  validate:"omitempty,url"`
}
```

`validation/standard-constraints-preferred` — время. `time.Time` (через кастомный decoder) + тег `validate:"required"` + кастомный тег (см. §3) для `future`/`past`:

```go
type CreateBookingRequest struct {
    StartsAt time.Time `json:"starts_at" validate:"required,future"` // future — custom (§3)
    EndsAt   time.Time `json:"ends_at"   validate:"required"`
}
```

`validation/standard-constraints-preferred` — деньги — `int64` (копейки/минорные единицы) или `github.com/shopspring/decimal`, не `float64`; числовые constraints — числовыми тегами, не строковыми:

```go
type PaymentRequest struct {
    AmountCop int64 `json:"amount_cop" validate:"required,gt=0"` // копейки, не float
}
```

`validation/no-false-or-composite-constraints` ❌ `validate:"required"` на non-pointer поле типа `int` — значение `0` всегда провалит required; для числа без нуля используй `validate:"gt=0"`.

`validation/standard-constraints-preferred` ❌ `validate:"regexp=^[a-zA-Z0-9._%+\\-]+@..."` вместо встроенного `email`.

`validation/no-false-or-composite-constraints` ❌ один «супер-тег» через кастомный валидатор, объединяющий несколько стандартных проверок — читаемость теряется; лучше перечислять явно.

---

## 3. Custom constraints — `R-VLD-CC-*`

`validation/custom-constraint-is-reusable` / `validation/custom-constraint-is-reusable` — переиспользуемый constraint регистрируется как именованный тег на глобальном/разделяемом `*validator.Validate`, в общем пакете `internal/validation/`:

```go
// internal/validation/tags.go
package validation

import (
    "regexp"
    "time"

    "github.com/go-playground/validator/v10"
)

var ruPhoneRE = regexp.MustCompile(`^\+7\d{10}$`)

func RegisterCustomTags(v *validator.Validate) {
    v.RegisterValidation("ru_phone", validateRuPhone)
    v.RegisterValidation("future", validateFuture)
    v.RegisterValidation("vat_number", validateVatNumber)
}

func validateRuPhone(fl validator.FieldLevel) bool {
    s, ok := fl.Field().Interface().(string)
    return ok && ruPhoneRE.MatchString(s)
}

func validateFuture(fl validator.FieldLevel) bool {
    t, ok := fl.Field().Interface().(time.Time)
    return ok && t.After(time.Now())
}

func validateVatNumber(fl validator.FieldLevel) bool {
    s, ok := fl.Field().Interface().(string)
    if !ok { return false }
    return len(s) == 10 || len(s) == 12 // ИНН 10 или 12 цифр
}
```

`validation/custom-constraint-named-by-domain` — имя тега по доменному термину без префиксов: `ru_phone`, `vat_number`, `future` — не `valid_phone`, `check_vat`, `is_future`.

`validation/custom-constraint-null-safe` — custom-тег вызывается только на не-nil (не-пустом) значении: для pointer-полей добавляй `omitempty` перед кастомным тегом, иначе комбинируй с `required`:

```go
type CustomerRequest struct {
    Phone    string  `json:"phone"    validate:"required,ru_phone"`    // required + custom
    AltPhone *string `json:"alt_phone" validate:"omitempty,ru_phone"`  // опционально — пропустить nil
}
```

`validation/constraint-is-stateless` — валидатор — stateless: `validateRuPhone` зависит только от значения. Если нужна БД-проверка (уникальность) — это не валидация контракта, а бизнес-правило в агрегате/handler (cross-ref `validation/domain-invariants-in-aggregate`).

`validation/custom-constraint-null-safe` ❌ кастомный валидатор паникует или возвращает некорректный результат при нулевом значении — `FieldLevel.Field()` может вернуть zero value; guard через type assertion с `ok`.

`validation/custom-constraint-is-reusable` ❌ регистрация кастомного тега inline в файле DTO — не находится grep-ом, не переиспользуется.

`validation/custom-constraint-is-reusable` ❌ вся логика нескольких правил в одном «мега-теге» — лучше отдельные именованные теги, каждый описывает одно правило.

---

## 4. Сценарии (groups) — `R-VLD-GRP-*`

`validation/scenario-groups-are-narrow` — `validator/v10` поддерживает группы через структурные теги нотации `groups:` (нестандартная фича), но идиоматичнее в Go — **отдельные struct-типы** для разных сценариев:

```go
// PREFER — разные типы для create/update
type CreateOrderRequest struct {
    CustomerID string             `json:"customer_id" validate:"required,uuid4"`
    Items      []OrderItemRequest `json:"items"       validate:"required,min=1,dive"`
}

type DraftOrderRequest struct {
    CustomerID string             `json:"customer_id" validate:"omitempty,uuid4"` // draft — все поля опциональны
    Items      []OrderItemRequest `json:"items"       validate:"omitempty,dive"`
}
```

`validation/scenario-marker-documented` — если нужна одна struct с разными сценариями (редко оправдано), используй `validate.StructCtx` + `ctx`-флаг через кастомный тег с доступом к контексту через `FieldLevel.Param()`.

`validation/scenario-groups-are-narrow` ❌ одна struct с «режимами» через boolean-поле или context-флаг — лучше два явных типа.

`validation/scenario-groups-are-narrow` ❌ struct, обслуживающая 3+ разных сценариев — разбить на отдельные типы.

---

## 5. Cross-field валидация — `R-VLD-XF-*`

`validation/cross-field-rules-on-object` — правило с 2+ полями одного struct — кастомный struct-level validator, зарегистрированный через `v.RegisterStructValidation`:

```go
// internal/validation/cross_field.go

func RegisterStructValidations(v *validator.Validate) {
    v.RegisterStructValidation(validateDateRange, DateRangeRequest{})
    v.RegisterStructValidation(validatePasswordsMatch, ChangePasswordRequest{})
}

func validateDateRange(sl validator.StructLevel) {
    r, ok := sl.Current().Interface().(DateRangeRequest)
    if !ok { return }
    if !r.EndsAt.IsZero() && !r.StartsAt.IsZero() && r.EndsAt.Before(r.StartsAt) {
        sl.ReportError(r.EndsAt, "ends_at", "EndsAt", "date_range", "")
    }
}

func validatePasswordsMatch(sl validator.StructLevel) {
    r, ok := sl.Current().Interface().(ChangePasswordRequest)
    if !ok { return }
    if r.Password != r.PasswordConfirm {
        sl.ReportError(r.PasswordConfirm, "password_confirm", "PasswordConfirm", "passwords_match", "")
    }
}
```

`validation/cross-field-rules-on-object` — имя тега/функции описывает правило: `date_range`, `passwords_match` — не `validate_request`, `check_fields`.

`validation/cross-field-rules-on-object` ❌ одноразовая cross-field проверка в handler-коде вместо `RegisterStructValidation` — если правило встречается в нескольких DTO, его надо вынести.

`validation/cross-field-rules-on-object` ❌ cross-field проверка в Handler до dispatch — место на DTO через struct-level validator.

---

## 6. Контракт-схема — `R-VLD-OAS-*`

`validation/single-source-of-truth` — **code-first в Go-UCP**: struct-теги + комментарии — источник правды; OpenAPI генерируется инструментом (напр. `oapi-codegen` или ручной spec, обновляемый совместно). Правило валидации живёт в struct-теге, в одном месте.

`validation/controller-implements-generated-contract` — если используется contract-first (`oapi-codegen` генерирует DTO из YAML), то:
- сгенерированные типы расширяются тегами через `x-go-type` / `x-oapi-codegen-extra-tags`;
- validate-теги прописываются в YAML-extension, не в сгенерированный файл вручную.

`validation/no-revalidation-after-edge` — после маппинга в UseCase-команду повторная валидация не делается; команда конструируется из уже чистого DTO:

```go
func toCreateOrderCommand(req CreateOrderRequest) order.CreateCommand {
    return order.CreateCommand{          // pure mapping, no validation
        CustomerID: req.CustomerID,
        Items:      toItems(req.Items),
    }
}
```

`validation/generated-artifacts-immutable` ❌ ручная правка сгенерированных файлов (при contract-first: `oapi-codegen` → сгенерированный DTO) — затрётся при регенерации.

`validation/single-source-of-truth` ❌ `validate.Struct(req)` и при этом ещё ручная `if req.Amount <= 0` проверка того же — дублирование источника правды.

`validation/controller-implements-generated-contract` ❌ inbound-данные как `map[string]any` / `json.RawMessage` без декодирования в типизированный struct — контракт не выражен.

---

## 7. Конфигурация — `R-VLD-CFG-*`

`validation/config-validated-at-startup` / `validation/config-validated-at-startup` — конфиг через `envconfig` с обязательными полями (`required:"true"`) и типобезопасными полями; `validate.Struct` добавляет дополнительные ограничения:

```go
// config/config.go
type Config struct {
    DatabaseURL string        `envconfig:"DATABASE_URL" required:"true"`
    RedisAddr   string        `envconfig:"REDIS_ADDR"   required:"true" validate:"hostname_port"`
    HTTPTimeout time.Duration `envconfig:"HTTP_TIMEOUT" default:"5s"    validate:"min=1s,max=60s"`
    Payment     PaymentConfig
}

type PaymentConfig struct {                          // R-VLD-CFG-4 — nested валидируется
    BaseURL    string `envconfig:"PAYMENT_BASE_URL" required:"true" validate:"url"`
    APIKey     string `envconfig:"PAYMENT_API_KEY"  required:"true" validate:"min=32"`
    TimeoutSec int    `envconfig:"PAYMENT_TIMEOUT"  default:"10"    validate:"min=1,max=120"`
}
```

При старте (`main.go`):

```go
cfg, err := config.Load()
if err != nil {
    slog.Error("invalid config", "error", err)
    os.Exit(1)                                      // fail-fast, R-VLD-WHERE-2
}
```

`validation/config-validated-at-startup` ❌ конфиг-struct без `required:"true"` / `validate`-тегов — поднялся с пустым `DatabaseURL`.

`validation/config-validated-at-startup` ❌ `os.Getenv("DATABASE_URL")` для required-конфига — без валидации и типизации; через `envconfig`.

---

## 8. Сообщения и i18n — `R-VLD-MSG-*`

`validation/message-in-user-language` / `validation/message-in-user-language` — пользовательские тексты ошибок — на русском с интерполяцией значений.
`validator/v10` возвращает `ValidationErrors` (слайс `FieldError`); маппинг тегов → читаемый текст — в хелпере:

```go
// internal/validation/messages.go
func Localize(fe validator.FieldError) string {
    switch fe.Tag() {
    case "required":
        return fmt.Sprintf("поле «%s» обязательно", fieldLabel(fe.Field()))
    case "min":
        return fmt.Sprintf("минимальная длина — %s символов", fe.Param())
    case "max":
        return fmt.Sprintf("максимальная длина — %s символов", fe.Param())
    case "email":
        return "некорректный адрес электронной почты"
    case "e164":
        return "телефон должен быть в формате +79XXXXXXXXX"
    case "ru_phone":
        return "телефон должен быть в формате +7XXXXXXXXXX"
    case "uuid4":
        return fmt.Sprintf("поле «%s» должно быть корректным UUID", fieldLabel(fe.Field()))
    case "gt":
        return fmt.Sprintf("значение должно быть больше %s", fe.Param())
    case "future":
        return "дата должна быть в будущем"
    case "date_range":
        return "дата окончания не может быть раньше даты начала"
    case "passwords_match":
        return "пароли не совпадают"
    default:
        return fmt.Sprintf("некорректное значение поля «%s»", fieldLabel(fe.Field()))
    }
}
```

`validation/message-in-user-language` — при необходимости i18n: ключи сообщений передаются в локализатор (напр. `golang.org/x/text/message`), не хардкодятся строками.

`validation/message-in-user-language` ❌ `fe.Error()` напрямую в ответ — английский технический текст (`Key: 'CreateOrderRequest.CustomerID' Error:Field validation for 'CustomerID' failed on the 'required' tag`).

`validation/message-in-user-language` ❌ технические термины в тексте (`Field customer_id failed required validation`); читаемое поле из `fieldLabel`.

`validation/no-duplicated-messages` ❌ одинаковый статичный текст на каждом поле без контекста — используй `fe.Field()` и `fe.Param()`.

### Маппинг ValidationError → 400 problem+json

Тип ошибки — `apperr.ValidationError` (из `core/apperr`, cross-ref `error-handling/go`);
`internal/validation/` предоставляет только хелпер маппинга тегов → `apperr.FieldError`:

```go
// internal/validation/error.go
func toValidationError(err error) *apperr.ValidationError {
    var ve validator.ValidationErrors
    if !errors.As(err, &ve) {
        return apperr.NewValidation("некорректные данные запроса")
    }
    fields := make([]apperr.FieldError, len(ve))
    for i, fe := range ve {
        fields[i] = apperr.FieldError{
            Field:   fe.Field(),
            Code:    fe.Tag(),
            Message: Localize(fe),
        }
    }
    return &apperr.ValidationError{Message: "validation failed", Fields: fields}
}
```

Edge-renderer (`httperr.Write`) при `apperr.KindOf(err) == apperr.Validation` отдаёт 400 + `errors`-массив:

```go
// edge/httperr/render.go (расширение из требований `error-handling/*`)
func Write(w http.ResponseWriter, r *http.Request, err error) {
    var ve *apperr.ValidationError
    if errors.As(err, &ve) {
        writeValidationProblem(w, ve.Fields)
        return
    }
    // ... общий path
}

func writeValidationProblem(w http.ResponseWriter, fields []apperr.FieldError) {
    body := map[string]any{
        "type":   "urn:problem:<service>:validation-error", // rest-api/error-type-is-stable-category: конкретный URN, не about:blank
        "title":  "Validation failed",
        "status": 400,
        "errors": fields,
    }
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(400)
    _ = json.NewEncoder(w).Encode(body)
}
```

---

## Чеклист подключения к новому сервису (Go)

- [ ] `internal/validation/` — пакет с `*validator.Validate` (singleton), `RegisterCustomTags`, `RegisterStructValidations`, `Localize`, `toValidationError` (возвращает `*apperr.ValidationError{Fields: []apperr.FieldError}`); собственного типа `ValidationError` нет
- [ ] `httpreq.Decode[T]` — decode + `validate.Struct` + `toValidationError`; хендлер получает уже чистый struct
- [ ] `config.Load()` — `envconfig.Process` + `validate.Struct`; `os.Exit(1)` при ошибке (fail-fast)
- [ ] Required-поля конфига — `required:"true"` в envconfig-теге, без default; nested-config валидируется рекурсивно
- [ ] Входные DTO: `validate:"required"` на обязательных полях; pointer-тип + `omitempty` — на опциональных
- [ ] Деньги — `int64` (копейки) или `shopspring/decimal`, не `float64`; тег `gt=0` вместо `required` для числа-не-ноль
- [ ] Кастомные теги: именованные (`ru_phone`, `vat_number`, `future`), stateless, без паники на zero-value, зарегистрированы в `RegisterCustomTags`
- [ ] Cross-field правила — `RegisterStructValidation` с говорящим именем правила в `ReportError`
- [ ] Нет ручной input-валидации в Handler; нет дублирования `validate.Struct` + `if`-проверки на то же поле
- [ ] Доменные инварианты — в агрегате (возвращают `*SomeDomainError` с `Kind() apperr.Domain`), не в struct-тегах
- [ ] `httperr.Write` расширен: `errors.As(err, &apperr.ValidationError)` → 400 + `errors`-массив + `"type":"urn:problem:<service>:validation-error"` (problem+json)
- [ ] Тексты ошибок — на русском через `Localize(fe)`; нет `fe.Error()` напрямую в ответ
- [ ] Нет `os.Getenv(...)` для required-конфига; нет inbound-данных как `map[string]any`
