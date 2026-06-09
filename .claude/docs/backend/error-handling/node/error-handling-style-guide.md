# Error Handling — Node Style Guide (NestJS / TypeScript)

Реализация язык-нейтрального контракта `../error-handling-rules.md` (`R-ERR-*`) на Node-стеке (NestJS + TypeScript).
Коды правил — общие с Java и Python; здесь — как они выглядят в NestJS-сервисе. Структура слоёв UCP:
`core/` (домен, без фреймворка), `adapters/out/*` (HTTP-клиенты на axios/undici), edge (NestJS Exception Filters).

Базовый принцип (`R-ERR-1`): **исключение — часть контракта**. `catch (e) { return null }` / проглоченный `catch` —
главный антипаттерн всего гайда.

---

## 1. Иерархия исключений — `R-ERR-HIER-*`

`R-ERR-HIER-1` / `R-ERR-HIER-2` — 4 базовых типа, все наследуют один корневой `AppError`, не «голый» `Error`
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

`R-ERR-HIER-3` — имя по бизнес-смыслу, не по техформату:

```ts
// PREFER
export class OrderAlreadyShippedError extends DomainError {}
export class InsufficientFundsError extends DomainError { ... }
// AVOID
export class BusinessError extends DomainError {}   // без контекста
```

`R-ERR-HIER-4` — `IntegrationError`-наследники с префиксом системы:

```ts
// adapters/out/payment/errors.ts
export class PaymentGatewayError extends IntegrationError {}
export class PaymentGatewayUnavailableError extends PaymentGatewayError {}   // CB открыт
```

`R-ERR-HIER-5` — конструктор фиксирует контекст обязательно (типизированные поля `readonly`):

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

`R-ERR-HIER-X1` ❌ `throw new Error("что-то сломалось")` — тип теряется, фильтр не отличит от технической. Кидать конкретный наследник.

`R-ERR-HIER-X2` ❌ `throw new TypeError`/`assert(...)` как бизнес-правило в доменном коде. Бизнес-правило → `DomainError`; нарушение инварианта агрегата → ловит unit-тест, не endpoint.

---

## 2. Где throw, где catch — `R-ERR-WHERE-*`

`R-ERR-WHERE-1` — `throw` где нужно: domain handler → `DomainError`, pipe/валидатор → `InputValidationError`, out-adapter → `IntegrationError`. Не накручивать `neverthrow.Result` везде (см. §6).

`R-ERR-WHERE-2` — три места catch:

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

`R-ERR-WHERE-3` — в UseCase Handler / Domain Service / Aggregate **ноль try/catch**.

`R-ERR-WHERE-X1` ❌ `try { ... } catch (e) { this.logger.error(e); }` без re-throw в handler/service — глушит, теряет тип, возвращает «успех». Главный силент-фейл.

`R-ERR-WHERE-X2` ❌ `catch (e) { throw new Error(String(e)) }` — теряется тип и `cause`; оборачивать в типизированный наследник (`throw new PaymentGatewayError(msg, { cause: e })`).

`R-ERR-WHERE-X3` ❌ `catch (e) { return null }` / `return []` / `return undefined` — скрывает проблему ещё глубже.

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

`R-ERR-MAP-1` — `DomainError` → 409 (нарушение состояния) / 422 (нарушение инвариантов); `type` = URL на код ошибки в `docs/spec/errors/`; контекст — extension-поля.

`R-ERR-MAP-2` — `InputValidationError` → 400 c `errors`-массивом. NestJS `ValidationPipe` (class-validator) кидает `BadRequestException` — привести к нашей форме отдельным фильтром или через `exceptionFactory`:

```ts
new ValidationPipe({ exceptionFactory: (errs) => new InputValidationError(formatErrors(errs)) })
```

`R-ERR-MAP-3` — `IntegrationError` → 502 (внешка 5xx) / 503 (CB открыт / bulkhead reject) / 504 (timeout). Сырое тело внешки в `detail` **не вкладывать** (PII) — фраза + `traceId`.

`R-ERR-MAP-4` — `TechnicalError` → 500, минимум в response, детали в логи (`AUTH-18`).

`R-ERR-MAP-5` — catch-all `@Catch()` фильтр → 500, ERROR-лог + stacktrace + контекст:

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

