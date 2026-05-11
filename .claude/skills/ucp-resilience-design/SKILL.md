---
name: ucp-resilience-design
description: Добавить Resilience4j-обвязку (Circuit Breaker, Bulkhead, Retry, Timeout, HealthIndicator) к УЖЕ существующему out-adapter, который сейчас работает на ad-hoc try/catch + timeouts. Миграционный скилл — превращает «защита из try-catch» в стандарт R-RES-*. Не создаёт новые модули, не трогает port в core/. Решает: per-system isolation OkHttpClient/RestClient, аннотации на adapter-методах (не на generated client), retry только при идемпотентности (R-RES-RE-1, AUTH-19), task-queue вместо sleep-loop polling, HealthIndicator с TTL-кешем. Применяется к существующим адаптерам, для новых интеграций — ucp-integration-design. Триггеры: «обвяжи адаптер X через Resilience4j», «добавь Circuit Breaker к sber-out-adapter», «мигрируй <system>-out-adapter под R-RES-*».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Resilience-обвязка существующего адаптера

Ты добавляешь Resilience4j-аннотации, конфиг и HealthIndicator к **уже существующему** out-adapter'у, который сейчас защищается ad-hoc (только timeouts + try/catch). Цель — миграция к Resilience Style Guide шаг за шагом, не trash-rewrite.

Для **новых** интеграций (новый внешний клиент с нуля) — используй `ucp-integration-design`.

## Инструкции

1. **Прочитай** `.claude/docs/resilience-rules.md` (главный, правила `R-RES-*`) и `.claude/docs/auth-patterns-style-guide.md` (`AUTH-19` для retry-решения).

2. **Идентифицируй существующий out-adapter:**
   - `git diff` или путь от пользователя.
   - Найди `<X>ClientAdapter.java`, `<X>ClientConfig.java` (или подобные имена).
   - Определи имя системы (`<system>`) — slug из имени класса/пакета.

3. **Проинспектируй текущее состояние адаптера** (что есть, что нужно добавить):
   - **Имеется ли `OkHttpClient`/`RestClient` бин?** Per-system или shared? Если shared — это нарушение `R-RES-ISO-X1`, шаг 1 миграции — разделить.
   - **Есть ли уже Resilience4j-аннотации?** Если есть — какие методы покрыты, какие пропущены?
   - **Какие методы в adapter** — public-операции, оборачивающие generated client? Это объекты для аннотаций (`R-RES-CB-1`).
   - **Идемпотентность каждого метода:**
     - GET-эквивалент → `@Retry` ОК.
     - Write с `Idempotency-Key` (`AUTH-19`) → `@Retry` ОК.
     - Write без → **только** `@CircuitBreaker` + `@Bulkhead`, без `@Retry` (`R-RES-RE-X1`).
   - **Есть ли `Thread.sleep` в коде** (особенно в циклах)? Это нарушение `R-RES-ASYNC-X1`. Перевести в task-queue (если в адаптере) или в комментарий «TODO миграция к task-queue» (если требует доработки в core/).
   - **Есть ли `<System>HealthIndicator`?** Если нет — добавить.
   - **Application.yml** — есть ли блок `resilience4j.*.instances.<system>`? Если нет — добавить.
   - **Money/non-money:** определить из доменного контекста (если адаптер реализует `PaymentPort`, `BillingPort` — money; `NotificationPort`, `LookupPort` — non-money). Влияет на CB threshold (30% vs 50%) и fallback strategy.

