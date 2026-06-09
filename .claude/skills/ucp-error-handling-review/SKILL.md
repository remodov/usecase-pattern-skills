---
name: ucp-error-handling-review
description: Ревью обработки ошибок в Spring Boot-сервисе по UCP (коды R-ERR-*) — иерархия Domain/Validation/Integration/Technical, GlobalExceptionHandler, mapping в ProblemDetails (RFC 9457), retry-семантика, наблюдаемость.
when_to_use: Ревью exception-классов, @RestControllerAdvice, out-adapter с try-catch, любого кода с catch (Exception e).
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок

Ты ревьюишь Spring Boot-сервис на соответствие `backend/error-handling/error-handling-rules.md` (`R-ERR-*`). Главные точки контроля: типизированная иерархия исключений, ровно три места catch, консистентный ProblemDetails-mapping, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/error-handling-rules.md`** — источник правил. Подгруппы: `R-ERR-HIER-*` (иерархия), `R-ERR-WHERE-*` (где throw/catch), `R-ERR-MAP-*` (ProblemDetails), `R-ERR-LOG-*` (logging), `R-ERR-RETRY-*` (retry-семантика), `R-ERR-RESULT-*` (Result vs Exception), `R-ERR-OBS-*` (observability).
- Парные документы: `backend/rest-api/rest-api-rules.md` (`R-API-ERR-*`), `backend/validation/validation-rules.md` (`R-VLD-*`), `backend/resilience/resilience-rules.md` (`R-RES-RE-*`/`R-RES-FB-*`), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-18`/`AUTH-19`), `backend/observability/observability-rules.md` (`R-OBS-LOG-*`).

## Инструкции

