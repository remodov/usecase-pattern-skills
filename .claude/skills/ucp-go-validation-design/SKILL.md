---
name: ucp-go-validation-design
lang: go
description: Спроектировать валидацию входа в Go-сервисе (net/http + chi) по UCP — struct-теги go-playground/validator, httpreq.Decode на границе, custom-теги internal/validation, cross-field RegisterStructValidation, envconfig fail-fast, Localize.
when_to_use: Триггеры — «валидация запроса в Go», «настрой validator/v10 для X», «go-playground/validator на chi». При новом хендлере, DTO или конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование валидации (Go / net/http + chi)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/spec.md` (`R-VLD-*`)
и его **Go-реализации** `backend/validation/references/go/implementation.md` (`github.com/go-playground/validator/v10`, struct-теги, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/spec.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/references/go/implementation.md` — Go-реализация (struct-теги, `httpreq.Decode`, `RegisterCustomTags`, `RegisterStructValidation`, `envconfig`, `Localize`).
   - `.claude/docs/backend/error-handling/spec.md` — как `*ValidationError` с `Kind() apperr.Validation` становится 400 (`error-handling/domain-and-validation-mapping`).

2. **Определи объект.** Входной HTTP-DTO хендлера / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев; коды правил НЕ цитируй в коде):
   - Входные DTO — типизированные struct'ы с `validate`-тегами; декодирование и валидация через `httpreq.Decode[T](r)` на границе до бизнес-логики; хендлер получает чистый struct (`validation/input-validated-at-edge`); required vs pointer (`*string`) + `omitempty` для опциональных (`validation/standard-constraints-preferred`); размеры строк — `min=N,max=M`; числа — `gt=0,lte=N`; деньги — `int64` (копейки) или `shopspring/decimal`, не `float64` (`R-VLD-STD-2/5`); форматы — встроенными тегами `email`/`e164`/`uuid4`/`url`, не самописным regex (`validation/standard-constraints-preferred`); nested-struct — `validate:"required,dive"` (`validation/nested-validated-recursively`).
   - Custom-теги — stateless функции `validator.FieldLevel → bool` с type assertion + `ok`-guard, именованные по домену (`ru_phone`, `vat_number`, `future`), зарегистрированные в `internal/validation/tags.go` через `RegisterCustomTags(v)` (`R-VLD-CC-1/2/3/5`); optional-поле — `omitempty` перед custom-тегом (`validation/custom-constraint-null-safe`).
   - Cross-field — `RegisterStructValidation(fn, T{})` в `internal/validation/cross_field.go` с говорящим именем тега в `sl.ReportError` (`R-VLD-XF-1/2`).
   - Конфиг — `kelseyhightower/envconfig` с `required:"true"` на обязательных полях + `validate.Struct(&cfg)` для дополнительных ограничений; `os.Exit(1)` при ошибке в `main.go` (`validation/config-validated-at-startup`, `R-VLD-CFG-1/2`); nested-config валидируется рекурсивно (`validation/config-validated-at-startup`).
   - `ValidationError` — struct с `Violations []Violation` + `Kind() apperr.Validation`; `toValidationError` через `errors.As(err, &validator.ValidationErrors)`; тексты из `Localize(fe)` по свичу на `fe.Tag()` — на русском с `fe.Field()`/`fe.Param()` для интерполяции (`R-VLD-MSG-1/2`).
   - `httperr.Write` расширяется: `errors.As(err, &ve)` → 400 + `application/problem+json` + `errors`-массив.
   - Группы сценариев — отдельные struct-типы (`CreateOrderRequest` vs `DraftOrderRequest`), не boolean-режим в одном struct (`validation/scenario-groups-are-narrow`).
   - После маппинга DTO в UseCase-команду повторный `validate.Struct` не вызывается — команда уже чистая (`validation/no-revalidation-after-edge`).

4. **Самопроверка** — пройдись по чеклисту из `go/implementation.md` §«Чеклист подключения». Рекомендуй `go vet ./...` + `golangci-lint run`.

5. **Финальный шаг:** предложи «запусти `ucp-go-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручные `if req.X == "" { http.Error(...) }` в Handler вместо `httpreq.Decode` + struct-тегов (`validation/input-validated-at-edge`); повторный `validate.Struct` UseCase-команды (`validation/no-revalidation-after-edge`).
- `validate`-теги на полях доменного агрегата (`validation/domain-invariants-in-aggregate`); инвариант — в конструкторе агрегата, возвращающем domain-ошибку с `Kind() apperr.Domain`.
- `validate:"required"` на `int`/`int64` (zero-value `0` всегда провалит) — используй `gt=0` (`validation/no-false-or-composite-constraints`); самописный email-regex вместо встроенного тега `email` (`validation/standard-constraints-preferred`).
- Кастомный тег регистрируется inline в файле DTO (`validation/custom-constraint-is-reusable`); panic / возврат некорректного значения на zero-value в FieldLevel без type assertion + `ok` (`validation/custom-constraint-null-safe`).
- Cross-field проверка в Handler до dispatch вместо `RegisterStructValidation` (`validation/cross-field-rules-on-object`).
- Один struct с 3+ разными сценариями через boolean-режим (`validation/scenario-groups-are-narrow`); `os.Getenv("X")` для required-конфига (`validation/config-validated-at-startup`).
- `fe.Error()` напрямую в ответ — английский технический текст (`validation/message-in-user-language`); технические термины в пользовательском сообщении (`validation/message-in-user-language`).
- Входные данные как `map[string]any` / `json.RawMessage` без декодирования в типизированный struct (`validation/controller-implements-generated-contract`).
- Деньги во `float64`; дублирование `validate.Struct` + ручной `if`-чек на то же поле (`validation/single-source-of-truth`).

После работы скилла — обязательно `ucp-go-validation-review`.

$ARGUMENTS
