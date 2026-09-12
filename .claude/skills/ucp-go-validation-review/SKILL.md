---
name: ucp-go-validation-review
lang: go
description: Ревью валидации входа в Go-сервисе (net/http + chi) по UCP — go-playground/validator v10 struct-теги на границе, httpreq.Decode, envconfig fail-fast, custom-теги и cross-field RegisterStructValidation, Localize → 400 problem+json.
when_to_use: Изменения в *request*.go, *dto*.go, internal/validation/, config/, httpreq/, edge/ или любом коде с validator.Struct / envconfig.Process.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью валидации (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/validation/spec.md`
(`R-VLD-*`, коды едины с Java/Python) и его **Go-реализации** `backend/validation/references/go/implementation.md`.
Помни парадигму: в Go нет декоратора-магии — граница это `httpreq.Decode[T]` (decode + `validate.Struct`) или
chi-middleware; `go-playground/validator/v10` — декларативные теги на struct-полях; конфиг — `envconfig` + fail-fast.

## Зависимости

- **`.claude/docs/backend/validation/spec.md`** — общий контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/references/go/implementation.md`** — Go-реализация (validator/v10, httpreq.Decode, envconfig, RegisterCustomTags, RegisterStructValidation, Localize).
- Парные: `backend/error-handling/spec.md` (`error-handling/domain-and-validation-mapping`), `backend/ddd-tactical/spec.md` (инварианты ≠ валидация).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`validation/input-validated-at-edge`), не префикс.

2. **Скоп.** `**/*request*.go`, `**/*dto*.go`, `internal/validation/`, `config/`, `edge/httpreq/`, `git diff` на `.go`.
   **`Grep`:** `if req\.` (ручные проверки в handler), `validate.Struct` вне `httpreq.Decode`, `os.Getenv` для конфига, `map\[string\]any` как inbound, `fe.Error()` в ответе.