1. **Прочти style guide** из `.claude/docs/backend/error-handling/error-handling-rules.md`. Цитируй конкретные коды (`R-ERR-WHERE-X1`, `R-ERR-HIER-X2`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - Любые `*Exception.java` — иерархия (`R-ERR-HIER-*`).
   - `**/*ExceptionHandler*.java`, `*GlobalExceptionHandler*.java` — `@RestControllerAdvice` (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapter-out-*/**/*Adapter*.java` — port-specific exceptions, ловля HTTP/SQL/Kafka (`R-ERR-WHERE-2b`).
   - Любые `*.java` с импортами `import ...exception.*` или `throw new`.
   - `git diff` на недавно изменённые файлы из перечисленного.
   - **Поиск через `Grep`**: regex `catch\s*\(\s*(Exception|Throwable|RuntimeException)\s+\w+\s*\)` — потенциальные нарушения `R-ERR-WHERE-X1`/`X2`.

3. **Прогон по подгруппам кодов.**

   ### `R-ERR-HIER-*` — иерархия
   - Базовые типы (`DomainException`, `ValidationException`, `IntegrationException`, `TechnicalException`) определены в `core/exception/`? — `R-ERR-HIER-1`.
   - Все они — `RuntimeException`-наследники, не `Exception`/`Throwable`? — `R-ERR-HIER-2`.
   - Доменные исключения именуются по бизнес-смыслу (`InsufficientFundsException`, `OrderAlreadyShippedException`)? Не `BusinessException` / `IllegalStateException` без контекста? — `R-ERR-HIER-3`.
   - `IntegrationException`-наследники имеют префикс системы (`SberRegisterException`)? — `R-ERR-HIER-4`.
   - Конструкторы фиксируют контекст (доменные ID, значения)? Не пустые `new InsufficientFundsException()`? — `R-ERR-HIER-5`.
   - Поиск `throw new RuntimeException("...")` — `R-ERR-HIER-X1`.
   - Поиск `throw new IllegalStateException(` в `core/` коде (не в test) — `R-ERR-HIER-X2`.

   ### `R-ERR-WHERE-*` — где throw / catch
   - В `core/` (Handler, Service, Aggregate) **нет** `try ... catch` блоков? Поиск через `Grep` для `*.java` в `core/`. Любой найденный — критика `R-ERR-WHERE-X1` (если catch (Exception/Throwable)) или замечание (если catch конкретного типа с осмысленной обработкой).
   - В `adapter-out-*/`: каждый low-level catch (`HttpServerErrorException`, `SQLException`, `KafkaException`, `IOException`) превращает в port-specific exception (`R-ERR-WHERE-2b`)? Если просто пробрасывает raw — нарушение.
   - `GlobalExceptionHandler` существует, аннотирован `@RestControllerAdvice`? — `R-ERR-WHERE-2a`.
   - Поиск `catch (Exception e) { return null; }` / `return Optional.empty();` / `return new <T>();` — критика `R-ERR-WHERE-X3`.
   - Поиск `catch (Exception e) { log.error(...); }` без re-throw — критика `R-ERR-WHERE-X1` (силент фейл).
   - Поиск `catch (Exception e) { throw new RuntimeException(e); }` — критика `R-ERR-WHERE-X2`.

   ### `R-ERR-MAP-*` — ProblemDetails
   - `@ExceptionHandler(DomainException.class)` → возвращает 409 или 422? — `R-ERR-MAP-1`.
   - `@ExceptionHandler(ValidationException.class)` или `MethodArgumentNotValidException` → 400 + per-field errors? — `R-ERR-MAP-2`.
   - `@ExceptionHandler(IntegrationException.class)` → 502 / 503 / 504 в зависимости от подтипа? — `R-ERR-MAP-3`.
   - `@ExceptionHandler(Throwable.class)` или `Exception.class` (catch-all) → 500? — `R-ERR-MAP-5`.
   - В response отсутствует stacktrace, exception class, SQL-сообщения? — `R-ERR-MAP-X2`/`R-ERR-MAP-X3`.
   - Поиск `setStatus(200)` или `ResponseEntity.ok()` в exception-handler — критика `R-ERR-MAP-X1` (HTTP 200 при ошибке).

   ### `R-ERR-LOG-*` — logging
   - В `@ExceptionHandler(DomainException.class)` — `log.warn(...)` (не `error`)? — `R-ERR-LOG-1`.
   - В `@ExceptionHandler(IntegrationException.class)` — `log.warn` (одиночный fail) или `log.error` (CB открыт)? — `R-ERR-LOG-2`.
   - В catch-all — `log.error("...", ex)` с объектом исключения? — `R-ERR-LOG-3`.
   - Поиск `log.error("...", e); throw e;` — критика `R-ERR-LOG-X1` (двойное логирование).
   - Поиск `log.error(e.getMessage())` (без объекта `e`) — критика `R-ERR-LOG-X2`.

   ### `R-ERR-RETRY-*` — retry-семантика
   - `@Retry` на adapter-методе, который кидает `DomainException` / `ValidationException` — нарушение `R-ERR-RETRY-1` (не должно retry-иться).
   - `retry-exceptions` в `application.yml` включает `HttpClientErrorException` (4xx) — `R-ERR-RETRY-2`.
   - `@Retry` на write-операции без `Idempotency-Key` — критика `R-ERR-RETRY-3` + cross-ref `R-RES-RE-X1`.

   ### `R-ERR-RESULT-*`
   - Поиск `Result<`, `Either<`, `sealed interface ...Result` — если используется глобально (везде вместо exceptions) — нарушение `R-ERR-RESULT-X1`.

   ### `R-ERR-OBS-*` — observability
   - Метрика `app_errors_total{type, exception}` (или эквивалент) экспонирована? — `R-ERR-OBS-1`.
   - Алёрты в `prometheus.rules.yml` / Grafana: только на `unexpected` / `technical`, не на любую error-метрику? — `R-ERR-OBS-X1` если алёрт на всё.

4. **Cross-check с другими гайдами:**
   - `@Retry` на write без `Idempotency-Key` → также `AUTH-19` и `R-RES-RE-X1`.
   - PII в `detail`-поле ProblemDetail → также `AUTH-18` и `R-OBS-PII-*`.
   - REST-формат ProblemDetails → `R-API-ERR-*`.
   - Bean validation handler (`MethodArgumentNotValidException`) → `R-VLD-WHERE-1`.

5. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-ERR-WHERE-X1`, `R-ERR-MAP-X1`).

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — потеря сигнала или некорректный ответ клиенту:
     - `R-ERR-WHERE-X1` (silent `catch (Exception e) { log.error }` без throw) — глушение бага
     - `R-ERR-WHERE-X3` (`return null` / `Optional.empty` в catch)
     - `R-ERR-MAP-X1` (HTTP 200 при ошибке) — мониторинг прозевает
     - `R-ERR-MAP-X3` (SQL-сообщение в response) — раскрытие схемы БД
     - `R-ERR-RETRY-3` (`@Retry` на write без `Idempotency-Key`) — двойное списание
     - отсутствие catch-all в `GlobalExceptionHandler` — unhandled stacktrace в response
   - **Предупреждение** — деградация без явной потери:
     - `R-ERR-HIER-X1` (`throw new RuntimeException`) — потеря типа, generic 500
     - `R-ERR-HIER-X2` (`IllegalStateException` в доменном коде)
     - `R-ERR-WHERE-X2` (`catch / throw new RuntimeException(e)`)
     - `R-ERR-LOG-X1` (двойное логирование)
     - `R-ERR-LOG-X2` (`log.error(e.getMessage())` без stacktrace)
     - DomainException на `ERROR`-уровне — false-positive алёрты (`R-ERR-LOG-1`)
   - **Замечание** — стилистика и недокрытие:
     - отсутствие метрики `app_errors_total`
     - конструктор exception без контекста (`R-ERR-HIER-5`)
     - отсутствие spec-карточки в `docs/spec/errors/`

## Что не входит

- Конкретный формат `ProblemDetails` (поля, JSON-структура) — `ucp-api-review` (`R-API-ERR-*`).
- Bean validation rules (`@NotBlank`, `@Size`) — `ucp-validation-review`.
- Retry policy конфиг (max-attempts, backoff) — `ucp-resilience-review`.
- PII в логах / маскирование — `ucp-observability-review` + `ucp-auth-review`.
- Spring Security 401/403 mapping — `ucp-auth-review` (`AUTH-6`).

$ARGUMENTS
