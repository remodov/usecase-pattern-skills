---
name: ucp-error-handling-design
description: Спроектировать обработку ошибок в Spring Boot-сервисе по UCP — sealed-семейства исключений на агрегат и на внешнюю систему, @RestControllerAdvice на входной адаптер со switch → ErrorCode контракта, четыре места catch, retry по виду отказа.
when_to_use: Триггеры — «настрой обработку ошибок», «добавь ExceptionHandler / advice», новое семейство исключений. При старте сервиса или миграции catch-log-return-null кода.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Проектирование обработки ошибок

Ты создаёшь / расширяешь обработку ошибок в Spring Boot-сервисе согласно `backend/error-handling/references/java/implementation.md` (правила `R-ERR-*`). Цель — единая стратегия: семейства исключений вместо общего корня, четыре места catch (граница входа / out-adapter / резильянс-обёртка / единица работы в relay-цикле), исчерпывающий `switch` в код контракта, наблюдаемость.

Не делает: настройку валидации (`ucp-validation-design`), резилианс-обвязку (`ucp-resilience-design`), security-mapping для 401/403 (`ucp-auth-design`), маскирование PII в логах (`ucp-observability-design`), каталог `ErrorCode` в OpenAPI (`ucp-api-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/spec.md` — главный документ, правила `R-ERR-*` (полный текст с примерами — `backend/error-handling/references/java/implementation.md`, открывай точечно по разделу).
   - `.claude/docs/backend/rest-api/spec.md` — для REST mapping (`R-API-ERR-*`, `rest-api/error-codes-enumerated`).
   - `.claude/docs/backend/resilience/spec.md` — `R-RES-RE-*`/`R-RES-FB-*` для retry-семантики.
   - `.claude/docs/backend/auth-patterns/spec.md` — `auth-patterns/money-commands-need-idempotency-key` для idempotency, `auth-patterns/error-response-hides-cause` для PII в response.
   - `.claude/docs/backend/observability/spec.md` — `R-OBS-LOG-*`/`R-OBS-MDC-*` для logging.

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP:
   - `core/exception/` — `sealed`-семейство на агрегат с вложенными `final`-вариантами; общих корней (`DomainException`, `IntegrationException`, …) нет.
   - `adapter-out-<system>/.../exception/` — семейство внешней системы с видом отказа внутри (`Kind`/`Group`: `CLIENT`, `SERVER`, `UNAVAILABLE`, `TIMEOUT`); interceptor клиента переводит низкоуровневые исключения в него.
   - `adapter-in-rest/` — `RestApiExceptionHandler` (`@RestControllerAdvice`) + `ErrorTraceId`; у каждого входного адаптера свой advice со своим конвертом.
   - `bootstrap/` — для ошибок ничего, кроме ArchUnit `NoTryCatchInHandlersTest`.
   - OpenAPI-контракт — enum `ErrorCode` и схема `ProblemDetails` (`ucp-api-design`).

3. **Аудит текущего состояния.** Заполни таблицу — что есть, что предстоит:

   | Компонент | Код правила | Текущее состояние | План |
   |---|---|---|---|
   | `sealed`-семейство на агрегат в `core/exception/` | `error-handling/four-exception-kinds` | нет / один тип с текстом / есть | создать / разнести на варианты |
   | Варианты по смыслу отказа, с `args` | `error-handling/domain-exception-named-by-meaning`, `error-handling/exception-carries-context` | inline `RuntimeException` / типизированы | мигрировать |
   | Семейство на внешнюю систему с видом отказа | `error-handling/integration-exception-names-system` | raw `HttpClientErrorException` / есть | обернуть в interceptor'е |
   | Advice на входной адаптер | `R-ERR-WHERE-2a` | нет / один общий в bootstrap / есть | создать / перенести |
   | исчерпывающий `switch` → статус + `ErrorCode` контракта, без `default` | `R-ERR-MAP-1..5` | catch-all only / по типам | разнести |
   | try-catch в Handler/Service/Aggregate | `error-handling/catch-in-three-places-only` | есть / нет | удалить (кроме relay на единицу работы) |
   | Метрика `app_errors_total` | `error-handling/errors-counted-by-kind` | нет / есть | добавить |

4. **Внеси изменения.** Lombok-defaults обязательны (`java-style/boilerplate-is-generated`–`java-style/builder-used-sparingly`). Не цитируй коды правил в комментариях кода (`java-style/no-rule-codes-or-history-in-code`).

   ### 4.1 Доменное семейство в `core/exception/`

   Одно `sealed`-семейство на агрегат, вариант — на каждый смысл отказа. Конструктор варианта фиксирует контекст, `args` уходят в сообщение и каталог:

   ```java
   @Getter
   public sealed abstract class HubConnectionException extends RuntimeException {
       private final Object[] args;

       private HubConnectionException(String message, Object... args) {
           super(message);
           this.args = args;
       }

       public static final class NotFound extends HubConnectionException {
           public NotFound(HubConnectionId id) {
               super("Hub connection %s not found".formatted(id), id);
           }
       }

       public static final class InvalidStateTransition extends HubConnectionException {
           public InvalidStateTransition(HubConnectionStatus from, String action) {
               super("Cannot %s hub connection in status %s".formatted(action, from), from, action);
           }
       }
   }
   ```

   `abstract` обязателен: иначе компилятор считает возможным экземпляр самого семейства и исчерпывающий `switch` без `default` не соберётся. Не заводи `DomainException`/`TechnicalException`: валидация входа — `MethodArgumentNotValidException` от контракта, непредвиденное — catch-all `Throwable`. `IllegalStateException` — только в недостижимой ветке исчерпывающего `switch`.

   ### 4.2 Семейство внешней системы в `adapter-out-<system>/`

   Одно семейство на систему, вид отказа — внутри; специфика системы (коды протокола, группы) живёт здесь же. Interceptor клиента переводит низкоуровневые исключения — единственный catch в адаптере:

   ```java
   @Getter
   public final class SberClientException extends RuntimeException {
       public enum Kind { CLIENT, SERVER, UNAVAILABLE, TIMEOUT }

       private final Kind kind;
       private final String operation;

       public SberClientException(Kind kind, String operation, Throwable cause) {
           super("Sber %s failed: %s".formatted(operation, kind), cause);
           this.kind = kind;
           this.operation = operation;
       }
   }
   ```

   ```java
   try {
       return mapper.toDomain(sberApi.register(mapper.toApi(request)));
   } catch (HttpServerErrorException ex) {
       throw new SberClientException(SberClientException.Kind.SERVER, "register", ex);
   } catch (HttpClientErrorException ex) {
       throw new SberClientException(SberClientException.Kind.CLIENT, "register", ex);
   } catch (ResourceAccessException ex) {
       throw new SberClientException(SberClientException.Kind.UNAVAILABLE, "register", ex);
   }
   ```

   ### 4.3 `RestApiExceptionHandler` в `adapter-in-rest/`

   Один `@RestControllerAdvice` на входной адаптер; по `@ExceptionHandler` на семейство, внутри — исчерпывающий `switch` по вариантам в статус + `ErrorCode` контракта, без `default`:

   ```java
   @RestControllerAdvice
   @RequiredArgsConstructor
   @Slf4j
   class RestApiExceptionHandler {

       private final ErrorTraceId errorTraceId;

       @ExceptionHandler(HubConnectionException.class)
       ResponseEntity<ProblemDetails> handle(HubConnectionException ex) {
           log.warn("Domain rule violated: {}", ex.getMessage());
           HttpStatus status = switch (ex) {
               case HubConnectionException.NotFound _ -> HttpStatus.NOT_FOUND;
               case HubConnectionException.InvalidStateTransition _ -> HttpStatus.CONFLICT;
           };
           ErrorCode code = switch (ex) {
               case HubConnectionException.NotFound _ -> ErrorCode.RESOURCE_NOT_FOUND;
               case HubConnectionException.InvalidStateTransition _ -> ErrorCode.INVALID_STATE_TRANSITION;
           };
           return problem(status, code, ex.getMessage());
       }

       @ExceptionHandler(SberClientException.class)
       ResponseEntity<ProblemDetails> handle(SberClientException ex) {
           HttpStatus status = switch (ex.getKind()) {
               case CLIENT -> HttpStatus.UNPROCESSABLE_ENTITY;
               case SERVER -> HttpStatus.BAD_GATEWAY;
               case UNAVAILABLE -> HttpStatus.SERVICE_UNAVAILABLE;
               case TIMEOUT -> HttpStatus.GATEWAY_TIMEOUT;
           };
           log.warn("Sber {} failed: {}", ex.getOperation(), ex.getKind());
           return problem(status, ErrorCode.EXTERNAL_SYSTEM_FAILURE, "Payment provider unavailable");
       }

       @ExceptionHandler(MethodArgumentNotValidException.class)
       ResponseEntity<ProblemDetails> handle(MethodArgumentNotValidException ex) { ... }   // 400 + ValidationError[]

       @ExceptionHandler(Throwable.class)
       ResponseEntity<ProblemDetails> handle(Throwable ex) {
           log.error("Unexpected error", ex);
           return problem(HttpStatus.INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, "Internal Server Error");
       }

       private ResponseEntity<ProblemDetails> problem(HttpStatus status, ErrorCode code, String detail) {
           ProblemDetails body = new ProblemDetails()
               .status(status.value()).code(code).detail(detail).traceId(errorTraceId.current());
           Metrics.counter("app_errors_total", "code", code.name()).increment();
           return ResponseEntity.status(status).body(body);
       }
   }
   ```

   Новый вариант семейства без ветки в `switch` не компилируется — так и задумано: код ответа — часть контракта, `default` его бы спрятал (`java-style/exhaustive-switch-on-sealed`). Kafka- и другие входные адаптеры получают свой обработчик со своим конвертом, не этот.

   ### 4.4 Удалить try-catch из Handler/Service/Aggregate

   Любой `try { ... } catch (Exception e) { log.error(...); return ...; }` или `catch (Exception e) { throw new RuntimeException(e); }` в `core/` — удалить. Доменное исключение проходит насквозь. Единственное исключение — relay-цикл: catch на **единице работы** (одна запись outbox), не на пачке.

   ### 4.5 `application.yml` / `build.gradle`

   - Никаких изменений в `application.yml` — Spring сам подхватывает `@RestControllerAdvice`.
   - В `build.gradle` — никаких новых зависимостей; `micrometer-core` для `app_errors_total` обычно уже есть через actuator.

   ### 4.6 Контракт и каталог сообщений

   - На каждый новый вариант — значение в enum `ErrorCode` OpenAPI-контракта (`rest-api/error-codes-enumerated`); если значения нет — это задача `ucp-api-design`, не ручной enum в коде.
   - Если в сервисе есть каталог сообщений (`ErrorMessageKeys` + `messages_*.properties` + parity-тест) — добавь ключ и тексты на всех языках; каталог — вариант, не норма, сам его не заводи.

5. **Самопроверка перед выдачей** — пройдись по чеклисту из `backend/error-handling/references/java/implementation.md` §«Чеклист подключения к новому сервису».

6. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

## Что НЕ делает

- Не настраивает Jakarta Validation (`ucp-validation-design`).
- Не настраивает резильянс / CircuitBreaker (`ucp-resilience-design`).
- Не пишет тесты — `ucp-test-design`.
- Не настраивает аутентификацию / 401/403 mapping (`ucp-auth-design`).
- Не ведёт enum `ErrorCode` в OpenAPI — `ucp-api-design`.
- Не добавляет варианты в существующие семейства под новый UseCase (это работа `ucp-pattern-design`).

После работы скилла — обязательно `ucp-error-handling-review` для верификации.

$ARGUMENTS
