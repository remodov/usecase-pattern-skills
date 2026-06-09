---
name: ucp-go-error-handling-design
lang: go
description: Спроектировать обработку ошибок в Go-сервисе (net/http + chi) по UCP (коды R-ERR-*) — категории apperr.Kind + errors.As, edge-renderer и recover-middleware с problem+json (RFC 9457), port-ошибки в out-adapter, retry-go, slog-наблюдаемость.
when_to_use: При старте сервиса или миграции «if err != nil { return nil }»-кода. Триггеры — «настрой обработку ошибок в Go», «apperr с категориями».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование обработки ошибок (Go / net/http + chi)

Ты создаёшь / расширяешь обработку ошибок в Go-сервисе согласно **общему контракту**
`backend/error-handling/error-handling-rules.md` (`R-ERR-*`) и его **Go-реализации**
`backend/error-handling/go/error-handling-style-guide.md`. Помни: в Go ошибки — значения; «edge-handler» = middleware,
«иерархия» = `Kind`-маркер + `errors.As`, `panic/recover` — только backstop. Цель — единая стратегия:
типизированные категории, обработка ровно в трёх местах (edge-renderer / out-adapter / резильянс-обёртка),
консистентный problem+json-mapping, наблюдаемость.

Не делает: валидацию входа (`ucp-go-validation-design`), резилианс-обвязку (`ucp-go-resilience-design`),
маскирование PII в логах (`ucp-go-observability-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — общий контракт, коды `R-ERR-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/error-handling/go/error-handling-style-guide.md` — Go-реализация (apperr/Kind, errors.As/%w, chi-middleware, retry-go/gobreaker, slog), открывай точечно по разделу.
   - `.claude/docs/backend/rest-api/rest-api-rules.md` — `R-API-ERR-*` для формата problem+json.
   - `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` — `AUTH-19` (идемпотентность), `AUTH-18` (PII в response).

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Go:
   - `core/` — домен; `core/apperr/` — категории; доменные ошибки рядом с агрегатом.
   - `edge/` — chi-роутер, error-renderer, recover-middleware.
   - `adapters/out/<system>/` — HTTP-клиент + port-specific ошибки.

3. **Аудит текущего состояния** (что есть / что предстоит): `apperr.Kind`+`Categorized`+`KindOf` (`R-ERR-HIER-1/2`), доменные типизированные ошибки с контекстом (`R-ERR-HIER-3/5`), edge-renderer + recover-middleware (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`), HTTP-клиенты мапят в port-specific с `%w` (`R-ERR-WHERE-2b`), нет `recover()` / проглоченных ошибок в core (`R-ERR-WHERE-X1/X3`), метрика `app_errors_total` (`R-ERR-OBS-1`).

4. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие выражается именами/типами/структурой; коды правил в комментариях НЕ цитируй).

   ### 4.1 `core/apperr/apperr.go` — категории
   `Kind` (Domain/Validation/Integration/Technical) + интерфейс `Categorized{ Kind() Kind }` + `KindOf(err) Kind` (через `errors.As`, дефолт Technical).

   ### 4.2 Доменные ошибки
   Типизированные структуры с контекстом-полями + `Error()` + `Kind() apperr.Domain`. Имена по бизнес-смыслу. Деньги — `int64` (минорные единицы) или `shopspring/decimal`, не `float64`.

   ### 4.3 `edge/httperr/render.go` + recover-middleware
   `Write(w, r, err)` → `mapKind(KindOf(err))` → `writeProblem(...)` с `Content-Type: application/problem+json` + лог один раз + inc метрики. `Recoverer`-middleware ловит `panic` → 500 + stack.

   ### 4.4 Port-specific ошибки в HTTP-клиентах
   `<System>Error` с `Unwrap()` и `Kind() Integration`; в клиенте: транспорт/timeout → `<System>Error`, 4xx → domain `Invalid…Error`, 5xx → `<System>Error`. Обёртка `%w`.

   ### 4.5 Никаких `recover()` / проглатываний в core
   Ошибки возвращаются вверх с `fmt.Errorf("...: %w", err)`-контекстом. Не `_ = call()`, не `return Zero{}, nil` при ошибке.

   ### 4.6 Retry (если есть исходящие вызовы)
   `retry-go` с `RetryIf(errors.As → Integration-тип)` только на идемпотентных; 4xx-производные не ретраятся (`R-ERR-RETRY-2/3`). CB — `sony/gobreaker` при необходимости.

   ### 4.7 Observability
   `app_errors_total` (`client_golang` `CounterVec` с `type`/`exception`); inc в edge-renderer и recover; `span.RecordError` + `SetStatus(codes.Error)`.

5. **Самопроверка** — пройдись по чеклисту из `go/error-handling-style-guide.md` §«Чеклист подключения». Рекомендуй `errcheck`+`errorlint` в `golangci-lint`.

6. **Финальный шаг:** предложи «запусти `ucp-go-error-handling-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `if err != nil { return nil }` / `_ = call()` / пустой `if err != nil {}` (`R-ERR-WHERE-X1`).
- `fmt.Errorf("...%v", err)` / `errors.New(err.Error())` (потеря `%w`/типа, `R-ERR-WHERE-X2`).
- `return Zero{}, nil` при фактической ошибке (`R-ERR-WHERE-X3`).
- `panic` для бизнес-правила; `recover` как control-flow между слоями (`R-ERR-HIER-X2`/`R-ERR-RESULT-X1`).
- `w.WriteHeader(200)` при ошибке (`R-ERR-MAP-X1`); `err.Error()` низкоуровневой ошибки в `detail` (`R-ERR-MAP-X3`).
- деньги во `float64`; retry на write без `Idempotency-Key` (`R-ERR-RETRY-3`).

После работы скилла — обязательно `ucp-go-error-handling-review` для верификации.

$ARGUMENTS
