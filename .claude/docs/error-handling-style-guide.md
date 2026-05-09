# Error Handling Style Guide

Единая стратегия обработки ошибок для Java/Spring-сервисов по Use Case Pattern. Иерархия исключений, где throw / где catch, mapping в `ProblemDetails` (RFC 9457), retry/no-retry, наблюдаемость. Каждое правило имеет код `R-ERR-*` — скилл `ucp-error-handling-review` цитирует их в findings.

Гайд намеренно широкий — он сшивает то, что разбросано по другим гайдам: REST-формат ошибок (`R-API-ERR-*`), валидация (`R-VLD-*`), резилианс (`R-RES-*`), security-mapping (`AUTH-6`). Здесь — общая модель: какие типы исключений в коде, где их обрабатывают, как они становятся ответом наружу.

Базовый принцип (`R-ERR-1`): **исключение — это часть контракта, не неожиданность**. Каждое исключение в публичной сигнатуре метода имеет тип, документированный смысл, и однозначный handler. Голый `catch (Exception e) { log.error(); return null; }` — главный антипаттерн всего гайда.

`R-ERR-2` **Только три места catch**:
1. **Edge** — `@RestControllerAdvice` для REST, `@KafkaListener`-error-handler для Kafka, `@Scheduled`-обёртка для cron. Превращает domain/integration-исключения в response/retry/skip.
2. **Integration boundary** — out-adapter ловит `HttpServerErrorException`/`SQLException`/`KafkaException`, превращает в свои port-specific exceptions (`PaymentGatewayException`, `CatalogPortException`).
3. **Резильянс-обёртка** — `@CircuitBreaker(fallbackMethod = ...)` (`R-RES-CB-*`), retry — это формальный catch, описанный конфигом, не try-catch в коде.

Везде ещё в коде — **никаких try-catch**. Доменное исключение проходит насквозь до edge.

---

## 1. Иерархия исключений — `R-ERR-HIER-*`

`R-ERR-HIER-1` **4 базовых типа** в проекте, остальное — наследники:

| Тип | Когда | HTTP-mapping | Retry-safe |
|---|---|---|---|
| `DomainException` | Бизнес-правило нарушено (нельзя отменить уже-отгруженный заказ, недостаточно средств) | 409 / 422 | ❌ нет |
| `ValidationException` | Невалидный input на edge (поле пустое, формат не тот) | 400 | ❌ нет |
| `IntegrationException` | Внешняя система отвечает неожиданно (5xx, timeout, malformed) | 502 / 503 / 504 | ✅ обычно |
| `TechnicalException` | Наша внутренняя проблема (БД unreachable, OOM proxy) | 500 | ✅ возможно |

`DomainException` и его наследники живут в `core/`. `IntegrationException` — в каждом `adapter-out-*` (наследник в своём пакете). `ValidationException` — в edge (controller layer). `TechnicalException` — в коре, но используется редко (90% технических ошибок ловится edge-handler-ом без явного объявления).

`R-ERR-HIER-2` **Все четыре — `RuntimeException`-наследники**. Не `Exception`. Checked-exceptions не используются — они вынуждают засорять сигнатуры или оборачивать в RuntimeException и теряют тип. Это командное правило, обсуждению не подлежит.

`R-ERR-HIER-3` **Доменные исключения именуются по бизнес-смыслу**, не по техническому формату:
- ✅ `OrderAlreadyShippedException`, `InsufficientFundsException`, `CustomerNotEligibleException`
- ❌ `BusinessException`, `IllegalStateException`, `ValidationFailedException` (без контекста)

Имя должно отвечать на вопрос «**что** нарушено», не «**как** упало».

`R-ERR-HIER-4` **`IntegrationException`-наследники имеют префикс системы**: `PaymentGatewayException`, `SberRegisterException`, `CatalogPortException`. Это позволяет в edge-handler различать «проблема у платёжки» от «проблема у каталога» и реагировать раздельно.

`R-ERR-HIER-5` **Конструкторы фиксируют контекст обязательно**. Не `new InsufficientFundsException()`, а `new InsufficientFundsException(customerId, requestedAmount, availableBalance)`. Лог-stacktrace + структурный контекст в одной точке возникновения.

```java
public final class InsufficientFundsException extends DomainException {

    private final CustomerId customerId;
    private final Money requested;
    private final Money available;

    public InsufficientFundsException(CustomerId customerId, Money requested, Money available) {
        super("Insufficient funds: customer=%s, requested=%s, available=%s"
            .formatted(customerId, requested, available));
        this.customerId = customerId;
        this.requested = requested;
        this.available = available;
    }
    // getters через @Getter (JS-6.3)
}
```

`R-ERR-HIER-X1` ❌ **`throw new RuntimeException("Что-то сломалось")`** в коде. Тип теряется, edge-handler не сможет различить от технической проблемы. Кидаем конкретный наследник.

