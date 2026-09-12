---
name: ucp-shutdown-review
description: Ревью graceful shutdown Spring Boot-сервиса по UCP — server.shutdown=graceful, ApplicationAvailability на SIGTERM, Kafka shutdown-timeout, awaitTermination, HikariCP, k8s preStop + terminationGracePeriodSeconds, probes.
when_to_use: Изменения в application.yml, k8s-манифестах, @PreDestroy/ContextClosedEvent-хендлерах, ThreadPoolTaskExecutor-бинах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью graceful shutdown

Ты ревьюишь Spring Boot-сервис на корректное завершение по SIGTERM согласно `backend/graceful-shutdown/spec.md` (`R-SHUT-*`). Главные точки контроля: Spring graceful включён, readiness переключается на SIGTERM, k8s preStop существует и terminationGracePeriodSeconds достаточный, Kafka/TaskScheduler/Async ждут текущие задачи, in-flight write-операции идемпотентны.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/spec.md`** — источник правил. Каждое нарушение цитируется кодом из подгрупп: `R-SHUT-CFG-*` (JVM/Spring конфиг), `R-SHUT-HTTP-*` (HTTP drain), `R-SHUT-KFK-*` (Kafka), `R-SHUT-DB-*` (БД/HikariCP), `R-SHUT-SCHED-*` (Scheduled/Async/outbox), `R-SHUT-K8S-*` (k8s манифесты), `R-SHUT-IDEM-*` (идемпотентность in-flight), `R-SHUT-OBS-*` (бюджет/метрики).
- Парные документы: `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` для idempotency), `backend/resilience/spec.md` (`resilience/retry-only-when-safe`, `R-RES-ASYNC-*`), `backend/java/spring-bootstrap/spec.md` (`spring-bootstrap/service-starts-without-broker` Kafka startup, `spring-bootstrap/stub-publisher-is-overridable` ExternalEventPublisher).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/graceful-shutdown/spec.md` (полный текст с yaml/Java-примерами и таблицей бюджетов — `backend/graceful-shutdown/references/java/implementation.md`, открывай точечно по разделу). Цитируй конкретные коды (`graceful-shutdown/web-server-graceful-enabled`, `graceful-shutdown/prestop-delay`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - `application*.yml` — `server.shutdown`, `spring.lifecycle.*`, `spring.kafka.listener.shutdown-*`, `spring.task.scheduling.shutdown.*`, `management.endpoint.health.probes.*`.
   - `**/k8s/**/*.yaml`, `helm/**/templates/deployment.yaml` — `terminationGracePeriodSeconds`, `lifecycle.preStop`, `readinessProbe`, `livenessProbe`, `strategy.rollingUpdate`.
   - Java-конфигурации с `ThreadPoolTaskExecutor`/`TaskScheduler`-bean — `setWaitForTasksToCompleteOnShutdown`, `setAwaitTerminationSeconds`.
   - Java-классы с `@EventListener(ContextClosedEvent.class)` или `ContextClosedEvent`/`@PreDestroy` — кастомные shutdown-хуки.
   - Outbox-relay, @Scheduled, @KafkaListener — для проверки cascade-времени и связи с `ApplicationAvailability`.
   - `git diff` на недавно изменённые файлы из перечисленного.

3. **Прогон по подгруппам кодов.**

   ### `R-SHUT-CFG-*` — JVM/Spring
   - `application.yml`: `server.shutdown: graceful`? — `graceful-shutdown/web-server-graceful-enabled`.
   - `spring.lifecycle.timeout-per-shutdown-phase` явно прописан 20-30s? Дефолт-30s ОК но без записи легко не заметить — заметка `graceful-shutdown/shutdown-budget-is-explicit`.
   - SIGTERM-listener существует и переключает `readinessState`? Spring Boot 2.3+ делает это автоматически — но если в коде есть кастомный `ContextClosedEvent`-listener без `AvailabilityChangeEvent` — заметка `graceful-shutdown/readiness-off-first`.
   - `management.endpoint.health.probes.enabled`, `management.health.livenessstate.enabled`, `management.health.readinessstate.enabled` — все три = `true`? — `graceful-shutdown/readiness-off-first`.
   - Поиск `AtomicBoolean shuttingDown` / `volatile boolean isShuttingDown` в коде → `graceful-shutdown/readiness-off-first`.

   ### `R-SHUT-HTTP-*`
   - При наличии `graceful-shutdown/web-server-graceful-enabled` — graceful HTTP работает автоматически. Главное — нет ли в коде `WebServerCustomizer` с `forceShutdown()` или `awaitTermination(0, ...)` — `graceful-shutdown/web-server-graceful-enabled`.
   - HTTP-эндпоинты с тайм-аутом >10 сек должны быть `@Async` или async-pattern (202 Accepted) — `graceful-shutdown/long-operations-are-async`. Проверь по `@GetMapping`/`@PostMapping`-методам с явными `Thread.sleep` или долгими внешними вызовами.

   ### `R-SHUT-KFK-*`
   - `spring.kafka.listener.shutdown-timeout: <N>s` явно (10-20s)? — `graceful-shutdown/consumer-finishes-batch`.
   - `spring.kafka.listener.ack-mode: BATCH` или `RECORD`? Если `MANUAL_IMMEDIATE` — обоснование? — `graceful-shutdown/consumer-finishes-batch`.
   - `spring.kafka.consumer.enable-auto-commit: true` — критическое нарушение `graceful-shutdown/consumer-finishes-batch` (потеря offsets).
   - Внутри `@KafkaListener`-методов есть retry-cascade на 30+ секунд? — `graceful-shutdown/consumer-finishes-batch` (не уложится в shutdown-timeout).
   - Raw `KafkaProducer` (не Spring) — есть ли `producer.close(Duration.ofSeconds(...))` в `@PreDestroy`? — `graceful-shutdown/consumer-finishes-batch`.

   ### `R-SHUT-DB-*`
   - Поиск `@PreDestroy` на классах, инжектящих `DataSource`/`HikariDataSource` — кастомное закрытие? — `graceful-shutdown/connection-pool-closes-last`.
   - Активные транзакции в long-running операциях защищены через `graceful-shutdown/web-server-graceful-enabled`/`graceful-shutdown/background-tasks-finish-iteration`/`graceful-shutdown/consumer-finishes-batch` — это уже покрыто другими подгруппами.

   ### `R-SHUT-SCHED-*`
   - `spring.task.scheduling.shutdown.await-termination: true` + `await-termination-period: 20-25s`? — `graceful-shutdown/background-tasks-finish-iteration`.
   - Кастомные `ThreadPoolTaskExecutor`-bean'ы — `setWaitForTasksToCompleteOnShutdown(true)` и `setAwaitTerminationSeconds(N)` явно? Без них — `graceful-shutdown/background-tasks-finish-iteration`/`graceful-shutdown/background-tasks-finish-iteration`.
   - Outbox-relay (типичный паттерн UCP) с `while(true)` без проверки `availability.isReadinessAccepting()` — `graceful-shutdown/outbox-relay-checks-readiness` потенциально не остановится.

   ### `R-SHUT-K8S-*`
   - `terminationGracePeriodSeconds: 60` (или ≥ суммы Spring/Kafka/Sched timeouts)? Дефолт 30 — критика `graceful-shutdown/shutdown-budget-is-explicit`.
   - `lifecycle.preStop` существует со `sleep 10` (или больше)? Отсутствие — критика `graceful-shutdown/prestop-delay`.
   - `readinessProbe` → `/actuator/health/readiness`, `livenessProbe` → `/actuator/health/liveness`? Не путаются? — `graceful-shutdown/readiness-off-first`.
   - `strategy.rollingUpdate.maxSurge: 1`, `maxUnavailable: 0` для production? — `graceful-shutdown/rolling-update-keeps-capacity`.

   ### `R-SHUT-IDEM-*`
   - In-flight write-операции (HTTP POST money-related, @KafkaListener side-effects, money-adapter cascade) защищены идемпотентностью? Cross-ref на `auth-patterns/money-commands-need-idempotency-key`, `resilience/retry-only-when-safe`. Нарушения — критика `graceful-shutdown/in-flight-operations-are-retry-safe`.
   - Outbox-pattern — есть либо двух-фазный статус (`pending → publishing → published`), либо `processed_event(event_id)`-дедуп на consumer? Если ни того ни другого — `graceful-shutdown/in-flight-operations-are-retry-safe` потенциально нарушен.

   ### `R-SHUT-OBS-*`
   - Сумма timeouts (preStop + Spring graceful + TaskScheduler + Kafka) ≤ `terminationGracePeriodSeconds`? Если суммарно >60s — критика `graceful-shutdown/shutdown-budget-is-explicit` (риск SIGKILL посередине).
   - Метрика `app_shutdown_duration_seconds` или эквивалент через Micrometer? — `graceful-shutdown/shutdown-is-observable`.
   - Лог `graceful shutdown started/completed` на INFO в `ContextClosedEvent`-listener? — `graceful-shutdown/shutdown-is-observable`/`graceful-shutdown/shutdown-is-observable`.
   - Поиск `log.error("Closing JPA EntityManagerFactory")` или `log.error("HikariPool")` — `graceful-shutdown/shutdown-is-observable` (нормальные события на ERROR).

4. **При ревью кода ищи паттерны-нарушения:**
   - `application.yml` без `server.shutdown` блока — дефолт-`immediate`, нарушает `graceful-shutdown/web-server-graceful-enabled`.
   - `spring.lifecycle.timeout-per-shutdown-phase: 60s` или больше — может выйти за `terminationGracePeriodSeconds`, `graceful-shutdown/shutdown-budget-is-explicit`.
   - k8s манифест без `lifecycle:` секции — критика `graceful-shutdown/prestop-delay`.
   - `terminationGracePeriodSeconds: 30` (дефолт) — критика `graceful-shutdown/shutdown-budget-is-explicit`.
   - `setWaitForTasksToCompleteOnShutdown(false)` явно — `graceful-shutdown/background-tasks-finish-iteration`.
   - `enable.auto.commit: true` в kafka consumer — `graceful-shutdown/consumer-finishes-batch`.
   - Money-операция (наличие `Money`/`Amount`/`PaymentCommand` в сигнатуре) без `Idempotency-Key` в HTTP-handler или без `processed_event`-проверки в Kafka-listener — `graceful-shutdown/in-flight-operations-are-retry-safe`.
   - В коде свой `volatile boolean shuttingDown` — `graceful-shutdown/readiness-off-first`.

5. **Cross-check с другими гайдами:**
   - Money-операция без `Idempotency-Key` → также сошлись на `auth-patterns/money-commands-need-idempotency-key` для подкрепления.
   - `@Retry` на write без идемпотентности → `resilience/retry-only-when-safe` (требования `resilience/*`).
   - `Thread.sleep`-loop в @Scheduled или @Async → `resilience/no-long-synchronous-waits`.
   - Kafka `enable.auto.commit: true` пересекается с outbox-pattern из `spring-bootstrap/stub-publisher-is-overridable`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`graceful-shutdown/prestop-delay`, `graceful-shutdown/web-server-graceful-enabled`).

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — потеря данных или 502 для клиента под нагрузкой:
     - `graceful-shutdown/web-server-graceful-enabled` (server.shutdown ≠ graceful) — все in-flight HTTP-запросы получают 502 на каждом deploy
     - `graceful-shutdown/prestop-delay` (нет preStop) — 5-15s 502s на каждом deploy
     - `graceful-shutdown/shutdown-budget-is-explicit` (terminationGracePeriodSeconds: 30 при больших timeouts) — SIGKILL посередине дрейна
     - `graceful-shutdown/consumer-finishes-batch` (auto-commit Kafka) — потеря offset → потеря/дубль сообщений
     - `graceful-shutdown/in-flight-operations-are-retry-safe` (money без Idempotency-Key) — двойное списание при retry клиента
     - `graceful-shutdown/connection-pool-closes-last` (DataSource closed early) — частичные коммиты
   - **Предупреждение** — деградация без явной потери:
     - `graceful-shutdown/readiness-off-first` (свой AtomicBoolean) — k8s балансер не узнаёт о shutdown
     - `graceful-shutdown/background-tasks-finish-iteration` (await-termination=false) — частично выполненные таски
     - `graceful-shutdown/web-server-graceful-enabled` (forceShutdown в кастомном WebServerCustomizer)
     - `graceful-shutdown/shutdown-budget-is-explicit` (сумма timeouts > terminationGracePeriodSeconds)
   - **Замечание** — стилистика и недокрытие:
     - `graceful-shutdown/shutdown-is-observable` (нормальные события на ERROR)
     - отсутствие метрики `app_shutdown_duration_seconds` (`graceful-shutdown/shutdown-is-observable`)
     - не явно прописанный `spring.lifecycle.timeout-per-shutdown-phase` (использование дефолта)

## Что не входит

- **Startup ordering** (Liquibase до Kafka, accept-traffic после warmup) — `ucp-bootstrap-design`/`ucp-bootstrap-review`.
- **Health-check содержание** (что именно проверять в readiness — внешние системы, БД) — частично `R-RES-HC-*` (`ucp-resilience-review`).
- **Saga compensation на отказе** — `ucp-distributed-review`.
- **Crash-recovery** (OOM, SIGKILL без graceful) — реализуется через идемпотентность; покрывается через `R-SHUT-IDEM-*` cross-ref на `auth-patterns/money-commands-need-idempotency-key`/`R-RES-*`.
- **Observability metrics в целом** — `ucp-observability-review` (этот скилл проверяет только shutdown-аспект `R-SHUT-OBS-*`).

$ARGUMENTS