`R-ERR-MAP-X1` ❌ HTTP 200 при ошибке с `{ success: false }` в body.
`R-ERR-MAP-X2` ❌ stacktrace в `detail` — утечка путей/версий; только в логи.
`R-ERR-MAP-X3` ❌ `String(err)` низкоуровневой ошибки как `detail` без санитизации (`error: relation "orders" does not exist`) — раскрытие схемы БД.

---

## 4. Логирование исключений — `R-ERR-LOG-*`

Логгер — `nestjs-pino` (JSON в проде), correlation через `AsyncLocalStorage` (`R-OBS-*`).

`R-ERR-LOG-1` — `DomainError` → `warn` в фильтре (ожидаемо, не баг).
`R-ERR-LOG-2` — `IntegrationError` → `warn` если CB закрыт, `error` если CB открылся.
`R-ERR-LOG-3` — `TechnicalError` и catch-all → `error` + stacktrace (`err.stack`) + контекст.
`R-ERR-LOG-4` — логируем один раз — в фильтре на edge.

`R-ERR-LOG-X1` ❌ `logger.error(e); throw e;` — двойное логирование. Либо логируй и обработай, либо проброс.
`R-ERR-LOG-X2` ❌ `logger.error(e.message)` без stack/объекта — теряется stacktrace. Передавай `err.stack` / объект ошибки.

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Retry/CB/bulkhead — `cockatiel` (TS-аналог resilience4j). На out-adapter, не в домене.

`R-ERR-RETRY-1` — по типу: `DomainError`/`InputValidationError` — никогда; `IntegrationError` — retry-safe при идемпотентности (`AUTH-19`); `TechnicalError` — обычно retry после latency.

```ts
import { retry, handleType, ExponentialBackoff } from 'cockatiel';

const policy = retry(handleType(PaymentGatewayError),                 // только 5xx/timeout, R-ERR-RETRY-3
  { maxAttempts: 3, backoff: new ExponentialBackoff({ initialDelay: 200, maxDelay: 2000 }) });

await policy.execute(() => this.payment.register(cmd));               // InvalidPaymentRequestError (4xx) НЕ ретраится
```

`R-ERR-RETRY-2` — HTTP 4xx от внешней системы — не retry; → port-specific (`InvalidPaymentRequestError`), edge отдаёт 422.
`R-ERR-RETRY-3` — 5xx и timeout — retry-safe только при идемпотентности; без `Idempotency-Key` на write — `R-RES-RE-X1`.

`R-ERR-RETRY-X1` ❌ retry-обёртка вокруг edge-фильтра — он вне retry-цикла.

---

## 6. Result-types vs exceptions — `R-ERR-RESULT-*`

`R-ERR-RESULT-1` — `neverthrow.Result` / `fp-ts Either` допустим точечно в чисто-функциональных модулях (парсер, calc engine).
`R-ERR-RESULT-2` — в цепочке UseCase Handler → Domain → Adapter — исключения, не Result.
`R-ERR-RESULT-X1` ❌ глобальная замена исключений на Result — превращает каждый вызов в `.isErr()`-разбор, ломает читаемость.

---

## 7. Observability — `R-ERR-OBS-*`

`R-ERR-OBS-1` — метрика `app_errors_total` через `prom-client`:

```ts
import { Counter } from 'prom-client';
export const appErrorsTotal = new Counter({
  name: 'app_errors_total', help: 'Application errors', labelNames: ['type', 'exception'] as const,
});
```

`R-ERR-OBS-2` — span на исключение помечается `ERROR` (OpenTelemetry):

```ts
span.setStatus({ code: SpanStatusCode.ERROR });
span.recordException(err as Error);
```

`R-ERR-OBS-3` — алёрты на необычные паттерны (рост `unexpected` → баг; `integration` → деградация внешки; `domain` для одного кода → изменилось бизнес-условие; `validation` рост → клиент сломал контракт).

`R-ERR-OBS-X1` ❌ алёрт «любое исключение в логах» — `DomainError` нормально частая; алёртить только на `unexpected`/`technical`.

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
- [ ] nestjs-pino: domain=warn, technical/unexpected=error; PII не в логах (`AUTH-16`)
- [ ] `application/problem+json` на всех error-response
- [ ] Деньги — `bigint` (минорные единицы) или decimal-библиотека, не `number`
- [ ] Spec в `docs/spec/errors/` — каждое доменное исключение имеет карточку
```
