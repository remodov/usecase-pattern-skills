---
name: ucp-node-error-handling-review
lang: node
description: Ревью обработки ошибок в NestJS-сервисе (Node/TypeScript) по UCP (коды R-ERR-*) — иерархия от AppError (не HttpException), Exception Filters per-type, problem+json (RFC 9457), port-исключения в axios out-adapter, retry через cockatiel.
when_to_use: Изменения в errors.ts, *.filter.ts, HTTP-клиентах (axios) или любом коде с catch.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок (Node / NestJS / TypeScript)

Ты ревьюишь NestJS-сервис на соответствие **общему контракту** `backend/error-handling/error-handling-rules.md`
(`R-ERR-*`, коды едины с Java/Python) и его **Node-реализации** `backend/error-handling/node/error-handling-style-guide.md`.
Главные точки: типизированная иерархия от `AppError` (не от `HttpException`), ровно три места catch, problem+json-mapping, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/error-handling-rules.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/node/error-handling-style-guide.md`** — Node-реализация (NestJS/axios/cockatiel/nestjs-pino/prom-client).
- Парные: `backend/rest-api/rest-api-rules.md` (`R-API-ERR-*`), `backend/validation/validation-rules.md`, `backend/resilience/resilience-rules.md`, `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-18`/`AUTH-19`), `backend/observability/observability-rules.md`.

## Инструкции

1. **Прочти** общий `error-handling-rules.md` (коды) и Node-style-guide (как это в NestJS). Цитируй конкретные коды (`R-ERR-WHERE-X1`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/errors.ts`, `core/**/errors.ts` — иерархия (`R-ERR-HIER-*`).
   - `**/*.filter.ts` (ExceptionFilter), `APP_FILTER`-провайдеры — edge (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.ts` (axios/HttpService-клиенты) — port-specific, ловля axios-ошибок (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.ts`.
   - **`Grep`**: `catch\s*\(` в `core/` и `} catch` без `throw` ниже — потенциальные `R-ERR-WHERE-X1`/`X3`.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - 4 базовых типа наследуют один `AppError`, **не** `HttpException` и не голый `Error`? — `R-ERR-HIER-1/2`.
   - Доменные именуются по бизнес-смыслу (`InsufficientFundsError`), не `BusinessError`? — `R-ERR-HIER-3`.
   - `IntegrationError`-наследники с префиксом системы (`PaymentGatewayError`)? — `R-ERR-HIER-4`.
   - Контекст в конструкторе (`readonly`-поля)? Не пустые? — `R-ERR-HIER-5`.
   - `throw new Error(...)` — `R-ERR-HIER-X1`.
   - `throw new TypeError`/`assert(...)` как бизнес-правило в core — `R-ERR-HIER-X2`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `try/catch`. Любой проглоченный catch — критика `R-ERR-WHERE-X1`.
   - В `adapters/out/`: `axios.isAxiosError(e)` → port-specific (4xx→domain `Invalid…Error`, 5xx/timeout→`<System>Error`, `{ cause: e }`)? Иначе нарушение `R-ERR-WHERE-2b`.
   - Per-type Exception Filters + catch-all `@Catch()`, зарегистрированы через `APP_FILTER`? — `R-ERR-WHERE-2a`.
   - `catch { return null }` / `return []` / `return undefined` — критика `R-ERR-WHERE-X3`.
   - `catch (e) { logger.error(e) }` без re-throw — критика `R-ERR-WHERE-X1`.
   - `catch (e) { throw new Error(String(e)) }` (теряется тип/cause) — критика `R-ERR-WHERE-X2`.

   ### `R-ERR-MAP-*`
   - Filter `DomainError` → 409/422? — `R-ERR-MAP-1`.
   - `ValidationPipe` → `InputValidationError`/`BadRequestException` → 400 + `errors`? — `R-ERR-MAP-2`.
   - `IntegrationError` → 502/503/504 по подтипу? — `R-ERR-MAP-3`.
   - catch-all `@Catch()` → 500? — `R-ERR-MAP-5`.
   - Все error-response `application/problem+json` (`res.type(...)`)? — `R-ERR-MAP-*`.
   - В response нет stacktrace / `String(err)` низкоуровневой ошибки? — `R-ERR-MAP-X2`/`X3`.
   - `res.status(200)` в фильтре / `{ success: false }` — критика `R-ERR-MAP-X1`.

   ### `R-ERR-LOG-*`
   - `DomainError` → `logger.warn` (не error)? — `R-ERR-LOG-1`.
   - catch-all → `logger.error` со `stack`? — `R-ERR-LOG-3`.
   - `logger.error(e); throw e;` — `R-ERR-LOG-X1`.
   - `logger.error(e.message)` без stack — `R-ERR-LOG-X2`.

   ### `R-ERR-RETRY-*`
   - `cockatiel` retry `handleType` на `DomainError`/`InputValidationError` — нарушение `R-ERR-RETRY-1`.
   - retry на 4xx-производном — `R-ERR-RETRY-2`.
   - retry на write без `Idempotency-Key` — критика `R-ERR-RETRY-3` + `R-RES-RE-X1`/`AUTH-19`.

   ### `R-ERR-RESULT-*`
   - Глобальный `neverthrow`/`Either` вместо исключений в цепочке Handler→Domain→Adapter — `R-ERR-RESULT-X1`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (prom-client `Counter` с `type`/`exception`) экспонирована? — `R-ERR-OBS-1`.
   - `span.recordException` + `setStatus(ERROR)` на ошибке? — `R-ERR-OBS-2`.
   - Алёрты только на `unexpected`/`technical` — `R-ERR-OBS-X1`.

4. **Cross-check:** retry на write без ключа → `AUTH-19`/`R-RES-RE-X1`; PII в `detail` → `AUTH-18`; problem+json формат → `R-API-ERR-*`; class-validator → `R-VLD-WHERE-1`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — `R-ERR-WHERE-X1` (проглоченный catch), `R-ERR-WHERE-X3` (`return null` в catch), `R-ERR-MAP-X1` (200 при ошибке), `R-ERR-MAP-X3` (SQL-текст в response), `R-ERR-RETRY-3` (retry write без ключа), отсутствие catch-all `@Catch()`, домен наследует `HttpException`.
   - **Предупреждение** — `R-ERR-HIER-X1/X2`, `R-ERR-WHERE-X2` (потеря cause), `R-ERR-LOG-X1/X2`, DomainError на error-уровне.
   - **Замечание** — нет `app_errors_total`, конструктор без контекста, деньги в `number`, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- class-validator constraints — `ucp-node-validation-review` (когда появится).
- Retry-policy конфиг — `ucp-node-resilience-review`.
- PII в логах — `ucp-node-observability-review` / `ucp-auth-review`.

$ARGUMENTS