3. **Прогон по подгруппам.**

   ### `R-VLD-WHERE-*`
   - `httpreq.Decode[T]` (decode + `validate.Struct` + `toValidationError`) вызывается первым в handler? — `validation/input-validated-at-edge`.
   - Конфиг через `envconfig.Process` + `validate.Struct` в `config.Load()`, `os.Exit(1)` при ошибке? — `validation/config-validated-at-startup`.
   - Доменные инварианты в конструкторе агрегата (возвращают типизированную ошибку с `Kind() apperr.Domain`), не в `validate`-тегах? — `validation/domain-invariants-in-aggregate`.
   - Nested-struct с тегом `validate:"required,dive"` или явным `validate.Struct` на вложенном поле? — `validation/nested-validated-recursively`.
   - Ручные `if req.Field == ""` / `if req.Amount < 0` в Handler вместо тегов — `validation/input-validated-at-edge` (критично).
   - `validate.Struct(cmd)` после маппинга уже провалидированного DTO в команду — `validation/no-revalidation-after-edge`.
   - `validate`-теги на полях доменного агрегата — `validation/domain-invariants-in-aggregate`.

   ### `R-VLD-STD-*`
   - Pointer-тип (`*string`) + `omitempty` для опционального поля; `validate:"required"` на не-пустых? — `validation/standard-constraints-preferred`.
   - Строки — `min=N,max=M`; числа — `gt=0,lte=M` (не `required` на `int` — ноль провалит) — `validation/standard-constraints-preferred`.
   - `email`, `e164`, `uuid4`, `url` из встроенных тегов, не самописный regex? — `validation/standard-constraints-preferred`.
   - `time.Time` + кастомный тег `future`/`past` через `RegisterCustomTags`? — `validation/standard-constraints-preferred`.
   - Деньги — `int64` (копейки) или `shopspring/decimal`, не `float64`; тег `gt=0`, не `required` — `validation/standard-constraints-preferred`.
   - `validate:"required"` на `int`/`int64` вместо `gt=0` — `validation/no-false-or-composite-constraints`.
   - Самописный regex для email/телефона вместо встроенного тега — `validation/standard-constraints-preferred`.

   ### `R-VLD-CC-*`
   - Кастомный тег зарегистрирован в `RegisterCustomTags` (`internal/validation/tags.go`)? — `R-VLD-CC-1/2`.
   - Имя тега по доменному термину: `ru_phone`, `vat_number`, `future` — не `valid_phone`, `check_inn`? — `validation/custom-constraint-named-by-domain`.
   - На optional-поле кастомный тег комбинируется с `omitempty`? — `validation/custom-constraint-null-safe`.
   - Функция валидатора stateless (только от значения), type-assertion с `ok`-guard на zero-value? — `validation/constraint-is-stateless`.
   - Паника или неверный результат при zero-value (`FieldLevel.Field()` может вернуть zero) — `validation/custom-constraint-null-safe`.
   - Регистрация тега inline в файле DTO — `validation/custom-constraint-is-reusable` (предупреждение).
   - «Мега-тег», объединяющий несколько несвязанных правил — `validation/custom-constraint-is-reusable`.

   ### `R-VLD-GRP-*`
   - Разные required-поля в разных сценариях — отдельные struct-типы (`CreateOrderRequest` vs `DraftOrderRequest`)? — `validation/scenario-groups-are-narrow`.
   - Если `GRP-2` нужен — через `validate.StructCtx` + `FieldLevel.Param()`.
   - Один struct с boolean-полем «режим» вместо двух типов — `validation/scenario-groups-are-narrow`.
   - Struct на 3+ разных сценария без разбивки — `validation/scenario-groups-are-narrow`.

   ### `R-VLD-XF-*`
   - Cross-field правило на 2+ полях — `RegisterStructValidation` в `internal/validation/cross_field.go`? — `validation/cross-field-rules-on-object`.
   - Имя тега/функции описывает правило: `date_range`, `passwords_match` — не `validate_request`? — `validation/cross-field-rules-on-object`.
   - Одноразовая cross-field проверка в handler-коде для правила, встречающегося в нескольких DTO — `validation/cross-field-rules-on-object`.
   - Cross-field проверка в Handler до dispatch — `validation/cross-field-rules-on-object`.

   ### `R-VLD-OAS-*`
   - Code-first: struct-тег — единственный источник правила, не дублируется ни в DTO, ни в ручной проверке? — `validation/single-source-of-truth`.
   - Contract-first (`oapi-codegen`): теги добавляются через `x-oapi-codegen-extra-tags`, не в сгенерированный файл? — `validation/controller-implements-generated-contract`.
   - После `toCreateOrderCommand(req)` нет повторного `validate.Struct` — команда «уже чистая» — `validation/no-revalidation-after-edge`.
   - Ручная правка сгенерированного файла — `validation/generated-artifacts-immutable`.
   - Дублирование: `validate.Struct(req)` и при этом ещё `if req.Amount <= 0` на то же поле — `validation/single-source-of-truth`.
   - Inbound-данные как `map[string]any` / `json.RawMessage` без декодирования в типизированный struct — `validation/controller-implements-generated-contract` (критично).

   ### `R-VLD-CFG-*`
   - `envconfig.Process("APP", &cfg)` + `validate.Struct(&cfg)` в `config.Load()`? — `R-VLD-CFG-1/2`.
   - Required-поля — `required:"true"` в envconfig-теге, без default? — `validation/config-validated-at-startup`.
   - Nested-config (`PaymentConfig`) валидируется рекурсивно (validate v10 обходит поля)? — `validation/config-validated-at-startup`.
   - Конфиг-struct без `required:"true"` / `validate`-тегов — `validation/config-validated-at-startup`.
   - `os.Getenv("KEY")` для required-конфига вместо envconfig — `validation/config-validated-at-startup` (критично).

   ### `R-VLD-MSG-*`
   - `Localize(fe validator.FieldError)` — маппинг тега → читаемый русский текст с интерполяцией `fe.Param()`, `fieldLabel(fe.Field())`? — `R-VLD-MSG-1/2`.
   - `fe.Error()` напрямую в ответ (английский технический текст) — `validation/message-in-user-language` (критично).
   - Технические термины в тексте (`Field customer_id failed...`) — `validation/message-in-user-language`.
   - Один и тот же статичный текст без контекста поля — `validation/no-duplicated-messages`.
   - ValidationError реализует `Kind() apperr.Validation`; edge-renderer (`httperr.Write`) через `errors.As(err, &ve)` → 400 + `errors`-массив (problem+json)?

4. **Cross-check:** 400-маппинг → `ucp-go-error-handling-review` (`error-handling/domain-and-validation-mapping`); доменные инварианты → `ucp-go-ddd-tactical-review` / `ucp-go-pattern-review`; retry без `Idempotency-Key` на write → `ucp-go-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — ручная input-валидация в Handler (`validation/input-validated-at-edge`), inbound как `map[string]any` (`validation/controller-implements-generated-contract`), деньги во `float64` (`validation/standard-constraints-preferred`), `os.Getenv` для required-конфига (`validation/config-validated-at-startup`), `fe.Error()` напрямую в ответ (`validation/message-in-user-language`).
   - **Предупреждение** — `validate`-теги на агрегате (`validation/domain-invariants-in-aggregate`), дублирование тег + ручной if (`validation/single-source-of-truth`), custom-тег inline в DTO (`validation/custom-constraint-is-reusable`), самописный regex для стандартного формата (`validation/standard-constraints-preferred`), cross-field в Handler (`validation/cross-field-rules-on-object`).
   - **Замечание** — нет `omitempty` на optional custom-теге, один struct на 3+ сценария, технические термины в message (`validation/message-in-user-language`), конфиг-struct без validate-тегов на вторичных полях.

## Что не входит

- Маппинг ошибки в 400/problem+json (поля `type`/`title`/`status`) — `ucp-go-error-handling-review` (`error-handling/domain-and-validation-mapping`, `R-API-ERR-*`).
- Доменные инварианты — `ucp-go-ddd-tactical-review` / `ucp-go-pattern-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.

$ARGUMENTS