`R-ERR-HIER-X2` ❌ **`throw new IllegalStateException(...)` в доменном коде**. Это сигнал «программистская ошибка» (логика противоречит сама себе). Если это бизнес-правило — `DomainException`-наследник; если это invariant violation в агрегате — отдельная категория, ловит unit-тест, не endpoint.

---

## 2. Где throw, где catch — `R-ERR-WHERE-*`

`R-ERR-WHERE-1` **Throw — везде где нужно**. Domain handler бросает `DomainException`, validator бросает `ValidationException`, out-adapter бросает `IntegrationException`. Не накручиваем `Optional<Result, Error>` или sealed-interface-Result везде только ради избежания исключений (`R-ERR-RESULT-X1`).

`R-ERR-WHERE-2` **Catch только в трёх местах** (см. `R-ERR-2`):

### a) `@RestControllerAdvice` — REST edge

Один `@RestControllerAdvice`-класс на сервис (`GlobalExceptionHandler`), отдельные `@ExceptionHandler`-методы под базовые типы. Mapping в `ProblemDetails` (см. §3).

```java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(DomainException.class)
    ProblemDetail handleDomain(DomainException ex) { ... }

    @ExceptionHandler(ValidationException.class)
    ProblemDetail handleValidation(ValidationException ex) { ... }

    @ExceptionHandler(IntegrationException.class)
    ProblemDetail handleIntegration(IntegrationException ex) { ... }

    // catch-all — только для непредвиденных. НЕ глушит, не кидает 200.
    @ExceptionHandler(Throwable.class)
    ProblemDetail handleUnexpected(Throwable ex) { ... }
}
```

### b) Out-adapter — integration boundary

```java
@Component
@RequiredArgsConstructor
public class SberClientAdapter implements PaymentPort {

    private final SberApi sberApi;

    @Override
    @CircuitBreaker(name = "sber", fallbackMethod = "registerFallback")
    @Bulkhead(name = "sber")
    public RegisterResult register(RegisterCommand cmd) {
        try {
            var response = sberApi.register(toApiDto(cmd));
            return mapToDomain(response);
        } catch (HttpServerErrorException ex) {
            throw new SberRegisterException("Sber 5xx on register", ex);
        } catch (HttpClientErrorException.BadRequest ex) {
            // 4xx от внешней системы — это **не** retry. Mapping в domain-error.
            throw new InvalidPaymentRequestException(cmd.orderId(), ex.getResponseBodyAsString());
        }
    }

    private RegisterResult registerFallback(RegisterCommand cmd, CallNotPermittedException ex) {
        // CB открыт — кидаем port-specific exception. Edge решит как реагировать.
        throw new SberUnavailableException(cmd.orderId(), ex);
    }
}
```

### c) Резильянс-обёртки

`@CircuitBreaker(fallbackMethod = ...)`, `@Retry`, `@Bulkhead` — формальный catch. Внутри fallback-метода **не пишем** свой try-catch на тот же тип — иначе обёртка перестаёт работать (см. `R-RES-FB-X3`).

`R-ERR-WHERE-3` **В UseCase Handler / Domain Service / Aggregate — ноль try-catch**. Бизнес-валидации бросают `DomainException`, integration-вызовы бросают `IntegrationException`. Контроллер либо `@RestControllerAdvice` ловят на edge.

`R-ERR-WHERE-X1` ❌ **`try { ... } catch (Exception e) { log.error("Failed", e); }`** в любом handler/service. Глушит исключение, упаковывает stacktrace в строку, теряет тип, возвращает «успех» вызывающему. Главный антипаттерн силент-фейлов.

`R-ERR-WHERE-X2` ❌ **`catch (Exception e) { throw new RuntimeException(e); }`** — теряется тип, edge-handler видит generic Throwable, отдаёт 500 на всё подряд. Если действительно нужно обернуть — оборачивай в **типизированный** наследник (`R-ERR-HIER-1`).

`R-ERR-WHERE-X3` ❌ **`catch (Exception e) { return Optional.empty(); }`** или `return null` — то же что `WHERE-X1`, только без логирования. Скрывает проблему ещё глубже.

---

## 3. Mapping в ProblemDetails — `R-ERR-MAP-*`

Сшивка с `R-API-ERR-*` из `rest-api-style-guide.md`. Тут — какие именно поля заполняются для каждого типа.

`R-ERR-MAP-1` **`DomainException` → 409 (Conflict) или 422 (Unprocessable Entity)**. 409 для нарушения текущего состояния (нельзя отменить отгруженный заказ), 422 для нарушения бизнес-инвариантов (заказ <100₽). Поле `type` в ProblemDetail = URL на доменный код ошибки в каталоге `docs/spec/errors/`.

