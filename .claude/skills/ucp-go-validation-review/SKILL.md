---
name: ucp-go-validation-review
lang: go
description: Ревью валидации входа в Go-сервисе (net/http + chi) по UCP (коды R-VLD-*) — go-playground/validator v10 struct-теги на границе, httpreq.Decode, envconfig fail-fast, custom-теги и cross-field RegisterStructValidation, Localize → 400 problem+json.
when_to_use: Изменения в *request*.go, *dto*.go, internal/validation/, config/, httpreq/, edge/ или любом коде с validator.Struct / envconfig.Process.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью валидации (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/validation/validation-rules.md`
(`R-VLD-*`, коды едины с Java/Python) и его **Go-реализации** `backend/validation/go/validation-style-guide.md`.
Помни парадигму: в Go нет декоратора-магии — граница это `httpreq.Decode[T]` (decode + `validate.Struct`) или
chi-middleware; `go-playground/validator/v10` — декларативные теги на struct-полях; конфиг — `envconfig` + fail-fast.

## Зависимости

- **`.claude/docs/backend/validation/validation-rules.md`** — общий контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/go/validation-style-guide.md`** — Go-реализация (validator/v10, httpreq.Decode, envconfig, RegisterCustomTags, RegisterStructValidation, Localize).
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-MAP-2`), `backend/ddd-tactical/ddd-tactical-rules.md` (инварианты ≠ валидация).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-VLD-WHERE-X1`), не префикс.

2. **Скоп.** `**/*request*.go`, `**/*dto*.go`, `internal/validation/`, `config/`, `edge/httpreq/`, `git diff` на `.go`.
   **`Grep`:** `if req\.` (ручные проверки в handler), `validate.Struct` вне `httpreq.Decode`, `os.Getenv` для конфига, `map\[string\]any` как inbound, `fe.Error()` в ответе.

