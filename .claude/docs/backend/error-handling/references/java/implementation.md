# Error Handling — реализация

Единая стратегия обработки ошибок для Java/Spring-сервисов по Use Case Pattern. Иерархия исключений, где throw / где catch, mapping в `ProblemDetails` (RFC 9457), retry/no-retry, наблюдаемость. Каждое правило имеет код `R-ERR-*` — скилл `ucp-error-handling-review` цитирует их в findings.

Гайд намеренно широкий — он сшивает то, что разбросано по другим гайдам: REST-формат ошибок (`R-API-ERR-*`), валидация (`R-VLD-*`), резилианс (`R-RES-*`), security-mapping (`auth-patterns/401-not-403`). Здесь — общая модель: какие типы исключений в коде, где их обрабатывают, как они становятся ответом наружу.

Базовый принцип (`error-handling/exceptions-are-part-of-contract`): **исключение — это часть контракта, не неожиданность**. Каждое исключение в публичной сигнатуре метода имеет тип, документированный смысл, и однозначный handler. Голый `catch (Exception e) { log.error(); return null; }` — главный антипаттерн всего гайда.

`error-handling/catch-in-three-places-only` **Только четыре места catch**:
1. **Edge** — `@RestControllerAdvice` для REST и для каждого протокольного входа, error-handler контейнера для Kafka, `try/catch` вокруг диспатча в `*Processing` планировщика. Превращает исключение в ответ, повтор или пропуск.
2. **Integration boundary** — out-adapter (interceptor клиента) ловит `HttpServerErrorException` / `SocketTimeoutException` / `IOException` / ошибку протокола и превращает их в семейство своей системы (`PartnerClientException` с видом отказа).
3. **Резильянс-обёртка** — `@CircuitBreaker(fallbackMethod = ...)` (`R-RES-CB-*`), retry — формальный catch, описанный конфигом, не try-catch в коде.
4. **Relay-цикл по единицам работы** — handler, который прогоняет пачку outbox-записей, ловит на **единице**, чтобы одна запись не валила остальные: логирует, оставляет запись в работе (re-claim после `reclaimAfter`) и идёт дальше. Перехват на всю пачку — нет.

Везде ещё в коде — **никаких try-catch**. Доменное исключение проходит насквозь до edge.

---

## 1. Семейства исключений — `R-ERR-HIER-*`

`error-handling/four-exception-kinds` **Два вида исключений, без общих корней.** Единица классификации — семейство, не категория:

| Вид | Форма | Где живёт | Пример |
|---|---|---|---|
| Доменное | `sealed abstract class <Aggregate>Exception extends RuntimeException` с вложенными `final`-вариантами | `core/exception/` | `HubConnectionException.NotFound`, `.InvalidStateTransition`, `.RolesRequired` |
| Интеграционное | семейство на внешнюю систему, вид отказа — внутри | `core/exception/` — порт и handler видят только его | `PartnerClientException` с `Group { CLIENT, SERVER, HUB }` |

Валидация входа — не класс, а граница: `MethodArgumentNotValidException` от контракта → 400. Техническое и непредвиденное — не класс, а catch-all `Throwable` на границе → 500. Общий корень над семействами (`DomainException`, `IntegrationException`, `TechnicalException`) не заводится: код ответа и допустимость повтора зависят от варианта семейства и вида отказа, а не от категории, а безликий корень приглашает бросать его напрямую. В эталоне — 22 доменных семейства и семейство `PartnerException`, общих корней нет.

Все исключения — `RuntimeException`-наследники. Checked-exceptions не используются — они засоряют сигнатуры или оборачиваются с потерей типа.

`error-handling/domain-exception-named-by-meaning` **Семейство — на агрегат, вариант — по смыслу отказа:**

