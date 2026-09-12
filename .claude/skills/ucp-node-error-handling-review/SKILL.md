---
name: ucp-node-error-handling-review
lang: node
description: Ревью обработки ошибок в NestJS-сервисе (Node/TypeScript) по UCP (требования error-handling/*) — иерархия от AppError (не HttpException), Exception Filters per-type, problem+json (RFC 9457), port-исключения в axios out-adapter, retry через cockatiel.
when_to_use: Изменения в errors.ts, *.filter.ts, HTTP-клиентах (axios) или любом коде с catch.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок (Node / NestJS / TypeScript)

Ты ревьюишь NestJS-сервис на соответствие **общему контракту** `backend/error-handling/spec.md`
(`R-ERR-*`, коды едины с Java/Python) и его **Node-реализации** `backend/error-handling/references/node/implementation.md`.
Главные точки: типизированная иерархия от `AppError` (не от `HttpException`), ровно три места catch, problem+json-mapping, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/spec.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/references/node/implementation.md`** — Node-реализация (NestJS/axios/cockatiel/nestjs-pino/prom-client).
- Парные: `backend/rest-api/spec.md` (`R-API-ERR-*`), `backend/validation/spec.md`, `backend/resilience/spec.md`, `backend/auth-patterns/spec.md` (`auth-patterns/error-response-hides-cause`/`auth-patterns/money-commands-need-idempotency-key`), `backend/observability/spec.md`.

## Инструкции

1. **Прочти** общий `error-handling/spec.md` и `references/node/implementation.md` (как это в NestJS). Цитируй конкретные коды (`error-handling/catch-does-not-swallow`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/errors.ts`, `core/**/errors.ts` — иерархия (`R-ERR-HIER-*`).
   - `**/*.filter.ts` (ExceptionFilter), `APP_FILTER`-провайдеры — edge (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.ts` (axios/HttpService-клиенты) — port-specific, ловля axios-ошибок (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.ts`.
   - **`Grep`**: `catch\s*\(` в `core/` и `} catch` без `throw` ниже — потенциальные `error-handling/catch-does-not-swallow`/`X3`.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - 4 базовых типа наследуют один `AppError`, **не** `HttpException` и не голый `Error`? — `R-ERR-HIER-1/2`.
   - Доменные именуются по бизнес-смыслу (`InsufficientFundsError`), не `BusinessError`? — `error-handling/domain-exception-named-by-meaning`.
   - `IntegrationError`-наследники с префиксом системы (`PaymentGatewayError`)? — `error-handling/integration-exception-names-system`.
   - Контекст в конструкторе (`readonly`-поля)? Не пустые? — `error-handling/exception-carries-context`.
   - `throw new Error(...)` — `error-handling/no-bare-base-exceptions`.
   - `throw new TypeError`/`assert(...)` как бизнес-правило в core — `error-handling/no-bare-base-exceptions`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `try/catch`. Любой проглоченный catch — критика `error-handling/catch-does-not-swallow`.
   - В `adapters/out/`: `axios.isAxiosError(e)` → port-specific (4xx→domain `Invalid…Error`, 5xx/timeout→`<System>Error`, `{ cause: e }`)? Иначе нарушение `R-ERR-WHERE-2b`.
   - Per-type Exception Filters + catch-all `@Catch()`, зарегистрированы через `APP_FILTER`? — `R-ERR-WHERE-2a`.
   - `catch { return null }` / `return []` / `return undefined` — критика `error-handling/catch-does-not-swallow`.
   - `catch (e) { logger.error(e) }` без re-throw — критика `error-handling/catch-does-not-swallow`.
   - `catch (e) { throw new Error(String(e)) }` (теряется тип/cause) — критика `error-handling/catch-does-not-swallow`.

   ### `R-ERR-MAP-*`
   - Filter `DomainError` → 409/422? — `error-handling/domain-and-validation-mapping`.
   - `ValidationPipe` → `InputValidationError`/`BadRequestException` → 400 + `errors`? — `error-handling/domain-and-validation-mapping`.
   - `IntegrationError` → 502/503/504 по подтипу? — `error-handling/integration-and-technical-mapping`.
   - catch-all `@Catch()` → 500? — `error-handling/integration-and-technical-mapping`.
   - Все error-response `application/problem+json` (`res.type(...)`)? — `R-ERR-MAP-*`.
   - В response нет stacktrace / `String(err)` низкоуровневой ошибки? — `error-handling/integration-and-technical-mapping`/`X3`.
   - `res.status(200)` в фильтре / `{ success: false }` — критика `error-handling/no-success-code-for-failure`.

   ### `R-ERR-LOG-*`
   - `DomainError` → `logger.warn` (не error)? — `error-handling/log-level-matches-kind`.
   - catch-all → `logger.error` со `stack`? — `error-handling/log-level-matches-kind`.
   - `logger.error(e); throw e;` — `error-handling/log-once-with-exception`.
   - `logger.error(e.message)` без stack — `error-handling/log-once-with-exception`.

   ### `R-ERR-RETRY-*`
   - `cockatiel` retry `handleType` на `DomainError`/`InputValidationError` — нарушение `error-handling/retry-semantics-by-kind`.
   - retry на 4xx-производном — `error-handling/retry-semantics-by-kind`.
   - retry на write без `Idempotency-Key` — критика `error-handling/retry-semantics-by-kind` + `resilience/retry-only-when-safe`/`auth-patterns/money-commands-need-idempotency-key`.

   ### `R-ERR-RESULT-*`
   - Глобальный `neverthrow`/`Either` вместо исключений в цепочке Handler→Domain→Adapter — `error-handling/result-type-is-local-choice`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (prom-client `Counter` с `type`/`exception`) экспонирована? — `error-handling/errors-counted-by-kind`.
   - `span.recordException` + `setStatus(ERROR)` на ошибке? — `error-handling/trace-span-marked-error`.
   - Алёрты только на `unexpected`/`technical` — `error-handling/alert-on-patterns-not-exceptions`.

4. **Cross-check:** retry на write без ключа → `auth-patterns/money-commands-need-idempotency-key`/`resilience/retry-only-when-safe`; PII в `detail` → `auth-patterns/error-response-hides-cause`; problem+json формат → `R-API-ERR-*`; class-validator → `validation/input-validated-at-edge`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — `error-handling/catch-does-not-swallow` (проглоченный catch), `error-handling/catch-does-not-swallow` (`return null` в catch), `error-handling/no-success-code-for-failure` (200 при ошибке), `error-handling/integration-and-technical-mapping` (SQL-текст в response), `error-handling/retry-semantics-by-kind` (retry write без ключа), отсутствие catch-all `@Catch()`, домен наследует `HttpException`.
   - **Предупреждение** — `R-ERR-HIER-X1/X2`, `error-handling/catch-does-not-swallow` (потеря cause), `R-ERR-LOG-X1/X2`, DomainError на error-уровне.
   - **Замечание** — нет `app_errors_total`, конструктор без контекста, деньги в `number`, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- class-validator constraints — `ucp-node-validation-review`.
- Retry-policy конфиг — `ucp-node-resilience-review`.
- PII в логах — `ucp-node-observability-review` / `ucp-auth-review`.

$ARGUMENTS
