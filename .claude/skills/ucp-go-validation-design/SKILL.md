---
name: ucp-go-validation-design
lang: go
description: Спроектировать валидацию входа в Go-сервисе (net/http + chi) по UCP (коды R-VLD-*) — struct-теги go-playground/validator, httpreq.Decode на границе, custom-теги internal/validation, cross-field RegisterStructValidation, envconfig fail-fast, Localize.
when_to_use: Триггеры — «валидация запроса в Go», «настрой validator/v10 для X», «go-playground/validator на chi». При новом хендлере, DTO или конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование валидации (Go / net/http + chi)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/validation-rules.md` (`R-VLD-*`)
и его **Go-реализации** `backend/validation/go/validation-style-guide.md` (`github.com/go-playground/validator/v10`, struct-теги, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/validation-rules.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/go/validation-style-guide.md` — Go-реализация (struct-теги, `httpreq.Decode`, `RegisterCustomTags`, `RegisterStructValidation`, `envconfig`, `Localize`).
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — как `*ValidationError` с `Kind() apperr.Validation` становится 400 (`R-ERR-MAP-2`).

2. **Определи объект.** Входной HTTP-DTO хендлера / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев; коды правил НЕ цитируй в коде):
   - Входные DTO — типизированные struct'ы с `validate`-тегами; декодирование и валидация через `httpreq.Decode[T](r)` на границе до бизнес-логики; хендлер получает чистый struct (`R-VLD-WHERE-1`); required vs pointer (`*string`) + `omitempty` для опциональных (`R-VLD-STD-1`); размеры строк — `min=N,max=M`; числа — `gt=0,lte=N`; деньги — `int64` (копейки) или `shopspring/decimal`, не `float64` (`R-VLD-STD-2/5`); форматы — встроенными тегами `email`/`e164`/`uuid4`/`url`, не самописным regex (`R-VLD-STD-3`); nested-struct — `validate:"required,dive"` (`R-VLD-WHERE-4`).
   - Custom-теги — stateless функции `validator.FieldLevel → bool` с type assertion + `ok`-guard, именованные по домену (`ru_phone`, `vat_number`, `future`), зарегистрированные в `internal/validation/tags.go` через `RegisterCustomTags(v)` (`R-VLD-CC-1/2/3/5`); optional-поле — `omitempty` перед custom-тегом (`R-VLD-CC-4`).
   - Cross-field — `RegisterStructValidation(fn, T{})` в `internal/validation/cross_field.go` с говорящим именем тега в `sl.ReportError` (`R-VLD-XF-1/2`).
   - Конфиг — `kelseyhightower/envconfig` с `required:"true"` на обязательных полях + `validate.Struct(&cfg)` для дополнительных ограничений; `os.Exit(1)` при ошибке в `main.go` (`R-VLD-WHERE-2`, `R-VLD-CFG-1/2`); nested-config валидируется рекурсивно (`R-VLD-CFG-4`).
   - `ValidationError` — struct с `Violations []Violation` + `Kind() apperr.Validation`; `toValidationError` через `errors.As(err, &validator.ValidationErrors)`; тексты из `Localize(fe)` по свичу на `fe.Tag()` — на русском с `fe.Field()`/`fe.Param()` для интерполяции (`R-VLD-MSG-1/2`).
   - `httperr.Write` расширяется: `errors.As(err, &ve)` → 400 + `application/problem+json` + `errors`-массив.
   - Группы сценариев — отдельные struct-типы (`CreateOrderRequest` vs `DraftOrderRequest`), не boolean-режим в одном struct (`R-VLD-GRP-1`).
   - После маппинга DTO в UseCase-команду повторный `validate.Struct` не вызывается — команда уже чистая (`R-VLD-OAS-6`).

4. **Самопроверка** — пройдись по чеклисту из `go/validation-style-guide.md` §«Чеклист подключения». Рекомендуй `go vet ./...` + `golangci-lint run`.

5. **Финальный шаг:** предложи «запусти `ucp-go-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручные `if req.X == "" { http.Error(...) }` в Handler вместо `httpreq.Decode` + struct-тегов (`R-VLD-WHERE-X1`); повторный `validate.Struct` UseCase-команды (`R-VLD-WHERE-X2`).
- `validate`-теги на полях доменного агрегата (`R-VLD-WHERE-X4`); инвариант — в конструкторе агрегата, возвращающем domain-ошибку с `Kind() apperr.Domain`.
- `validate:"required"` на `int`/`int64` (zero-value `0` всегда провалит) — используй `gt=0` (`R-VLD-STD-X1`); самописный email-regex вместо встроенного тега `email` (`R-VLD-STD-X2`).
- Кастомный тег регистрируется inline в файле DTO (`R-VLD-CC-X2`); panic / возврат некорректного значения на zero-value в FieldLevel без type assertion + `ok` (`R-VLD-CC-X1`).
- Cross-field проверка в Handler до dispatch вместо `RegisterStructValidation` (`R-VLD-XF-X2`).
- Один struct с 3+ разными сценариями через boolean-режим (`R-VLD-GRP-X2`); `os.Getenv("X")` для required-конфига (`R-VLD-CFG-X2`).
- `fe.Error()` напрямую в ответ — английский технический текст (`R-VLD-MSG-X1`); технические термины в пользовательском сообщении (`R-VLD-MSG-X2`).
- Входные данные как `map[string]any` / `json.RawMessage` без декодирования в типизированный struct (`R-VLD-OAS-X5`).
- Деньги во `float64`; дублирование `validate.Struct` + ручной `if`-чек на то же поле (`R-VLD-OAS-X4`).

После работы скилла — обязательно `ucp-go-validation-review`.

$ARGUMENTS