```java
@Getter
public sealed abstract class HubConnectionException extends RuntimeException {

    private static final String NOT_FOUND_MSG = "HubConnection not found: %s";
    private static final String INVALID_STATE_MSG = "Cannot %s HubConnection in status %s";

    private final Object[] args;

    private HubConnectionException(String message, Object... args) {
        super(message);
        this.args = args;
    }

    public static final class NotFound extends HubConnectionException {
        public NotFound(UUID hubConnectionId) {
            super(String.format(NOT_FOUND_MSG, hubConnectionId), hubConnectionId);
        }
    }

    public static final class InvalidStateTransition extends HubConnectionException {
        public InvalidStateTransition(String action, RegistrationStatus status) {
            super(String.format(INVALID_STATE_MSG, action, status), action, status);
        }
    }
}
```

Имя варианта отвечает на «что нарушено» (`NotFound`, `DuplicateClient`, `PullModuleNotExposed`), имя семейства — «чьё правило». `sealed abstract` даёт границе исчерпывающий `switch` без `default`: забытый вариант — ошибка компиляции. `abstract` обязателен — иначе компилятор считает возможным экземпляр самого семейства и требует для него ветку. Конструктор семейства приватный — наружу только варианты, «голый» `HubConnectionException` бросить нельзя.

`error-handling/exception-carries-context` **Контекст — в конструкторе и в `args`.** Техническое сообщение собирается из констант семейства для журнала; те же значения лежат в `Object[] args` и подставляются в сообщение для клиента на границе (§3). Не `new NotFound()`, а `new NotFound(hubConnectionId)`.

`error-handling/integration-exception-names-system` **Семейство — на внешнюю систему, вид отказа — внутри:**

```java
@Getter
public final class PartnerClientException extends PartnerException {

    public enum Group {
        CLIENT, SERVER, HUB;

        public static Group of(Integer statusCode) {
            if (statusCode == null) {
                return HUB;
            }
            return switch (statusCode / 1000) {
                case 2 -> CLIENT;
                case 3 -> SERVER;
                default -> HUB;
            };
        }
    }

    private final Group group;
    private final Integer httpStatus;
    private final Integer statusCode;
}
```

Вид отказа решает и код ответа (§3), и повтор (§5): серверный отказ и таймаут повторяемы при идемпотентности, клиентский — никогда. Бросает семейство interceptor клиента в out-adapter (`PartnerApiErrorInterceptor`: HTTP 4xx/5xx, таймаут и IO → синтетические коды, партнёрского протокола `statusCode != 1000`); handler'ы и порты знают только семейство. Имя — по системе: `PartnerClientException`, `CsmsClientException`, `SberClientException`.

`error-handling/no-bare-base-exceptions` ❌ **`throw new RuntimeException("Что-то сломалось")`** в коде. Тип теряется, edge отдаёт 500 на всё подряд. Бросается вариант семейства.

`error-handling/no-bare-base-exceptions` **`IllegalStateException` / `IllegalArgumentException` — только в недостижимых ветках**: `default ->` в исчерпывающем `switch` по enum, нереализованная стратегия в реестре стратегий. Это ошибка программиста — её ловит тест, а не клиент. Бизнес-правило и нарушение инварианта агрегата — вариант доменного семейства (`RolesRequired`, `InvalidStateTransition`), не `IllegalStateException`.

**Каталог сообщений — вариант, не норма.** Когда ответы читают люди на своём языке: `ErrorMessageKeys` (`@UtilityClass` с ключами вида `hub-connection.not-found`) в `core/exception`, `messages.properties` / `messages_ru.properties` в ресурсах core, `MessageSource` на границе подставляет `args` семейства в текст; `ErrorMessageKeysCatalogParityTest` держит паритет ключей и записей. Без каталога сообщение клиенту — техническое, из конструктора.

---

## 2. Где throw, где catch — `R-ERR-WHERE-*`

`error-handling/throw-where-detected` **Throw — везде где нужно**. Агрегат и handler бросают вариант доменного семейства, interceptor клиента в out-adapter — семейство своей системы, контракт на границе — ошибку валидации. Не накручиваем `Optional<Result, Error>` или sealed-interface-Result везде только ради избежания исключений (`error-handling/result-type-is-local-choice`).

`error-handling/catch-in-three-places-only` **Catch только в трёх местах** (см. `error-handling/catch-in-three-places-only`):

