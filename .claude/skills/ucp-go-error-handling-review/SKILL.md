---
name: ucp-go-error-handling-review
lang: go
description: Ревью обработки ошибок в Go-сервисе (net/http + chi) по UCP (коды R-ERR-*) — ошибки как значения, Kind-маркер + errors.As, edge-renderer и recover-middleware, problem+json (RFC 9457), обёртка %w, port-specific в out-adapter, retry на идемпотентных.
when_to_use: Изменения в apperr/*.go, *errors.go, edge-middleware, HTTP-клиентах или любом коде с возвратом error.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью обработки ошибок (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/error-handling/error-handling-rules.md`
(`R-ERR-*`, коды едины с Java/Python/Node) и его **Go-реализации** `backend/error-handling/go/error-handling-style-guide.md`.
Помни парадигму: в Go ошибки — **значения**, не исключения; «edge-handler» = middleware, «иерархия» = `Kind`-маркер + `errors.As`,
`panic/recover` — только backstop, не control-flow.

## Зависимости

- **`.claude/docs/backend/error-handling/error-handling-rules.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/go/error-handling-style-guide.md`** — Go-реализация (apperr.Kind, errors.As/%w, chi-middleware, retry-go/gobreaker, slog, client_golang).
- Парные: `backend/rest-api/rest-api-rules.md` (`R-API-ERR-*`), `backend/validation/validation-rules.md`, `backend/resilience/resilience-rules.md`, `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-18`/`AUTH-19`), `backend/observability/observability-rules.md`.

## Инструкции

1. **Прочти** общий `error-handling-rules.md` (коды) и Go-style-guide (как это в Go). Цитируй конкретные коды (`R-ERR-WHERE-X1`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/apperr/*.go`, `**/*errors.go` — категории и типизированные ошибки (`R-ERR-HIER-*`).
   - `edge/**`, `**/middleware/*.go`, `**/render*.go` — edge-renderer + recover (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.go` (HTTP-клиенты) — port-specific, маппинг статусов/транспорта (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.go`.
   - **`Grep`**: `_ = ` (игнор ошибки), `return nil$` после `if err != nil`, `fmt.Errorf\("[^"]*%v"`, `recover\(\)` вне edge.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - Есть `Kind` + `Categorized`-маркер + `KindOf(err)` (через `errors.As`)? — `R-ERR-HIER-1/2`.
   - Доменные ошибки — типизированные структуры с `Kind() Domain`, имена по бизнес-смыслу (`InsufficientFundsError`)? — `R-ERR-HIER-3`.
   - Integration-ошибки с префиксом системы (`GatewayError`), реализуют `Unwrap()` и `Kind() Integration`? — `R-ERR-HIER-4`.
   - Контекст в полях структуры + конструктор? — `R-ERR-HIER-5`.
   - `errors.New("...")`/`fmt.Errorf("...")` без категории там, где edge ждёт Domain — `R-ERR-HIER-X1`.
   - `panic(...)` для бизнес-правила — `R-ERR-HIER-X2`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `recover()`; ошибки возвращаются вверх. — `R-ERR-WHERE-3`.
   - Out-adapter мапит транспорт/4xx (→domain)/5xx (→Integration) в port-specific с `%w`? — `R-ERR-WHERE-2b`.
   - Единый edge-renderer + `Recoverer`-middleware (panic→500)? — `R-ERR-WHERE-2a`.
   - Проглатывание: `if err != nil { slog.Error(...); return nil }`, пустой `if err != nil {}`, `_ = call()` — критика `R-ERR-WHERE-X1`.
   - `errors.New(err.Error())` / `fmt.Errorf("...%v", err)` (теряется `%w`/тип) — критика `R-ERR-WHERE-X2`.
   - `return Zero{}, nil` при фактической ошибке — критика `R-ERR-WHERE-X3`.

   ### `R-ERR-MAP-*`
   - `mapKind`: Domain→409/422, Validation→400, Integration→502/503/504, Technical→500? — `R-ERR-MAP-1..4`.
   - recover-middleware → 500? — `R-ERR-MAP-5`.
   - `Content-Type: application/problem+json` на всех error-response? — `R-ERR-MAP-*`.
   - В response нет stack / `err.Error()` низкоуровневой ошибки? — `R-ERR-MAP-X2`/`X3`.
   - `w.WriteHeader(200)` при ошибке / `{"success": false}` — критика `R-ERR-MAP-X1`.

   ### `R-ERR-LOG-*`
   - Domain → `slog.WarnContext` (не Error)? — `R-ERR-LOG-1`.
   - panic/Technical → `slog.ErrorContext` + stack? — `R-ERR-LOG-3`.
   - `slog.Error(...); return err` — `R-ERR-LOG-X1`.
   - `slog.Error(err.Error())` строкой вместо атрибута `"error", err` — `R-ERR-LOG-X2`.

   ### `R-ERR-RETRY-*`
   - `retry.RetryIf` пропускает Domain/Validation — нарушение `R-ERR-RETRY-1`.
   - retry на 4xx-производном (`InvalidPaymentRequestError`) — `R-ERR-RETRY-2`.
   - retry на write без `Idempotency-Key` — критика `R-ERR-RETRY-3` + `R-RES-RE-X1`/`AUTH-19`.

   ### `R-ERR-RESULT-*`
   - `panic/recover` как control-flow между слоями (имитация try/catch) — `R-ERR-RESULT-X1`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (client_golang `CounterVec` с `type`/`exception`)? — `R-ERR-OBS-1`.
   - `span.RecordError` + `SetStatus(codes.Error)` на ошибке? — `R-ERR-OBS-2`.
   - Алёрты только на `unexpected`/`technical` — `R-ERR-OBS-X1`.

4. **Cross-check:** retry на write без ключа → `AUTH-19`/`R-RES-RE-X1`; PII в `detail` → `AUTH-18`; problem+json → `R-API-ERR-*`; validator → `R-VLD-WHERE-1`. Рекомендуй `errcheck`+`errorlint` в линтере, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — `R-ERR-WHERE-X1` (`_ =`/проглоченный err), `R-ERR-WHERE-X3` (`Zero{}, nil`), `R-ERR-MAP-X1` (200 при ошибке), `R-ERR-MAP-X3` (SQL-текст в response), `R-ERR-RETRY-3`, отсутствие recover-middleware, `panic` для бизнес-правила.
   - **Предупреждение** — `R-ERR-WHERE-X2` (`%v` вместо `%w`, потеря типа), `R-ERR-HIER-X1`, `R-ERR-LOG-X1/X2`, Domain на Error-уровне.
   - **Замечание** — нет `app_errors_total`, ошибка без контекста, деньги во `float64`, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- validator-constraints — `ucp-go-validation-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.
- PII в логах — `ucp-go-observability-review` / `ucp-auth-review`.

$ARGUMENTS