4. **Произведи изменения.** Lombok-defaults обязательны (`JS-6.1`–`JS-6.7`). Не цитируй коды правил в комментариях кода (`JS-7.3`).

   ### 4.1. Per-system isolation в `<X>ClientConfig.java`
   - Если бин клиента сейчас shared — раздели его на `@Bean("<system>RestClient")` или `@Bean("<system>OkHttpClient")`.
   - Свой `Dispatcher`/`ConnectionPool` per-system (`R-RES-ISO-1`).
   - `<System>ClientSettings` (`@ConfigurationProperties("client.<system>")`) — если ещё нет.

   ### 4.2. Аннотации в `<X>ClientAdapter.java`
   На каждом public-методе, который вызывает generated client:

   ```java
   // ВАРИАНТ A: idempotent (read или Idempotency-Key) — все три
   @CircuitBreaker(name = "<system>", fallbackMethod = "<op>Fallback")
   @Bulkhead(name = "<system>")
   @Retry(name = "<system>")
   public <X>Result <op>(<X>Command cmd) { ... }

   // ВАРИАНТ B: non-idempotent write — БЕЗ @Retry
   @CircuitBreaker(name = "<system>", fallbackMethod = "<op>Fallback")
   @Bulkhead(name = "<system>")
   public <X>Result <op>(<X>Command cmd) { ... }
   ```

   Fallback-методы:
   - **Money** → fallback ставит запрос в task-queue, возвращает `<X>Result.queued(taskId)`. Не `null`/`Money.ZERO` (`R-RES-FB-X1`).
   - **Non-money read** → fallback из локального кеша или пустой результат (`<X>Result.empty()`).
   - **Если адаптер не имеет очевидной fallback-стратегии** → fallback бросает port-specific exception, handler решит на верхнем уровне. Тогда `fallbackMethod` опускается, а `CallNotPermittedException` маппится в exception (`R-RES-CB-6`).

   ### 4.3. `Thread.sleep`-loop polling (если есть, как в bus-tickets `InsuranceClientAdapter`)

   Если в коде adapter обнаружен `Thread.sleep` в цикле, опрашивающем внешнюю систему (антипаттерн `R-RES-ASYNC-X1`):

   - **Не переписывай** прямо сейчас в task-queue (это требует доработок в `core/` — Port + UseCase + scheduler).
   - **Замени логику** на одиночный sync-вызов и **TODO-комментарий**:
     ```java
     // TODO R-RES-ASYNC-1: sync-polling блокирует worker-threads.
     //   Перевести в task-queue: создать <X>PollingTask + scheduler @Scheduled(5s).
     //   См. resilience-rules.md §11. Координирует ucp-pattern-design.
     ```
   - В выводе — отдельный пункт «**Требует доработки в `core/`:** перевод polling в task-queue». Возможно отдельный PR.

   ### 4.4. `<System>HealthIndicator.java`
   Если ещё нет — создать (см. шаблон в `ucp-integration-design` пункт 4.3 или Resilience Style Guide §10). С `AtomicReference<CachedHealth>` и TTL 30s.

   ### 4.5. Patch `application.yml`
   Добавить блок per-system instances:
   ```yaml
   resilience4j:
     circuitbreaker:
       configs.default:                          # если ещё не определён
         sliding-window-type: COUNT_BASED
         sliding-window-size: 50
         minimum-number-of-calls: 10
         failure-rate-threshold: 50
         wait-duration-in-open-state: 30s
         permitted-number-of-calls-in-half-open-state: 3
       instances.<system>:
         base-config: default
         failure-rate-threshold: 30              # money — порог ниже
     bulkhead.instances.<system>:
       max-concurrent-calls: 16                  # ≈ pool max-concurrent × 0.8
       max-wait-duration: 100ms
     retry.instances.<system>:                   # ТОЛЬКО если adapter имеет @Retry-методы
       max-attempts: 3
       wait-duration: 500ms
       enable-exponential-backoff: true
       exponential-backoff-multiplier: 2.0
       retry-exceptions:
         - java.io.IOException
         - org.springframework.web.client.HttpServerErrorException
       ignore-exceptions:
         - org.springframework.web.client.HttpClientErrorException

   management:
     health:
       <system>:
         enabled: true
   ```

5. **Самопроверка перед выдачей** (`R-RES-*`):
   - Per-system bean'ы клиента (а не shared default).
   - Каждый public-метод адаптера имеет `@CircuitBreaker(name = "<system>")` + `@Bulkhead(name = "<system>")`.
   - `@Retry` только на idempotent (read / write с Idempotency-Key).
   - `@Retry` без `enable-exponential-backoff` запрещён.
   - Fallback-методы не возвращают null/zero для money.
   - HealthIndicator с TTL-кешем существует.
   - Все sleep-loop polling — заменены на одиночный вызов + TODO-комментарий.
   - В application.yml — блок `resilience4j.*.instances.<system>` присутствует.

6. **Структура вывода:**
   1. **Audit текущего состояния:** одна таблица — что есть, чего нет, какие нарушения `R-RES-*`-кодов обнаружены.
   2. **План миграции** — какие правила покрываются этим скиллом сейчас, что требует отдельной работы (например, переход polling-loop в task-queue нужно делать вместе с `ucp-pattern-design`).
   3. **Изменения по файлам:**
      - Каждый изменённый файл — отдельный code block.
      - Patch для `application.yml` — явно «add» / «replace».
   4. **Заметки по реализации:**
      - Команды проверки: `./gradlew compileJava`, `./gradlew test --tests *<X>ClientAdapterTest`.
      - Если есть TODO в коде (sleep-loop) — список TODO в отчёте с приоритетами.
      - **Финальный шаг:** «запусти `ucp-resilience-review <x>-out-adapter/`» для верификации.

## Что НЕ делает

- Не создаёт новые модули, не трогает port-интерфейс в `core/`. Полное создание интеграции — `ucp-integration-design`.
- Не делает sync-polling в task-queue полностью — только помечает TODO. Полный перевод требует UseCase-handler в core, scheduler — это `ucp-pattern-design`.
- Не настраивает gradle dependencies — добавление `resilience4j-spring-boot3` в `bootstrap` происходит один раз через `ucp-bootstrap-design`.
- Не пишет тесты — `ucp-test-design` отдельным шагом.

После работы скилла — обязательно `ucp-resilience-review` для верификации, что миграция не оставила пропусков.

$ARGUMENTS