3. **Прогон по подгруппам.**

   ### `R-VLD-WHERE-*`
   - `httpreq.Decode[T]` (decode + `validate.Struct` + `toValidationError`) вызывается первым в handler? — `R-VLD-WHERE-1`.
   - Конфиг через `envconfig.Process` + `validate.Struct` в `config.Load()`, `os.Exit(1)` при ошибке? — `R-VLD-WHERE-2`.
   - Доменные инварианты в конструкторе агрегата (возвращают типизированную ошибку с `Kind() apperr.Domain`), не в `validate`-тегах? — `R-VLD-WHERE-3`.
   - Nested-struct с тегом `validate:"required,dive"` или явным `validate.Struct` на вложенном поле? — `R-VLD-WHERE-4`.
   - Ручные `if req.Field == ""` / `if req.Amount < 0` в Handler вместо тегов — `R-VLD-WHERE-X1` (критично).
   - `validate.Struct(cmd)` после маппинга уже провалидированного DTO в команду — `R-VLD-WHERE-X2`.
   - `validate`-теги на полях доменного агрегата — `R-VLD-WHERE-X4`.

   ### `R-VLD-STD-*`
   - Pointer-тип (`*string`) + `omitempty` для опционального поля; `validate:"required"` на не-пустых? — `R-VLD-STD-1`.
   - Строки — `min=N,max=M`; числа — `gt=0,lte=M` (не `required` на `int` — ноль провалит) — `R-VLD-STD-2`.
   - `email`, `e164`, `uuid4`, `url` из встроенных тегов, не самописный regex? — `R-VLD-STD-3`.
   - `time.Time` + кастомный тег `future`/`past` через `RegisterCustomTags`? — `R-VLD-STD-4`.
   - Деньги — `int64` (копейки) или `shopspring/decimal`, не `float64`; тег `gt=0`, не `required` — `R-VLD-STD-5`.
   - `validate:"required"` на `int`/`int64` вместо `gt=0` — `R-VLD-STD-X1`.
   - Самописный regex для email/телефона вместо встроенного тега — `R-VLD-STD-X2`.

   ### `R-VLD-CC-*`
   - Кастомный тег зарегистрирован в `RegisterCustomTags` (`internal/validation/tags.go`)? — `R-VLD-CC-1/2`.
   - Имя тега по доменному термину: `ru_phone`, `vat_number`, `future` — не `valid_phone`, `check_inn`? — `R-VLD-CC-3`.
   - На optional-поле кастомный тег комбинируется с `omitempty`? — `R-VLD-CC-4`.
   - Функция валидатора stateless (только от значения), type-assertion с `ok`-guard на zero-value? — `R-VLD-CC-5`.
   - Паника или неверный результат при zero-value (`FieldLevel.Field()` может вернуть zero) — `R-VLD-CC-X1`.
   - Регистрация тега inline в файле DTO — `R-VLD-CC-X2` (предупреждение).
   - «Мега-тег», объединяющий несколько несвязанных правил — `R-VLD-CC-X3`.

   ### `R-VLD-GRP-*`
   - Разные required-поля в разных сценариях — отдельные struct-типы (`CreateOrderRequest` vs `DraftOrderRequest`)? — `R-VLD-GRP-1`.
   - Если `GRP-2` нужен — через `validate.StructCtx` + `FieldLevel.Param()`.
   - Один struct с boolean-полем «режим» вместо двух типов — `R-VLD-GRP-X1`.
   - Struct на 3+ разных сценария без разбивки — `R-VLD-GRP-X2`.

   ### `R-VLD-XF-*`
   - Cross-field правило на 2+ полях — `RegisterStructValidation` в `internal/validation/cross_field.go`? — `R-VLD-XF-1`.
   - Имя тега/функции описывает правило: `date_range`, `passwords_match` — не `validate_request`? — `R-VLD-XF-2`.
   - Одноразовая cross-field проверка в handler-коде для правила, встречающегося в нескольких DTO — `R-VLD-XF-X1`.
   - Cross-field проверка в Handler до dispatch — `R-VLD-XF-X2`.

   ### `R-VLD-OAS-*`
   - Code-first: struct-тег — единственный источник правила, не дублируется ни в DTO, ни в ручной проверке? — `R-VLD-OAS-1`.
   - Contract-first (`oapi-codegen`): теги добавляются через `x-oapi-codegen-extra-tags`, не в сгенерированный файл? — `R-VLD-OAS-4`.
   - После `toCreateOrderCommand(req)` нет повторного `validate.Struct` — команда «уже чистая» — `R-VLD-OAS-6`.
   - Ручная правка сгенерированного файла — `R-VLD-OAS-X1`.
   - Дублирование: `validate.Struct(req)` и при этом ещё `if req.Amount <= 0` на то же поле — `R-VLD-OAS-X4`.
   - Inbound-данные как `map[string]any` / `json.RawMessage` без декодирования в типизированный struct — `R-VLD-OAS-X5` (критично).

   ### `R-VLD-CFG-*`
   - `envconfig.Process("APP", &cfg)` + `validate.Struct(&cfg)` в `config.Load()`? — `R-VLD-CFG-1/2`.
   - Required-поля — `required:"true"` в envconfig-теге, без default? — `R-VLD-CFG-2`.
   - Nested-config (`PaymentConfig`) валидируется рекурсивно (validate v10 обходит поля)? — `R-VLD-CFG-4`.
   - Конфиг-struct без `required:"true"` / `validate`-тегов — `R-VLD-CFG-X1`.
   - `os.Getenv("KEY")` для required-конфига вместо envconfig — `R-VLD-CFG-X2` (критично).

   ### `R-VLD-MSG-*`
   - `Localize(fe validator.FieldError)` — маппинг тега → читаемый русский текст с интерполяцией `fe.Param()`, `fieldLabel(fe.Field())`? — `R-VLD-MSG-1/2`.
   - `fe.Error()` напрямую в ответ (английский технический текст) — `R-VLD-MSG-X1` (критично).
   - Технические термины в тексте (`Field customer_id failed...`) — `R-VLD-MSG-X2`.
   - Один и тот же статичный текст без контекста поля — `R-VLD-MSG-X3`.
   - ValidationError реализует `Kind() apperr.Validation`; edge-renderer (`httperr.Write`) через `errors.As(err, &ve)` → 400 + `errors`-массив (problem+json)?

4. **Cross-check:** 400-маппинг → `ucp-go-error-handling-review` (`R-ERR-MAP-2`); доменные инварианты → `ucp-go-ddd-tactical-review` / `ucp-go-pattern-review`; retry без `Idempotency-Key` на write → `ucp-go-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — ручная input-валидация в Handler (`R-VLD-WHERE-X1`), inbound как `map[string]any` (`R-VLD-OAS-X5`), деньги во `float64` (`R-VLD-STD-5`), `os.Getenv` для required-конфига (`R-VLD-CFG-X2`), `fe.Error()` напрямую в ответ (`R-VLD-MSG-X1`).
   - **Предупреждение** — `validate`-теги на агрегате (`R-VLD-WHERE-X4`), дублирование тег + ручной if (`R-VLD-OAS-X4`), custom-тег inline в DTO (`R-VLD-CC-X2`), самописный regex для стандартного формата (`R-VLD-STD-X2`), cross-field в Handler (`R-VLD-XF-X2`).
   - **Замечание** — нет `omitempty` на optional custom-теге, один struct на 3+ сценария, технические термины в message (`R-VLD-MSG-X2`), конфиг-struct без validate-тегов на вторичных полях.

## Что не входит

- Маппинг ошибки в 400/problem+json (поля `type`/`title`/`status`) — `ucp-go-error-handling-review` (`R-ERR-MAP-2`, `R-API-ERR-*`).
- Доменные инварианты — `ucp-go-ddd-tactical-review` / `ucp-go-pattern-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.

$ARGUMENTS