```java
@ExceptionHandler(InsufficientFundsException.class)
ProblemDetail handleInsufficientFunds(InsufficientFundsException ex) {
    var pd = ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY,
        "Operation cannot be completed due to insufficient funds");
    pd.setType(URI.create("https://api.example.com/errors/insufficient-funds"));
    pd.setProperty("customerId", ex.getCustomerId());
    pd.setProperty("requested", ex.getRequested());
    pd.setProperty("available", ex.getAvailable());
    pd.setProperty("traceId", MDC.get("traceId"));
    return pd;
}
```

`R-ERR-MAP-2` **`ValidationException` → 400 (Bad Request)**. `errors`-массив с per-field подробностями. Spring Jakarta Validation (`@Valid`) автоматом мапит в `MethodArgumentNotValidException` — обработать в `@RestControllerAdvice` отдельно, привести к нашей форме.

`R-ERR-MAP-3` **`IntegrationException` → 502 / 503 / 504**:
- 502 если внешка вернула 5xx с понятным телом — мы обработали, мост сломан.
- 503 если CB открыт (`R-RES-FB-*`) или `RejectedExecutionException` от bulkhead — сервис временно не может обслужить.
- 504 если timeout (наш или внешний).

В `detail` **не вкладываем сырое тело внешки** (может содержать PII / debugging info внешней системы) — общая фраза + `traceId` для cross-system корреляции.

`R-ERR-MAP-4` **`TechnicalException` → 500**. Минимум информации в response (просто «Internal Server Error» + traceId), всё остальное — в логи. По `AUTH-18` PII / стектрейсы не уходят в response.

`R-ERR-MAP-5` **Catch-all (`Throwable`) → 500**. Логируется с `ERROR`-уровнем + полный stacktrace + структурный контекст. Это сигнал бага: появилось исключение, которое не описано в иерархии. Создавать issue-trekker.

`R-ERR-MAP-X1` ❌ **HTTP 200 при ошибке** с `{"success": false, "error": "..."}` в body. SOAP-эпохи остались позади — REST использует HTTP-коды по назначению. Особенно опасно: client-side инструменты (Sentry, dashboards) считают всё, что не 4xx/5xx, успехом — мониторинг прозевает.

`R-ERR-MAP-X2` ❌ **stacktrace в `detail`-поле ProblemDetail**. Утечка информации (классы, версии, paths сервера). Только в логи.

`R-ERR-MAP-X3` ❌ **Сообщение исключения как `detail` без локализации/санитизации**. `"java.sql.SQLException: relation \"order_doc\" does not exist"` в response клиента — раскрытие схемы БД.

---

## 4. Логирование исключений — `R-ERR-LOG-*`

Сшивка с `R-OBS-LOG-*`/`R-OBS-MDC-*` из `observability-style-guide.md`.

`R-ERR-LOG-1` **`DomainException` логируется на `WARN`** в edge-handler-е. Это ожидаемая ошибка (бизнес-правило сработало), не баг сервиса. ERROR создаст false-positive алёрты.

`R-ERR-LOG-2` **`IntegrationException` логируется на `WARN`**, если CB ещё закрыт (одиночный fail в потоке). На `ERROR`, если CB открылся — это уже инцидент.

`R-ERR-LOG-3` **`TechnicalException` и catch-all (`Throwable`) — `ERROR`** + полный stacktrace + структурный контекст (request-id, customer-id, operation).

`R-ERR-LOG-4` **Логируем один раз — на edge-handler**. Не на каждом уровне call stack. Иначе одна ошибка превращается в 5 строк лога с разной полнотой контекста.

`R-ERR-LOG-X1` ❌ **`log.error("...", e); throw e;`** — двойное логирование. Логирует здесь, потом ещё раз на edge. Шум в логе. Либо логируй и обработай, либо проброс — выбирай.

`R-ERR-LOG-X2` ❌ **`log.error(e.getMessage())` без объекта `e`** — теряется stacktrace, остаётся только сообщение. Используй `log.error("Context: {}", contextValue, e)` (последний аргумент — объект исключения, без `{}`-плейсхолдера).

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Сшивка с `R-RES-RE-*` из `resilience-style-guide.md` и `AUTH-19` из `auth-patterns-style-guide.md`.

`R-ERR-RETRY-1` **По типу exception — однозначный ответ**:
- `DomainException` — **никогда не retry**. Бизнес-правило — детерминированно.
- `ValidationException` — **никогда не retry**. Те же данные → тот же fail.
- `IntegrationException` — **retry safe** при идемпотентности (`AUTH-19`). Если операция write без `Idempotency-Key` — retry запрещён (`R-RES-RE-X1`).
- `TechnicalException` — обычно retry (после latency).

