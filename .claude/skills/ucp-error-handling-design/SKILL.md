---
name: ucp-error-handling-design
description: Спроектировать обработку ошибок в Spring Boot-сервисе по UCP (коды R-ERR-*) — иерархия Domain/Validation/Integration/Technical, GlobalExceptionHandler с ProblemDetails (RFC 9457), port-исключения в out-adapter, retry-семантика, наблюдаемость.
when_to_use: Триггеры — «настрой обработку ошибок», «добавь GlobalExceptionHandler». При старте сервиса или миграции catch-log-return-null кода.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Проектирование обработки ошибок

Ты создаёшь / расширяешь обработку ошибок в Spring Boot-сервисе согласно `backend/error-handling/java/error-handling-style-guide.md` (правила `R-ERR-*`). Цель — единая стратегия: типизированная иерархия, ровно три места catch (edge / out-adapter / резильянс-обёртка), консистентный ProblemDetails-mapping, наблюдаемость.

Не делает: настройку валидации (`ucp-validation-design`), резилианс-обвязку (`ucp-resilience-design`), security-mapping для 401/403 (`ucp-auth-design`), маскирование PII в логах (`ucp-observability-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — главный документ, правила `R-ERR-*` (полный текст с примерами — `backend/error-handling/java/error-handling-style-guide.md`, открывай точечно по разделу).
   - `.claude/docs/backend/rest-api/rest-api-rules.md` — для REST mapping (`R-API-ERR-*`).
   - `.claude/docs/backend/resilience/resilience-rules.md` — `R-RES-RE-*`/`R-RES-FB-*` для retry-семантики.
   - `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` — `AUTH-19` для idempotency, `AUTH-18` для PII в response.
   - `.claude/docs/backend/observability/observability-rules.md` — `R-OBS-LOG-*`/`R-OBS-MDC-*` для logging.

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP:
   - `core/` — здесь будут базовые exception-классы + доменные наследники.
   - `bootstrap/` — здесь GlobalExceptionHandler.
   - `adapter-out-*` — здесь port-specific exception + ловля низкоуровневых.
   - `adapter-in-rest/` — controllers, аннотации `@Valid`.

3. **Аудит текущего состояния.** Заполни таблицу — что есть, что предстоит:

   | Компонент | Код правила | Текущее состояние | План |
   |---|---|---|---|
   | Базовые exceptions (`DomainException`, etc.) | `R-ERR-HIER-1/2` | нет / частично / есть | создать / усилить |
   | Доменные наследники с контекстом | `R-ERR-HIER-3/5` | inline `RuntimeException` / типизированы | мигрировать |
   | `GlobalExceptionHandler` | `R-ERR-WHERE-2a` | нет / есть | создать / расширить |
   | Per-type `@ExceptionHandler` | `R-ERR-MAP-1..5` | catch-all only / per-type | разнести |
   | Out-adapter ловят low-level → port-specific | `R-ERR-WHERE-2b` | пробрасывают raw / типизировано | обернуть |
   | try-catch в Domain/Handler | `R-ERR-WHERE-X1` | есть / нет | удалить |
   | Метрика `app_errors_total` | `R-ERR-OBS-1` | нет / есть | добавить |

4. **Внеси изменения.** Lombok-defaults обязательны (`JS-6.1`–`JS-6.7`). Не цитируй коды правил в комментариях кода (`JS-7.3`).

   ### 4.1 Базовые exception-классы в `core/exception/`

   ```java
   public abstract class DomainException extends RuntimeException {
       protected DomainException(String message) { super(message); }
       protected DomainException(String message, Throwable cause) { super(message, cause); }
   }

   public class ValidationException extends RuntimeException { ... }
   public abstract class IntegrationException extends RuntimeException { ... }
   public class TechnicalException extends RuntimeException { ... }
   ```

   ### 4.2 Доменные наследники с типизированным контекстом

   Для каждого нарушения бизнес-правила — отдельный класс. Имя по бизнес-смыслу (`R-ERR-HIER-3`), конструктор фиксирует контекст (`R-ERR-HIER-5`):

   ```java
   @Getter
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
   }
   ```

   ### 4.3 `GlobalExceptionHandler` в `bootstrap/`

   Один класс с `@RestControllerAdvice`, отдельный `@ExceptionHandler`-метод на каждый базовый тип:

   ```java
   @RestControllerAdvice
   @Slf4j
   class GlobalExceptionHandler {

       @ExceptionHandler(DomainException.class)
       ProblemDetail handleDomain(DomainException ex, HttpServletRequest req) {
           log.warn("Domain rule violated: {}", ex.getMessage());     // R-ERR-LOG-1
           var pd = ProblemDetail.forStatusAndDetail(HttpStatus.UNPROCESSABLE_ENTITY,
               sanitize(ex.getMessage()));
           pd.setType(URI.create("https://api.example.com/errors/" + slugify(ex.getClass().getSimpleName())));
           pd.setProperty("traceId", MDC.get("traceId"));
           Metrics.counter("app_errors_total", "type", "domain", "exception", ex.getClass().getSimpleName()).increment();
           return pd;
       }

       @ExceptionHandler(ValidationException.class)
       ProblemDetail handleValidation(ValidationException ex) { ... }   // R-ERR-MAP-2

       @ExceptionHandler(IntegrationException.class)
       ProblemDetail handleIntegration(IntegrationException ex) { ... } // R-ERR-MAP-3

       @ExceptionHandler(MethodArgumentNotValidException.class)         // от @Valid
       ProblemDetail handleBeanValidation(MethodArgumentNotValidException ex) { ... }

       @ExceptionHandler(Throwable.class)                                // catch-all R-ERR-MAP-5
       ProblemDetail handleUnexpected(Throwable ex) {
           log.error("Unexpected error", ex);
           Metrics.counter("app_errors_total", "type", "unexpected", "exception", ex.getClass().getSimpleName()).increment();
           var pd = ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Internal Server Error");
           pd.setProperty("traceId", MDC.get("traceId"));
           return pd;
       }
   }
   ```

   ### 4.4 Port-specific exceptions для каждого `adapter-out-*`

   Для каждого внешнего адаптера — свой пакет exception с базовым `<X>IntegrationException extends IntegrationException`. Ловля низкоуровневых HTTP/SQL/Kafka exceptions внутри adapter-метода, проброс типизированного:

   ```java
   public abstract class SberIntegrationException extends IntegrationException { ... }
   public class SberRegisterException extends SberIntegrationException { ... }
   public class SberUnavailableException extends SberIntegrationException { ... }   // CB открыт
   public class InvalidPaymentRequestException extends DomainException { ... }      // 4xx → domain-уровень
   ```

   В adapter:
   ```java
   try {
       var resp = sberApi.register(toApiDto(cmd));
       return mapToDomain(resp);
   } catch (HttpServerErrorException ex) {
       throw new SberRegisterException("Sber 5xx on register", ex);
   } catch (HttpClientErrorException.BadRequest ex) {
       throw new InvalidPaymentRequestException(cmd.orderId(), ex.getResponseBodyAsString());
   }
   ```

   ### 4.5 Удалить try-catch из Handler/Service/Aggregate

   Любой `try { ... } catch (Exception e) { log.error(...); return ...; }` или `catch (Exception e) { throw new RuntimeException(e); }` в `core/` — удалить. Доменное исключение должно проходить насквозь.

   ### 4.6 `application.yml` / `build.gradle`

   - Никаких изменений в `application.yml` для error-handling — Spring сам подхватывает `@RestControllerAdvice`.
   - В `build.gradle` — никаких новых зависимостей (Spring Boot 3 уже включает Jakarta Validation + ProblemDetails).
   - Если ещё не подключён `micrometer-core` для метрики `app_errors_total` — добавить (обычно уже есть через actuator).

   ### 4.7 Spec — `docs/spec/errors/`

   На каждый домений exception — карточка в `docs/spec/errors/<slug>.md` с frontmatter:
   ```yaml
   ---
   code: insufficient-funds
   http_status: 422
   domain: payment
   thrown_by: PayCommand handler
   ---
   ```

5. **Самопроверка перед выдачей** — пройдись по чеклисту из `backend/error-handling/java/error-handling-style-guide.md` §«Чеклист подключения к новому сервису».

6. **Структура вывода:**
   1. **Audit таблица** (из шага 3).
   2. **План изменений** — какие классы создаются/правятся, в каком порядке.
   3. **Изменения по файлам** — каждый отдельным code-block с пометкой «add» / «replace».
   4. **Команды проверки локально:**
      - `./gradlew compileJava test --tests *GlobalExceptionHandlerTest`
      - integration-test: послать невалидный input → проверить 400 с ProblemDetails-телом.
   5. **Что **не** покрывается** (с пояснением, какой скилл это делает).
   6. **Финальный шаг:** «запусти `ucp-error-handling-review` для верификации».

## Что НЕ делает

- Не настраивает Jakarta Validation (`ucp-validation-design`).
- Не настраивает резильянс / CircuitBreaker (`ucp-resilience-design`).
- Не пишет тесты — `ucp-test-design`.
- Не настраивает аутентификацию / 401/403 mapping (`ucp-auth-design`).
- Не масштабирует существующие domain-exceptions (это работа `ucp-pattern-design` при добавлении нового UseCase).

После работы скилла — обязательно `ucp-error-handling-review` для верификации.

$ARGUMENTS
