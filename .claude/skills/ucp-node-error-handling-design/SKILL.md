---
name: ucp-node-error-handling-design
lang: node
description: Спроектировать обработку ошибок NestJS-сервиса (Node/TypeScript) по UCP (коды R-ERR-*) — иерархия от AppError, Exception Filters с mapping в problem+json (RFC 9457), port-исключения в axios out-adapter, retry через cockatiel, prom-client + pino.
when_to_use: Триггеры — «настрой обработку ошибок в NestJS», «добавь exception filters». При старте сервиса или миграции catch→null-кода.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(pnpm*) Bash(npx*)
---

# Проектирование обработки ошибок (Node / NestJS / TypeScript)

Ты создаёшь / расширяешь обработку ошибок в NestJS-сервисе согласно **общему контракту**
`backend/error-handling/error-handling-rules.md` (`R-ERR-*`) и его **Node-реализации**
`backend/error-handling/node/error-handling-style-guide.md`. Цель — единая стратегия: типизированная иерархия,
ровно три места catch (edge-filter / axios out-adapter / резильянс-обёртка), консистентный problem+json-mapping, наблюдаемость.

Не делает: валидацию входа (`ucp-node-validation-design`), резилианс-обвязку (`ucp-node-resilience-design`),
маскирование PII в логах (`ucp-node-observability-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — общий контракт, коды `R-ERR-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/error-handling/node/error-handling-style-guide.md` — Node-реализация (NestJS/axios/cockatiel/pino), открывай точечно по разделу.
   - `.claude/docs/backend/rest-api/rest-api-rules.md` — `R-API-ERR-*` для формата problem+json.
   - `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` — `AUTH-19` (идемпотентность), `AUTH-18` (PII в response).

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на NestJS:
   - `core/` — базовые ошибки (`AppError` + 4 типа) + доменные наследники; без NestJS-импортов.
   - `edge/filters/` — Exception Filters, `problem.ts`.
   - `adapters/out/<system>/` — axios-клиент + port-specific ошибки.

3. **Аудит текущего состояния** (что есть / что предстоит): базовые ошибки от `AppError` (не от `HttpException`) (`R-ERR-HIER-1/2`), доменные с контекстом (`R-ERR-HIER-3/5`), per-type filters + catch-all через `APP_FILTER` (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`), axios-адаптеры мапят ошибки в port-specific (`R-ERR-WHERE-2b`), нет `try/catch` в core (`R-ERR-WHERE-X1`), метрика `app_errors_total` (`R-ERR-OBS-1`).

4. **Произведи код** (полные `.ts`-файлы; strict TypeScript; без комментариев в коде — соответствие выражается именами/типами/структурой; коды правил в комментариях НЕ цитируй).

   ### 4.1 `core/errors.ts` — корень + 4 типа
   `AppError extends Error` (с `this.name = new.target.name`) и `DomainError` / `InputValidationError` / `IntegrationError` / `TechnicalError` от него. **Не наследовать `HttpException`** — HTTP-семантика на edge.

   ### 4.2 Доменные наследники с контекстом
   `readonly`-поля в конструкторе (`InsufficientFundsError(customerId, requested, available)`), имена по бизнес-смыслу. Деньги — `bigint`/decimal-библиотека, не `number`.

   ### 4.3 `edge/problem.ts` + `edge/filters/*.filter.ts`
   Хелпер `sendProblem(res, status, title, detail, ext)` → `res.type('application/problem+json').json(...)`. Per-type фильтры (`@Catch(DomainError)`→422/409, `@Catch(InputValidationError)`→400, `@Catch(IntegrationError)`→502/503/504) + catch-all `@Catch()`→500 (`logger.error(stack)` + traceId). Регистрация через `APP_FILTER`-провайдеры.

   ### 4.4 Port-specific ошибки в axios-адаптерах
   `<System>Error extends IntegrationError`; в адаптере `if (axios.isAxiosError(e))` (4xx → domain `Invalid…Error`, 5xx/timeout → `<System>Error` с `{ cause: e }`); не-axios — пробрасывать.

   ### 4.5 Убрать `try/catch` из Handler/Service/Aggregate
   Доменные `throw`, integration-вызовы бросают `IntegrationError`. Перехват — только в фильтре / адаптере.

   ### 4.6 Retry (если есть исходящие вызовы)
   `cockatiel` `retry(handleType(<System>Error), ...)` только на идемпотентных вызовах; 4xx-производные (`Invalid…Error`) не ретраятся (`R-ERR-RETRY-2/3`).

   ### 4.7 Observability
   `app_errors_total` (`prom-client` `Counter` с `type`/`exception`); в catch-all и domain-filter — `.inc({...})`; `span.recordException` + `setStatus(ERROR)`.

   ### 4.8 ValidationPipe
   Глобальный `ValidationPipe` с `exceptionFactory` → `InputValidationError` (а не дефолтный `BadRequestException`), чтобы 400 шёл через наш problem+json (`R-ERR-MAP-2`).

5. **Самопроверка** — пройдись по чеклисту из `node/error-handling-style-guide.md` §«Чеклист подключения».

6. **Финальный шаг:** предложи «запусти `ucp-node-error-handling-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `catch { return null }` / проглоченный `catch` (`R-ERR-WHERE-X1`/`X3`).
- `throw new Error(...)` / `throw new Error(String(e))` без `cause` (`R-ERR-HIER-X1`/`R-ERR-WHERE-X2`).
- домен наследует `HttpException` (HTTP-семантика в core).
- `res.status(200)` при ошибке (`R-ERR-MAP-X1`).
- `String(err)` низкоуровневой ошибки в `detail` (`R-ERR-MAP-X3`).
- деньги в `number`; retry на write без `Idempotency-Key` (`R-ERR-RETRY-3`).

После работы скилла — обязательно `ucp-node-error-handling-review` для верификации.

$ARGUMENTS