`R-ERR-RETRY-2` **HTTP 4xx от внешней системы — НЕ retry**. Это означает «мы послали что-то некорректное», retry не поможет. Превращаем в port-specific exception (`InvalidPaymentRequestException`), edge отдаёт 422.

`R-ERR-RETRY-3` **HTTP 5xx и timeout — retry safe только при идемпотентности**. Без `Idempotency-Key` на write — `R-RES-RE-X1` нарушение, money-операция может списаться дважды.

`R-ERR-RETRY-X1` ❌ **`@Retry` на `@ExceptionHandler`-аннотированном методе** — не имеет смысла, edge-handler уже вне retry-цикла.

---

## 6. Result-types vs exceptions — `R-ERR-RESULT-*`

Альтернативный паттерн — `Result<T, E>` / sealed-interface вместо исключений. У нас он **разрешён точечно**, не как замена.

`R-ERR-RESULT-1` **Result допустим в чисто-функциональных модулях**, где исключение реально семантически часть результата (парсер: `ParseResult<Token, ParseError>`; calculation engine: `CalcResult<Money, CalcError>`). Эти модули редкие — обычно это «вычислительный стэйджик» внутри одного use case.

`R-ERR-RESULT-2` **В цепочке UseCase Handler → Domain → Adapter — исключения**, не Result. Иначе каждый метод обязан вернуть `Result<T, MyError>` и каждый caller — pattern-match-ить. Это разрушает читаемость и не приносит type-safety поверх того, что уже даёт типизированная иерархия исключений.

`R-ERR-RESULT-X1` ❌ **Глобальная замена исключений на Result** ради «type-safe error handling». В Java без полноценного pattern-matching это превращается в `result.isOk() ? result.value() : throw result.error()` — те же яйца, в профиль.

---

## 7. Observability — `R-ERR-OBS-*`

`R-ERR-OBS-1` **Метрика `app_errors_total{type=...,exception=...}`** (Counter). Tag `type` — `domain` / `validation` / `integration` / `technical` / `unexpected`. Tag `exception` — simple class name. Дашборд: количество per-type, аномалии.

`R-ERR-OBS-2` **Trace span на исключение помечается как `ERROR`** (OpenTelemetry SpanStatus.ERROR + recordException). Edge-handler делает это автоматически если span создан в `@RestController` через Spring Cloud Sleuth / OTel-instrumentation.

`R-ERR-OBS-3` **Алёрты — на необычные паттерны**, не на каждое исключение:
- Резкий рост `unexpected` (catch-all) → новый баг, разбираться.
- Рост `integration` → внешняя система деградирует.
- Рост `domain` для одного код ошибки → возможно бизнес-условие изменилось, не предупредили команду.
- `validation` обычно стабилен — резкий рост = клиент сломал контракт.

`R-ERR-OBS-X1` ❌ **Алёрт «Любое исключение в логах»**. Шум — `DomainException` нормально, частая. Алёртить только на `unexpected`/`technical`.

---

## 8. Что **не** покрывает этот гайд

- **REST-формат ошибок** (структура `ProblemDetail`, обязательные поля) — `rest-api-style-guide.md` (`R-API-ERR-*`).
- **Валидация инпута через `@Valid`** — `validation-style-guide.md` (`R-VLD-WHERE-*`).
- **Retry-policy конфигурация** (exponential backoff, max attempts) — `resilience-style-guide.md` (`R-RES-RE-*`).
- **PII в логах и detail** — `auth-patterns-style-guide.md` (`AUTH-18`) + `observability-style-guide.md` (`R-OBS-PII-*`).
- **Спецификация ошибок в спеке** (`docs/spec/errors/`) — `ucp-spec-design`.

---

## Чеклист подключения к новому сервису

- [ ] 4 базовых исключения определены в `core/`: `DomainException`, `ValidationException`, `IntegrationException`, `TechnicalException`
- [ ] Все — `RuntimeException`-наследники, не Checked
- [ ] Доменные исключения именуются по бизнес-смыслу, конструкторы фиксируют контекст
- [ ] Один `GlobalExceptionHandler` с `@RestControllerAdvice` + per-type `@ExceptionHandler`
- [ ] Catch-all (`Throwable`) → 500 + ERROR-лог + traceId в response
- [ ] Out-adapter ловит низкоуровневые exceptions, бросает port-specific
- [ ] Никаких try-catch в UseCase Handler / Domain Service / Aggregate
- [ ] DomainException → WARN, IntegrationException → WARN/ERROR (зависит от CB), TechnicalException/unexpected → ERROR
- [ ] Логирование один раз — на edge
- [ ] Метрика `app_errors_total{type=...,exception=...}` экспонирована
- [ ] Алёрт на `unexpected`-counter, не на все исключения
- [ ] Spec в `docs/spec/errors/` — каждое доменное исключение имеет карточку
