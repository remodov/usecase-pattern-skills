---
name: ucp-go-error-handling-review
lang: go
description: Ревью обработки ошибок в Go-сервисе (net/http + chi) по UCP — ошибки как значения, Kind-маркер + errors.As, edge-renderer и recover-middleware, problem+json (RFC 9457), обёртка %w, port-specific в out-adapter, retry на идемпотентных.
when_to_use: Изменения в apperr/*.go, *errors.go, edge-middleware, HTTP-клиентах или любом коде с возвратом error.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью обработки ошибок (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/error-handling/spec.md`
(`R-ERR-*`, коды едины с Java/Python/Node) и его **Go-реализации** `backend/error-handling/references/go/implementation.md`.
Помни парадигму: в Go ошибки — **значения**, не исключения; «edge-handler» = middleware, «иерархия» = `Kind`-маркер + `errors.As`,
`panic/recover` — только backstop, не control-flow.

## Зависимости

- **`.claude/docs/backend/error-handling/spec.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/references/go/implementation.md`** — Go-реализация (apperr.Kind, errors.As/%w, chi-middleware, retry-go/gobreaker, slog, client_golang).
- Парные: `backend/rest-api/spec.md` (`R-API-ERR-*`), `backend/validation/spec.md`, `backend/resilience/spec.md`, `backend/auth-patterns/spec.md` (`auth-patterns/error-response-hides-cause`/`auth-patterns/money-commands-need-idempotency-key`), `backend/observability/spec.md`.

## Инструкции

1. **Прочти** общий `error-handling/spec.md` и `references/go/implementation.md` (как это в Go). Цитируй конкретные коды (`error-handling/catch-does-not-swallow`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/apperr/*.go`, `**/*errors.go` — категории и типизированные ошибки (`R-ERR-HIER-*`).
   - `edge/**`, `**/middleware/*.go`, `**/render*.go` — edge-renderer + recover (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.go` (HTTP-клиенты) — port-specific, маппинг статусов/транспорта (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.go`.
   - **`Grep`**: `_ = ` (игнор ошибки), `return nil$` после `if err != nil`, `fmt.Errorf\("[^"]*%v"`, `recover\(\)` вне edge.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - Есть `Kind` + `Categorized`-маркер + `KindOf(err)` (через `errors.As`)? — `R-ERR-HIER-1/2`.
   - Доменные ошибки — типизированные структуры с `Kind() Domain`, имена по бизнес-смыслу (`InsufficientFundsError`)? — `error-handling/domain-exception-named-by-meaning`.
   - Integration-ошибки с префиксом системы (`GatewayError`), реализуют `Unwrap()` и `Kind() Integration`? — `error-handling/integration-exception-names-system`.
   - Контекст в полях структуры + конструктор? — `error-handling/exception-carries-context`.
   - `errors.New("...")`/`fmt.Errorf("...")` без категории там, где edge ждёт Domain — `error-handling/no-bare-base-exceptions`.
   - `panic(...)` для бизнес-правила — `error-handling/no-bare-base-exceptions`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `recover()`; ошибки возвращаются вверх. — `error-handling/catch-in-three-places-only`.
   - Out-adapter мапит транспорт/4xx (→domain)/5xx (→Integration) в port-specific с `%w`? — `R-ERR-WHERE-2b`.
   - Единый edge-renderer + `Recoverer`-middleware (panic→500)? — `R-ERR-WHERE-2a`.
   - Проглатывание: `if err != nil { slog.Error(...); return nil }`, пустой `if err != nil {}`, `_ = call()` — критика `error-handling/catch-does-not-swallow`.
   - `errors.New(err.Error())` / `fmt.Errorf("...%v", err)` (теряется `%w`/тип) — критика `error-handling/catch-does-not-swallow`.
   - `return Zero{}, nil` при фактической ошибке — критика `error-handling/catch-does-not-swallow`.

   ### `R-ERR-MAP-*`
   - `mapKind`: Domain→409/422, Validation→400, Integration→502/503/504, Technical→500? — `R-ERR-MAP-1..4`.
   - recover-middleware → 500? — `error-handling/integration-and-technical-mapping`.
   - `Content-Type: application/problem+json` на всех error-response? — `R-ERR-MAP-*`.
   - В response нет stack / `err.Error()` низкоуровневой ошибки? — `error-handling/integration-and-technical-mapping`/`X3`.
   - `w.WriteHeader(200)` при ошибке / `{"success": false}` — критика `error-handling/no-success-code-for-failure`.

   ### `R-ERR-LOG-*`
   - Domain → `slog.WarnContext` (не Error)? — `error-handling/log-level-matches-kind`.
   - panic/Technical → `slog.ErrorContext` + stack? — `error-handling/log-level-matches-kind`.
   - `slog.Error(...); return err` — `error-handling/log-once-with-exception`.
   - `slog.Error(err.Error())` строкой вместо атрибута `"error", err` — `error-handling/log-once-with-exception`.

   ### `R-ERR-RETRY-*`
   - `retry.RetryIf` пропускает Domain/Validation — нарушение `error-handling/retry-semantics-by-kind`.
   - retry на 4xx-производном (`InvalidPaymentRequestError`) — `error-handling/retry-semantics-by-kind`.
   - retry на write без `Idempotency-Key` — критика `error-handling/retry-semantics-by-kind` + `resilience/retry-only-when-safe`/`auth-patterns/money-commands-need-idempotency-key`.

   ### `R-ERR-RESULT-*`
   - `panic/recover` как control-flow между слоями (имитация try/catch) — `error-handling/result-type-is-local-choice`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (client_golang `CounterVec` с `type`/`exception`)? — `error-handling/errors-counted-by-kind`.
   - `span.RecordError` + `SetStatus(codes.Error)` на ошибке? — `error-handling/trace-span-marked-error`.
   - Алёрты только на `unexpected`/`technical` — `error-handling/alert-on-patterns-not-exceptions`.

4. **Cross-check:** retry на write без ключа → `auth-patterns/money-commands-need-idempotency-key`/`resilience/retry-only-when-safe`; PII в `detail` → `auth-patterns/error-response-hides-cause`; problem+json → `R-API-ERR-*`; validator → `validation/input-validated-at-edge`. Рекомендуй `errcheck`+`errorlint` в линтере, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — `error-handling/catch-does-not-swallow` (`_ =`/проглоченный err), `error-handling/catch-does-not-swallow` (`Zero{}, nil`), `error-handling/no-success-code-for-failure` (200 при ошибке), `error-handling/integration-and-technical-mapping` (SQL-текст в response), `error-handling/retry-semantics-by-kind`, отсутствие recover-middleware, `panic` для бизнес-правила.
   - **Предупреждение** — `error-handling/catch-does-not-swallow` (`%v` вместо `%w`, потеря типа), `error-handling/no-bare-base-exceptions`, `R-ERR-LOG-X1/X2`, Domain на Error-уровне.
   - **Замечание** — нет `app_errors_total`, ошибка без контекста, деньги во `float64`, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- validator-constraints — `ucp-go-validation-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.
- PII в логах — `ucp-go-observability-review` / `ucp-auth-review`.

$ARGUMENTS
