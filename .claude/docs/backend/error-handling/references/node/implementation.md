# Error Handling — реализация на Node (NestJS / TypeScript)

Реализация язык-нейтрального контракта `../spec.md` (`R-ERR-*`) на Node-стеке (NestJS + TypeScript).
Коды правил — общие с Java и Python; здесь — как они выглядят в NestJS-сервисе. Структура слоёв UCP:
`core/` (домен, без фреймворка), `adapters/out/*` (HTTP-клиенты на axios/undici), edge (NestJS Exception Filters).

Базовый принцип (`error-handling/exceptions-are-part-of-contract`): **исключение — часть контракта**. `catch (e) { return null }` / проглоченный `catch` —
главный антипаттерн всего гайда.

---

## 1. Иерархия исключений — `R-ERR-HIER-*`

`error-handling/four-exception-kinds` / `error-handling/four-exception-kinds` — 4 базовых типа, все наследуют один корневой `AppError`, не «голый» `Error`
и **не** `HttpException` из NestJS (HTTP-семантика — на edge, не в домене):

```ts
// core/errors.ts
export abstract class AppError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = new.target.name;            // корректное имя в stacktrace
  }
}

export abstract class DomainError extends AppError {}        // 409/422, no-retry
export class InputValidationError extends AppError {}        // 400, no-retry
export abstract class IntegrationError extends AppError {}   // 502/503/504, retry-safe
export class TechnicalError extends AppError {}              // 500, retry-возможно
```

`DomainError` живёт в `core/`, `IntegrationError`-наследники — в каждом `adapters/out/<system>/`,
`InputValidationError` — на edge.

`error-handling/domain-exception-named-by-meaning` — имя по бизнес-смыслу, не по техформату:

```ts
// PREFER
export class OrderAlreadyShippedError extends DomainError {}
export class InsufficientFundsError extends DomainError { ... }
// AVOID
export class BusinessError extends DomainError {}   // без контекста
```

`error-handling/integration-exception-names-system` — `IntegrationError`-наследники с префиксом системы:

```ts
// adapters/out/payment/errors.ts
export class PaymentGatewayError extends IntegrationError {}
export class PaymentGatewayUnavailableError extends PaymentGatewayError {}   // CB открыт
```

`error-handling/exception-carries-context` — конструктор фиксирует контекст обязательно (типизированные поля `readonly`):

```ts
export class InsufficientFundsError extends DomainError {
  constructor(
    readonly customerId: string,
    readonly requested: bigint,        // деньги — bigint (минорные единицы) или Decimal-библиотека, не number
    readonly available: bigint,
  ) {
    super(`Insufficient funds: customer=${customerId}, requested=${requested}, available=${available}`);
  }
}
```

`error-handling/no-bare-base-exceptions` ❌ `throw new Error("что-то сломалось")` — тип теряется, фильтр не отличит от технической. Кидать конкретный наследник.

`error-handling/no-bare-base-exceptions` ❌ `throw new TypeError`/`assert(...)` как бизнес-правило в доменном коде. Бизнес-правило → `DomainError`; нарушение инварианта агрегата → ловит unit-тест, не endpoint.

---

## 2. Где throw, где catch — `R-ERR-WHERE-*`

`error-handling/throw-where-detected` — `throw` где нужно: domain handler → `DomainError`, pipe/валидатор → `InputValidationError`, out-adapter → `IntegrationError`. Не накручивать `neverthrow.Result` везде (см. §6).

`error-handling/catch-in-three-places-only` — три места catch:

**a) Edge — NestJS Exception Filters** (per-type, регистрируются глобально через `APP_FILTER`):

```ts
// edge/filters/domain-error.filter.ts
@Catch(DomainError)
export class DomainErrorFilter implements ExceptionFilter {
  catch(err: DomainError, host: ArgumentsHost): void {
    const res = host.switchToHttp().getResponse<Response>();
    this.logger.warn(`domain rule violated: ${err.message}`);          // R-ERR-LOG-1
    appErrorsTotal.inc({ type: 'domain', exception: err.name });
    sendProblem(res, 422, 'Operation cannot be completed', 'insufficient funds', {
      type: 'https://api.example.com/errors/insufficient-funds',
    });
  }
}
```

Регистрация (most-specific filter выигрывает; обязателен catch-all `@Catch()`):

```ts
// app.module.ts
providers: [
  { provide: APP_FILTER, useClass: UnexpectedFilter },     // @Catch() — catch-all, регистрируется первым
  { provide: APP_FILTER, useClass: IntegrationErrorFilter },
  { provide: APP_FILTER, useClass: DomainErrorFilter },
]
```

**b) Integration boundary — HTTP-адаптер** (axios) ловит низкоуровневое, кидает port-specific:

```ts
// adapters/out/payment/payment.client.ts
@Injectable()
export class PaymentClientAdapter implements PaymentPort {
  async register(cmd: RegisterCommand): Promise<RegisterResult> {
    try {
      const { data } = await this.http.axiosRef.post('/register', toApi(cmd));
      return toDomain(data);
    } catch (e) {
      if (axios.isAxiosError(e)) {
        const status = e.response?.status;
        if (status && status < 500) {                                 // 4xx → domain, R-ERR-RETRY-2
          throw new InvalidPaymentRequestError(cmd.orderId, e.response?.data);
        }
        throw new PaymentGatewayError('payment 5xx/timeout', { cause: e });
      }
      throw e;                                                        // не axios — пробрасываем как есть
    }
  }
}
```

**c) Резильянс-обёртка** — cockatiel (retry / circuitBreaker / bulkhead), формальный catch (см. §5).

`error-handling/catch-in-three-places-only` — в UseCase Handler / Domain Service / Aggregate **ноль try/catch**.

`error-handling/catch-does-not-swallow` ❌ `try { ... } catch (e) { this.logger.error(e); }` без re-throw в handler/service — глушит, теряет тип, возвращает «успех». Главный силент-фейл.

`error-handling/catch-does-not-swallow` ❌ `catch (e) { throw new Error(String(e)) }` — теряется тип и `cause`; оборачивать в типизированный наследник (`throw new PaymentGatewayError(msg, { cause: e })`).

`error-handling/catch-does-not-swallow` ❌ `catch (e) { return null }` / `return []` / `return undefined` — скрывает проблему ещё глубже.

---

## 3. Mapping в ProblemDetails — `R-ERR-MAP-*`

RFC 9457 вручную (NestJS не даёт ProblemDetail). Хелпер:

```ts
// edge/problem.ts
export function sendProblem(res: Response, status: number, title: string, detail: string,
                            ext: Record<string, unknown> = {}): void {
  res.status(status).type('application/problem+json').json({
    type: 'about:blank', title, status, detail, traceId: getTraceId(), ...ext,
  });
}
```

`error-handling/domain-and-validation-mapping` — `DomainError` → 409 (нарушение состояния) / 422 (нарушение инвариантов); `type` = URL на код ошибки в `docs/spec/errors/`; контекст — extension-поля.

`error-handling/domain-and-validation-mapping` — `InputValidationError` → 400 c `errors`-массивом. NestJS `ValidationPipe` (class-validator) кидает `BadRequestException` — привести к нашей форме отдельным фильтром или через `exceptionFactory`:

```ts
new ValidationPipe({ exceptionFactory: (errs) => new InputValidationError(formatErrors(errs)) })
```

`error-handling/integration-and-technical-mapping` — `IntegrationError` → 502 (внешка 5xx) / 503 (CB открыт / bulkhead reject) / 504 (timeout). Сырое тело внешки в `detail` **не вкладывать** (PII) — фраза + `traceId`.

`error-handling/integration-and-technical-mapping` — `TechnicalError` → 500, минимум в response, детали в логи (`auth-patterns/error-response-hides-cause`).

`error-handling/integration-and-technical-mapping` — catch-all `@Catch()` фильтр → 500, ERROR-лог + stacktrace + контекст:

```ts
@Catch()
export class UnexpectedFilter implements ExceptionFilter {
  catch(err: unknown, host: ArgumentsHost): void {
    const res = host.switchToHttp().getResponse<Response>();
    this.logger.error('unexpected error', err instanceof Error ? err.stack : String(err));  // R-ERR-LOG-3
    appErrorsTotal.inc({ type: 'unexpected', exception: (err as Error)?.name ?? 'Unknown' });
    sendProblem(res, 500, 'Internal Server Error', 'internal error');
  }
}
```

`error-handling/no-success-code-for-failure` ❌ HTTP 200 при ошибке с `{ success: false }` в body.
`error-handling/integration-and-technical-mapping` ❌ stacktrace в `detail` — утечка путей/версий; только в логи.
`error-handling/integration-and-technical-mapping` ❌ `String(err)` низкоуровневой ошибки как `detail` без санитизации (`error: relation "orders" does not exist`) — раскрытие схемы БД.

---

## 4. Логирование исключений — `R-ERR-LOG-*`

Логгер — `nestjs-pino` (JSON в проде), correlation через `AsyncLocalStorage` (`R-OBS-*`).

`error-handling/log-level-matches-kind` — `DomainError` → `warn` в фильтре (ожидаемо, не баг).
`error-handling/log-level-matches-kind` — `IntegrationError` → `warn` если CB закрыт, `error` если CB открылся.
`error-handling/log-level-matches-kind` — `TechnicalError` и catch-all → `error` + stacktrace (`err.stack`) + контекст.
`error-handling/log-once-with-exception` — логируем один раз — в фильтре на edge.

