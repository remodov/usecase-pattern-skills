---
name: ucp-error-handling-review
description: Ревью обработки ошибок в Spring Boot-сервисе по UCP (требования error-handling/*) — sealed-семейства на агрегат и на систему, @RestControllerAdvice на входной адаптер, switch → ErrorCode контракта, четыре места catch, retry по виду отказа.
when_to_use: Ревью exception-классов, @RestControllerAdvice, interceptor'ов клиентов и out-adapter с try-catch, любого кода с catch (Exception e).
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок

Ты ревьюишь Spring Boot-сервис на соответствие `backend/error-handling/spec.md` (`R-ERR-*`). Главные точки контроля: семейства исключений (на агрегат, на внешнюю систему), четыре места catch, исчерпывающее отображение в `ErrorCode` контракта, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/spec.md`** — источник правил. Подгруппы: `R-ERR-HIER-*` (семейства), `R-ERR-WHERE-*` (где throw/catch), `R-ERR-MAP-*` (отображение в ответ), `R-ERR-LOG-*` (logging), `R-ERR-RETRY-*` (retry-семантика), `R-ERR-RESULT-*` (Result vs Exception), `R-ERR-OBS-*` (observability).
- Парные документы: `backend/rest-api/spec.md` (`R-API-ERR-*`, `rest-api/error-codes-enumerated`), `backend/validation/spec.md` (`R-VLD-*`), `backend/resilience/spec.md` (`R-RES-RE-*`/`R-RES-FB-*`), `backend/auth-patterns/spec.md` (`auth-patterns/error-response-hides-cause`/`auth-patterns/money-commands-need-idempotency-key`), `backend/observability/spec.md` (`R-OBS-LOG-*`).

## Инструкции

0. **Проверь, что гейты, обещанные требованиями, включены:** ArchUnit `NoTryCatchInHandlersTest` (с явным исключением relay-обработчиков), Error Prone `ThrowSpecificExceptions`, integration-тест advice. Обещанный, но не включённый гейт — отдельная находка.

1. **Прочти требования** из `.claude/docs/backend/error-handling/spec.md`. Цитируй конкретные коды (`error-handling/catch-does-not-swallow`, `error-handling/no-bare-base-exceptions`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - Любые `*Exception.java` — семейства (`R-ERR-HIER-*`).
   - `**/*ExceptionHandler*.java` с `@RestControllerAdvice` — по одному на входной адаптер (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapter-out-*/**/*Interceptor*.java`, `*Adapter*.java` — перевод HTTP/SQL/Kafka в семейство системы (`R-ERR-WHERE-2b`).
   - Любые `*.java` с импортами `import ...exception.*` или `throw new`.
   - `git diff` на недавно изменённые файлы из перечисленного.
   - **Поиск через `Grep`**: regex `catch\s*\(\s*(Exception|Throwable|RuntimeException)\s+\w+\s*\)` — потенциальные нарушения `error-handling/catch-does-not-swallow`/`X2`.

3. **Прогон по подгруппам кодов.**

   ### `R-ERR-HIER-*` — семейства
   - На каждый агрегат — `sealed abstract`-семейство в `core/exception/` с вложенными `final`-вариантами, вариант на смысл отказа? Один тип с текстом «что случилось» — нарушение `error-handling/four-exception-kinds` (граница не отобразит причину в код).
   - Общие корни (`DomainException`, `IntegrationException`, `TechnicalException`, `ValidationException` как класс) — не нарушение сами по себе, но замечание: единица классификации — семейство; прямой `throw new DomainException(...)` минуя семейство — нарушение `error-handling/domain-exception-named-by-meaning`.
   - Варианты именуются по смыслу (`NotFound`, `InvalidStateTransition`, `DuplicateClient`)? Не `BusinessException` / `IllegalStateException` без контекста? — `error-handling/domain-exception-named-by-meaning`.
   - Семейство внешней системы несёт систему в имени (`SberClientException`, `PartnerClientException`) и вид отказа внутри (`Kind`/`Group`: клиентский / серверный / недоступность / таймаут)? — `error-handling/integration-exception-names-system`.
   - Конструкторы фиксируют контекст (доменные ID, значения, `args`)? Не пустые `new NotFound()`? — `error-handling/exception-carries-context`.
   - Поиск `throw new RuntimeException("...")` — `error-handling/no-bare-base-exceptions`.
   - Поиск `throw new IllegalStateException(` в `core/` (не в test) — допустим только в недостижимой ветке исчерпывающего `switch`; иначе `error-handling/no-bare-base-exceptions`.

   ### `R-ERR-WHERE-*` — где throw / catch
   - В `core/` (Handler, Service, Aggregate) **нет** `try ... catch` блоков? Поиск через `Grep` для `*.java` в `core/`. Любой найденный — критика `error-handling/catch-does-not-swallow` (если catch (Exception/Throwable)) или замечание (если catch конкретного типа с осмысленной обработкой). Исключение — relay-цикл: catch на единице работы (одна запись outbox) законен, catch на всей пачке — нарушение `error-handling/catch-in-three-places-only`.
   - В `adapter-out-*/`: каждый low-level catch (`HttpServerErrorException`, `HttpClientErrorException`, `ResourceAccessException`, `SQLException`, `KafkaException`) превращается в семейство системы с видом отказа (`R-ERR-WHERE-2b`)? Если просто пробрасывает raw — нарушение.
   - `@RestControllerAdvice` есть у каждого входного адаптера и лежит в нём, не в `bootstrap/`? Один общий advice на REST и Kafka — замечание `R-ERR-WHERE-2a` (разные конверты).
   - Поиск `catch (Exception e) { return null; }` / `return Optional.empty();` / `return new <T>();` — критика `error-handling/catch-does-not-swallow`.
   - Поиск `catch (Exception e) { log.error(...); }` без re-throw — критика `error-handling/catch-does-not-swallow` (силент фейл).
   - Поиск `catch (Exception e) { throw new RuntimeException(e); }` — критика `error-handling/catch-does-not-swallow`.

   ### `R-ERR-MAP-*` — отображение в ответ
   - `@ExceptionHandler(<Aggregate>Exception.class)` содержит `switch` по вариантам → статус + `ErrorCode` контракта (`NotFound` → 404, неверный вход → 400, конфликт состояния → 409, инвариант → 422) без `default`? `default` в разборе семейства — нарушение `java-style/exhaustive-switch-on-sealed`: новый вариант молча уйдёт чужим кодом. Вариант без ветки, уходящий 500 — нарушение `error-handling/domain-and-validation-mapping`.
   - `MethodArgumentNotValidException` → 400 + перечень по полям (`ValidationError[]`)? — `error-handling/domain-and-validation-mapping`.
   - Семейство системы отображается по виду отказа: клиентский → 409/422 кодом контракта, серверный → 502, разрыв цепи / недоступность → 503, таймаут → 504? — `error-handling/integration-and-technical-mapping`.
   - `@ExceptionHandler(Throwable.class)` (catch-all) → 500 + `traceId` через `ErrorTraceId`? — `error-handling/integration-and-technical-mapping`.
   - В response отсутствует stacktrace, exception class, SQL-сообщения? — `error-handling/integration-and-technical-mapping`.
   - `ErrorCode` берётся из сгенерированного OpenAPI-enum, не из ручного enum в коде? — `rest-api/error-codes-enumerated` (cross-ref).
   - Поиск `setStatus(200)` или `ResponseEntity.ok()` в exception-handler — критика `error-handling/no-success-code-for-failure` (HTTP 200 при ошибке).

   ### `R-ERR-LOG-*` — logging
   - В обработчике доменного семейства — `log.warn(...)` (не `error`)? — `error-handling/log-level-matches-kind`.
   - В обработчике семейства системы — `log.warn` (клиентский / единичный серверный отказ) или `log.error` (CB открыт)? — `error-handling/log-level-matches-kind`.
   - В catch-all — `log.error("...", ex)` с объектом исключения? — `error-handling/log-level-matches-kind`.
   - Поиск `log.error("...", e); throw e;` — критика `error-handling/log-once-with-exception` (двойное логирование).
   - Поиск `log.error(e.getMessage())` (без объекта `e`) — критика `error-handling/log-once-with-exception`.

   ### `R-ERR-RETRY-*` — retry-семантика
   - `@Retry` на adapter-методе, который кидает доменное семейство — нарушение `error-handling/retry-semantics-by-kind` (детерминировано, не должно retry-иться).
   - Повтор не различает вид отказа: `retry-exceptions` включает `HttpClientErrorException` (4xx) или семейство системы целиком без исключения клиентского вида — `error-handling/retry-semantics-by-kind`.
   - `@Retry` на write-операции без `Idempotency-Key` — критика `error-handling/retry-semantics-by-kind` + cross-ref `resilience/retry-only-when-safe`.

   ### `R-ERR-RESULT-*`
   - Поиск `Result<`, `Either<`, `sealed interface ...Result` — если используется глобально (везде вместо exceptions) — нарушение `error-handling/result-type-is-local-choice`.

   ### `R-ERR-OBS-*` — observability
   - Метрика `app_errors_total{code}` (или эквивалент) экспонирована? — `error-handling/errors-counted-by-kind`.
   - Алёрты в `prometheus.rules.yml` / Grafana: только на непредвиденное / открытый CB, не на любую error-метрику? — `error-handling/alert-on-patterns-not-exceptions` если алёрт на всё.

4. **Cross-check с другими гайдами:**
   - `@Retry` на write без `Idempotency-Key` → также `auth-patterns/money-commands-need-idempotency-key` и `resilience/retry-only-when-safe`.
   - PII или `cause.getMessage()` в `detail` → также `auth-patterns/error-response-hides-cause` и `R-OBS-PII-*`.
   - REST-формат `ProblemDetails` и enum `ErrorCode` → `R-API-ERR-*`.
   - Bean validation handler (`MethodArgumentNotValidException`) → `validation/input-validated-at-edge`.
   - Каталог сообщений (`ErrorMessageKeys` + `messages_*.properties`): если есть — parity-тест ключей на всех языках; если нет — не требовать.

5. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`error-handling/catch-does-not-swallow`, `error-handling/no-success-code-for-failure`).

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — потеря сигнала или некорректный ответ клиенту:
     - `error-handling/catch-does-not-swallow` (silent `catch (Exception e) { log.error }` без throw) — глушение бага
     - `error-handling/catch-does-not-swallow` (`return null` / `Optional.empty` в catch)
     - `error-handling/catch-in-three-places-only` (catch на всю пачку relay) — одна битая запись останавливает публикацию
     - `error-handling/no-success-code-for-failure` (HTTP 200 при ошибке) — мониторинг прозевает
     - `error-handling/integration-and-technical-mapping` (SQL-сообщение в response) — раскрытие схемы БД
     - `error-handling/retry-semantics-by-kind` (`@Retry` на write без `Idempotency-Key`) — двойное списание
     - отсутствие catch-all в advice входного адаптера — unhandled stacktrace в response
   - **Предупреждение** — деградация без явной потери:
     - `error-handling/four-exception-kinds` (один тип с текстом на все отказы агрегата) — клиент разбирает строку
     - `error-handling/no-bare-base-exceptions` (`throw new RuntimeException`) — потеря типа, generic 500
     - `error-handling/no-bare-base-exceptions` (`IllegalStateException` вне недостижимой ветки)
     - `error-handling/integration-exception-names-system` (raw `HttpClientErrorException` из адаптера) — граница не различит систему и вид
     - `error-handling/catch-does-not-swallow` (`catch / throw new RuntimeException(e)`)
     - `error-handling/log-once-with-exception` (двойное логирование / `log.error(e.getMessage())` без stacktrace)
     - доменный отказ на `ERROR`-уровне — false-positive алёрты (`error-handling/log-level-matches-kind`)
   - **Замечание** — стилистика и недокрытие:
     - отсутствие метрики `app_errors_total`
     - конструктор варианта без контекста (`error-handling/exception-carries-context`)
     - семейство `sealed`, но не `abstract` — исчерпывающий `switch` без `default` не соберётся, и появится соблазн его добавить
     - вариант семейства без значения `ErrorCode` в контракте
     - ключ каталога сообщений без текста в одном из `messages_*.properties`

## Что не входит

- Конкретный формат `ProblemDetails` (поля, JSON-структура) и enum `ErrorCode` — `ucp-api-review` (`R-API-ERR-*`).
- Bean validation rules (`@NotBlank`, `@Size`) — `ucp-validation-review`.
- Retry policy конфиг (max-attempts, backoff) — `ucp-resilience-review`.
- PII в логах / маскирование — `ucp-observability-review` + `ucp-auth-review`.
- Spring Security 401/403 mapping — `ucp-auth-review` (`auth-patterns/401-not-403`).

$ARGUMENTS