### a) `@RestControllerAdvice` — граница входа, по одному на входной адаптер

Advice — на протокол, не на сервис: у REST и у протокольного входа разные конверты ошибок. `@RestControllerAdvice(basePackages = "…adapter.in.restapi")` отдаёт ProblemDetails, `@RestControllerAdvice(basePackages = "…adapter.in.partnerapi")` — конверт партнёрского протокола со `statusCode` и HTTP 200; контроллер с особым контрактом (команд партнёрского протокола CPO) получает свой `@RestControllerAdvice(assignableTypes = …)`. Внутри каждого — `@ExceptionHandler` на семейство с исчерпывающим `switch` (§3) и catch-all `Throwable` → 500. Один `GlobalExceptionHandler` на всё — только у сервиса с единственным протоколом.

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
            throw new SberClientException(SberClientException.Kind.SERVER, "register", ex);
        } catch (HttpClientErrorException.BadRequest ex) {
            // 4xx от внешней системы — это **не** retry: вид отказа CLIENT, edge отдаст код контракта, не 502.
            throw new SberClientException(SberClientException.Kind.CLIENT, "register", ex);
        }
    }

    private RegisterResult registerFallback(RegisterCommand cmd, CallNotPermittedException ex) {
        // CB открыт — тот же вид семейства, отказ доступности. Edge отдаст 503.
        throw new SberClientException(SberClientException.Kind.UNAVAILABLE, "register", ex);
    }
}
```

### c) Резильянс-обёртки

`@CircuitBreaker(fallbackMethod = ...)`, `@Retry`, `@Bulkhead` — формальный catch. Внутри fallback-метода **не пишем** свой try-catch на тот же тип — иначе обёртка перестаёт работать (см. `resilience/fallback-does-not-fake-success`).

`error-handling/catch-in-three-places-only` **В UseCase Handler / Domain Service / Aggregate — ноль try-catch** (исключение — relay-цикл на единицу работы, п. 4). Бизнес-валидации бросают вариант доменного семейства, integration-вызовы — семейство системы. Ловит граница.

`error-handling/catch-does-not-swallow` ❌ **`try { ... } catch (Exception e) { log.error("Failed", e); }`** в любом handler/service. Глушит исключение, упаковывает stacktrace в строку, теряет тип, возвращает «успех» вызывающему. Главный антипаттерн силент-фейлов.

`error-handling/catch-does-not-swallow` ❌ **`catch (Exception e) { throw new RuntimeException(e); }`** — теряется тип, edge-handler видит generic Throwable, отдаёт 500 на всё подряд. Если действительно нужно обернуть — оборачивай в вариант своего семейства (`error-handling/four-exception-kinds`).

`error-handling/catch-does-not-swallow` ❌ **`catch (Exception e) { return Optional.empty(); }`** или `return null` — то же что `WHERE-X1`, только без логирования. Скрывает проблему ещё глубже.

---

## 3. Отображение в ответ — `R-ERR-MAP-*`

Сшивка с `R-API-ERR-*`: форма ответа — схема `ProblemDetails` и enum `ErrorCode` **из OpenAPI-контракта** (`rest-api/error-codes-enumerated`), сгенерированные вместе с интерфейсами контроллеров. Spring'овый `ProblemDetail` и `type`-URL на каталог в документации не используются: каталог кодов и есть контракт.

`error-handling/domain-and-validation-mapping` **Семейство → исчерпывающий `switch` → статус, код контракта, ключ сообщения:**

```java
@ExceptionHandler(HubConnectionException.class)
public ResponseEntity<ProblemDetailResponse> handleHubConnection(HubConnectionException exception) {
    HttpStatus status = switch (exception) {
        case HubConnectionException.NotFound _, HubConnectionException.ClientNotFound _ -> HttpStatus.NOT_FOUND;
        case HubConnectionException.RolesRequired _, HubConnectionException.ClientsRequireHubRole _ -> HttpStatus.BAD_REQUEST;
        case HubConnectionException.InvalidStateTransition _ -> HttpStatus.CONFLICT;
    };
    ErrorCode code = switch (exception) {
        case HubConnectionException.NotFound _, HubConnectionException.ClientNotFound _ -> ErrorCode.RESOURCE_NOT_FOUND;
        case HubConnectionException.RolesRequired _ -> ErrorCode.ROLES_REQUIRED;
        case HubConnectionException.ClientsRequireHubRole _ -> ErrorCode.CLIENTS_REQUIRE_HUB_ROLE;
        case HubConnectionException.InvalidStateTransition _ -> ErrorCode.INVALID_STATE_TRANSITION;
    };
    String messageKey = switch (exception) {
        case HubConnectionException.NotFound _ -> ErrorMessageKeys.HUB_CONNECTION_NOT_FOUND;
        case HubConnectionException.ClientNotFound _ -> ErrorMessageKeys.HUB_CONNECTION_CLIENT_NOT_FOUND;
        case HubConnectionException.RolesRequired _ -> ErrorMessageKeys.HUB_CONNECTION_ROLES_REQUIRED;
        case HubConnectionException.ClientsRequireHubRole _ -> ErrorMessageKeys.HUB_CONNECTION_CLIENTS_REQUIRE_HUB_ROLE;
        case HubConnectionException.InvalidStateTransition _ -> ErrorMessageKeys.HUB_CONNECTION_INVALID_STATE_TRANSITION;
    };
    return problemDetail(status, code, messageKey, exception.getArgs());
}
```

Правило статусов: «не найдено» → 404; нарушено правило входа (обязательная роль, недопустимый тип) → 400; нарушено правило состояния → 409, инвариант → 422. Ветки `default` нет: семейство `sealed abstract`, и компилятор требует ветку на каждый вариант — новый вариант без кода ответа не собирается (`java-style/exhaustive-switch-on-sealed`). Код по умолчанию превратил бы забытый вариант в молчаливый 409.

`error-handling/domain-and-validation-mapping` **Валидация контракта → 400** с перечнем по полям: `MethodArgumentNotValidException` обрабатывается в том же advice (наследование от `ResponseEntityExceptionHandler`) и приводится к той же `ProblemDetailResponse` с `ErrorCode.VALIDATION_FAILED` и массивом `ValidationError`.

`error-handling/integration-and-technical-mapping` **Интеграционное семейство → по виду отказа**: клиентский (партнёр отверг наш запрос) → 409/422 с кодом контракта, не 502 — повтор не поможет; серверный → 502; разрыв цепи или отказ bulkhead → 503; таймаут → 504. Протокольный вход отвечает своим конвертом — для партнёрского протокола это `statusCode` 2xxx/3xxx при HTTP 200. В `detail` **не вкладываем сырое тело внешки** (PII, устройство чужой системы) — общая фраза + `traceId`.

`error-handling/integration-and-technical-mapping` **Catch-all (`Throwable`) → 500.** Минимум в ответе («Internal Server Error» + `traceId`), всё остальное — в журнал уровнем ERROR с полным stacktrace. Это сигнал: появилось исключение вне семейств — заводить вариант или чинить баг.

**`traceId` в ответе — через `ErrorTraceId`**: сначала `Tracer.currentSpan()`, затем `MDC`, затем сгенерированный — ответ несёт идентификатор и там, где трассировка выключена.

`error-handling/no-success-code-for-failure` ❌ **HTTP 200 при ошибке** с `{"success": false, "error": "..."}` в body. SOAP-эпохи остались позади — REST использует HTTP-коды по назначению. Особенно опасно: client-side инструменты (Sentry, dashboards) считают всё, что не 4xx/5xx, успехом — мониторинг прозевает.

`error-handling/integration-and-technical-mapping` ❌ **stacktrace в `detail`-поле ProblemDetail**. Утечка информации (классы, версии, paths сервера). Только в логи.

`error-handling/integration-and-technical-mapping` ❌ **Сообщение исключения как `detail` без локализации/санитизации**. `"java.sql.SQLException: relation \"order_doc\" does not exist"` в response клиента — раскрытие схемы БД.

---

## 4. Логирование исключений — `R-ERR-LOG-*`

Сшивка с `R-OBS-LOG-*`/`R-OBS-MDC-*` из `backend/observability/references/java/implementation.md`.

`error-handling/log-level-matches-kind` **Доменное семейство логируется на `WARN`** в edge-handler-е. Это ожидаемая ошибка (бизнес-правило сработало), не баг сервиса. ERROR создаст false-positive алёрты.

`error-handling/log-level-matches-kind` **Интеграционное семейство — `WARN`** при клиентском или единичном серверном отказе. `ERROR`, если CB открылся — это уже инцидент.

`error-handling/log-level-matches-kind` **Catch-all (`Throwable`) — `ERROR`** + полный stacktrace + структурный контекст (request-id, customer-id, operation).

`error-handling/log-once-with-exception` **Логируем один раз — на edge-handler**. Не на каждом уровне call stack. Иначе одна ошибка превращается в 5 строк лога с разной полнотой контекста.

`error-handling/log-once-with-exception` ❌ **`log.error("...", e); throw e;`** — двойное логирование. Логирует здесь, потом ещё раз на edge. Шум в логе. Либо логируй и обработай, либо проброс — выбирай.

`error-handling/log-once-with-exception` ❌ **`log.error(e.getMessage())` без объекта `e`** — теряется stacktrace, остаётся только сообщение. Используй `log.error("Context: {}", contextValue, e)` (последний аргумент — объект исключения, без `{}`-плейсхолдера).

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Сшивка с `R-RES-RE-*` из `backend/resilience/references/java/implementation.md` и `auth-patterns/money-commands-need-idempotency-key` из `backend/auth-patterns/references/java/implementation.md`.

`error-handling/retry-semantics-by-kind` **По виду отказа — однозначный ответ**:
- Вариант доменного семейства — **никогда не retry**. Бизнес-правило детерминированно.
- Ошибка валидации контракта — **никогда не retry**. Те же данные → тот же fail.
- Интеграционное семейство, вид **CLIENT** — **никогда**: партнёр отверг наш запрос, повтор пошлёт то же.
- Интеграционное семейство, вид **SERVER / TIMEOUT / UNAVAILABLE** — retry safe только при идемпотентности (`auth-patterns/money-commands-need-idempotency-key`). Write без `Idempotency-Key` — retry запрещён (`resilience/retry-only-when-safe`).
- Непредвиденное (catch-all) — не повторять автоматически: сначала понять, что это.

`error-handling/retry-semantics-by-kind` **HTTP 4xx от внешней системы — НЕ retry**. Это означает «мы послали что-то некорректное», retry не поможет. Это вид отказа CLIENT семейства системы; edge отдаёт код контракта (409/422), не 502.

`error-handling/retry-semantics-by-kind` **HTTP 5xx и timeout — retry safe только при идемпотентности**. Без `Idempotency-Key` на write — `resilience/retry-only-when-safe` нарушение, money-операция может списаться дважды.

`error-handling/no-retry-at-edge` ❌ **`@Retry` на `@ExceptionHandler`-аннотированном методе** — не имеет смысла, edge-handler уже вне retry-цикла.

---

## 6. Result-types vs exceptions — `R-ERR-RESULT-*`

Альтернативный паттерн — `Result<T, E>` / sealed-interface вместо исключений. У нас он **разрешён точечно**, не как замена.

`error-handling/result-type-is-local-choice` **Result допустим в чисто-функциональных модулях**, где исключение реально семантически часть результата (парсер: `ParseResult<Token, ParseError>`; calculation engine: `CalcResult<Money, CalcError>`). Эти модули редкие — обычно это «вычислительный стэйджик» внутри одного use case.

`error-handling/result-type-is-local-choice` **В цепочке UseCase Handler → Domain → Adapter — исключения**, не Result. Иначе каждый метод обязан вернуть `Result<T, MyError>` и каждый caller — pattern-match-ить. Это разрушает читаемость и не приносит type-safety поверх того, что уже даёт типизированная иерархия исключений.

`error-handling/result-type-is-local-choice` ❌ **Глобальная замена исключений на Result** ради «type-safe error handling». В Java без полноценного pattern-matching это превращается в `result.isOk() ? result.value() : throw result.error()` — те же яйца, в профиль.

---

## 7. Observability — `R-ERR-OBS-*`

`error-handling/errors-counted-by-kind` **Метрика `app_errors_total{type=...,exception=...}`** (Counter). Tag `type` — `domain` / `validation` / `integration` / `unexpected`. Tag `exception` — семейство и вариант (`HubConnectionException.NotFound`, `PartnerClientException.SERVER`). Дашборд: количество per-type, аномалии.

`error-handling/trace-span-marked-error` **Trace span на исключение помечается как `ERROR`** (OpenTelemetry SpanStatus.ERROR + recordException). Edge-handler делает это автоматически если span создан в `@RestController` через Spring Cloud Sleuth / OTel-instrumentation.

`error-handling/alert-on-patterns-not-exceptions` **Алёрты — на необычные паттерны**, не на каждое исключение:
- Резкий рост `unexpected` (catch-all) → новый баг, разбираться.
- Рост `integration` → внешняя система деградирует.
- Рост `domain` для одного код ошибки → возможно бизнес-условие изменилось, не предупредили команду.
- `validation` обычно стабилен — резкий рост = клиент сломал контракт.

`error-handling/alert-on-patterns-not-exceptions` ❌ **Алёрт «Любое исключение в логах»**. Шум — доменные отказы нормальны и часты. Алёртить только на `unexpected` и на открытие CB у интеграций.

---

## 8. Что **не** покрывает этот гайд

- **REST-формат ошибок** (структура `ProblemDetail`, обязательные поля) — `backend/rest-api/references/java/implementation.md` (`R-API-ERR-*`).
- **Валидация инпута через `@Valid`** — `backend/validation/references/java/implementation.md` (`R-VLD-WHERE-*`).
- **Retry-policy конфигурация** (exponential backoff, max attempts) — `backend/resilience/references/java/implementation.md` (`R-RES-RE-*`).
- **PII в логах и detail** — `backend/auth-patterns/references/java/implementation.md` (`auth-patterns/error-response-hides-cause`) + `backend/observability/references/java/implementation.md` (`R-OBS-PII-*`).
- **Каталог кодов ошибок** — enum `ErrorCode` и схема `ProblemDetails` в OpenAPI-контракте (`rest-api/error-codes-enumerated`), `ucp-api-design`.

---

## Чеклист подключения к новому сервису

- [ ] Доменные исключения — `sealed abstract` семейство на агрегат в `core/exception/` с вложенными `final`-вариантами и `Object[] args`; общих корней нет
- [ ] Интеграционные — семейство на внешнюю систему с видом отказа внутри; бросает interceptor клиента в out-adapter
- [ ] Все — `RuntimeException`-наследники, не Checked; `IllegalStateException` — только недостижимые ветки
- [ ] Варианты именуются по смыслу отказа, конструкторы фиксируют контекст
- [ ] По одному `@RestControllerAdvice` на входной адаптер; маппинг — исчерпывающий `switch` → статус + `ErrorCode` контракта, без `default`: новый вариант не собирается, пока не получит ветку
- [ ] Catch-all (`Throwable`) → 500 + ERROR-лог + `traceId` через `ErrorTraceId`
- [ ] `MethodArgumentNotValidException` → 400 с `ValidationError[]` в той же форме
- [ ] Никаких try-catch в UseCase Handler / Domain Service / Aggregate; в relay-цикле — на единицу работы
- [ ] Доменное → WARN, интеграционное → WARN / ERROR при открытом CB, catch-all → ERROR; логирование один раз — на edge
- [ ] Retry — по виду отказа: CLIENT никогда, SERVER/TIMEOUT при идемпотентности
- [ ] Метрика `app_errors_total{type=...,exception=...}` экспонирована; алёрт на `unexpected` и открытие CB
- [ ] Каталог сообщений (`ErrorMessageKeys` + `messages_*.properties` + parity-тест) — если ответы читают люди