`error-handling/log-once-with-exception` ❌ `logger.error(e); throw e;` — двойное логирование. Либо логируй и обработай, либо проброс.
`error-handling/log-once-with-exception` ❌ `logger.error(e.message)` без stack/объекта — теряется stacktrace. Передавай `err.stack` / объект ошибки.

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Retry/CB/bulkhead — `cockatiel` (TS-аналог resilience4j). На out-adapter, не в домене.

`error-handling/retry-semantics-by-kind` — по типу: `DomainError`/`InputValidationError` — никогда; `IntegrationError` — retry-safe при идемпотентности (`auth-patterns/money-commands-need-idempotency-key`); `TechnicalError` — обычно retry после latency.

```ts
import { retry, handleType, ExponentialBackoff } from 'cockatiel';

const policy = retry(handleType(PaymentGatewayError),                 // только 5xx/timeout, R-ERR-RETRY-3
  { maxAttempts: 3, backoff: new ExponentialBackoff({ initialDelay: 200, maxDelay: 2000 }) });

await policy.execute(() => this.payment.register(cmd));               // InvalidPaymentRequestError (4xx) НЕ ретраится
```

`error-handling/retry-semantics-by-kind` — HTTP 4xx от внешней системы — не retry; → port-specific (`InvalidPaymentRequestError`), edge отдаёт 422.
`error-handling/retry-semantics-by-kind` — 5xx и timeout — retry-safe только при идемпотентности; без `Idempotency-Key` на write — `resilience/retry-only-when-safe`.

`error-handling/no-retry-at-edge` ❌ retry-обёртка вокруг edge-фильтра — он вне retry-цикла.

---

## 6. Result-types vs exceptions — `R-ERR-RESULT-*`

`error-handling/result-type-is-local-choice` — `neverthrow.Result` / `fp-ts Either` допустим точечно в чисто-функциональных модулях (парсер, calc engine).
`error-handling/result-type-is-local-choice` — в цепочке UseCase Handler → Domain → Adapter — исключения, не Result.
`error-handling/result-type-is-local-choice` ❌ глобальная замена исключений на Result — превращает каждый вызов в `.isErr()`-разбор, ломает читаемость.

---

## 7. Observability — `R-ERR-OBS-*`

`error-handling/errors-counted-by-kind` — метрика `app_errors_total` через `prom-client`:

```ts
import { Counter } from 'prom-client';
export const appErrorsTotal = new Counter({
  name: 'app_errors_total', help: 'Application errors', labelNames: ['type', 'exception'] as const,
});
```

`error-handling/trace-span-marked-error` — span на исключение помечается `ERROR` (OpenTelemetry):

```ts
span.setStatus({ code: SpanStatusCode.ERROR });
span.recordException(err as Error);
```

`error-handling/alert-on-patterns-not-exceptions` — алёрты на необычные паттерны (рост `unexpected` → баг; `integration` → деградация внешки; `domain` для одного кода → изменилось бизнес-условие; `validation` рост → клиент сломал контракт).

`error-handling/alert-on-patterns-not-exceptions` ❌ алёрт «любое исключение в логах» — `DomainError` нормально частая; алёртить только на `unexpected`/`technical`.

---

## Чеклист подключения к новому сервису (Node/NestJS)

- [ ] 4 базовых исключения в `core/errors.ts` от общего `AppError` (не от `HttpException`)
- [ ] Доменные наследники с `readonly`-контекстом, имена по бизнес-смыслу
- [ ] Per-type Exception Filters + catch-all `@Catch()`, зарегистрированы через `APP_FILTER`
- [ ] Catch-all → 500 + `logger.error(stack)` + `traceId`
- [ ] `ValidationPipe` с `exceptionFactory` → `InputValidationError` → 400
- [ ] axios out-adapter ловит `isAxiosError` → port-specific (4xx→domain, 5xx/timeout→IntegrationError), `{ cause: e }`
- [ ] Никаких try/catch в UseCase Handler / Domain Service / Aggregate
- [ ] `cockatiel` retry только на идемпотентных Integration-вызовах, `handleType(<System>Error)` на 5xx-типе
- [ ] `app_errors_total{type,exception}` (prom-client); `span.recordException` на ошибке
- [ ] nestjs-pino: domain=warn, technical/unexpected=error; PII не в логах (`auth-patterns/no-pii-in-logs-and-events`)
- [ ] `application/problem+json` на всех error-response
- [ ] Деньги — `bigint` (минорные единицы) или decimal-библиотека, не `number`
- [ ] Spec в `docs/spec/errors/` — каждое доменное исключение имеет карточку
```
