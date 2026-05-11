---
name: ucp-shutdown-review
description: Ревью корректного завершения Spring Boot-сервиса по UCP — server.shutdown=graceful, ApplicationAvailability в SIGTERM-listener, Tomcat/Netty drain, Kafka listener-container shutdown-timeout, TaskScheduler/Async с awaitTermination, HikariCP не закрыт раньше времени, k8s preStop sleep + terminationGracePeriodSeconds: 60, readiness/liveness probes на actuator, идемпотентность in-flight write-операций (cross-ref AUTH-19), метрика app_shutdown_duration_seconds. Опирается на коды R-SHUT-*. Вызывается на ревью application.yml, k8s-манифестов (Deployment, Service), любых @PreDestroy / ContextClosedEvent-хендлеров, ThreadPoolTaskExecutor бинов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью graceful shutdown

Ты ревьюишь Spring Boot-сервис на корректное завершение по SIGTERM согласно `graceful-shutdown-style-guide.md` (`R-SHUT-*`). Главные точки контроля: Spring graceful включён, readiness переключается на SIGTERM, k8s preStop существует и terminationGracePeriodSeconds достаточный, Kafka/TaskScheduler/Async ждут текущие задачи, in-flight write-операции идемпотентны.

## Зависимости

- **`.claude/docs/graceful-shutdown-style-guide.md`** — источник правил. Каждое нарушение цитируется кодом из подгрупп: `R-SHUT-CFG-*` (JVM/Spring конфиг), `R-SHUT-HTTP-*` (HTTP drain), `R-SHUT-KFK-*` (Kafka), `R-SHUT-DB-*` (БД/HikariCP), `R-SHUT-SCHED-*` (Scheduled/Async/outbox), `R-SHUT-K8S-*` (k8s манифесты), `R-SHUT-IDEM-*` (идемпотентность in-flight), `R-SHUT-OBS-*` (бюджет/метрики).
- Парные документы: `auth-patterns-style-guide.md` (`AUTH-19` для idempotency), `resilience-rules.md` (`R-RES-RE-X1`, `R-RES-ASYNC-*`), `spring-bootstrap-style-guide.md` (`BS-13` Kafka startup, `BS-15` ExternalEventPublisher).

## Инструкции

1. **Прочти style guide** из `.claude/docs/graceful-shutdown-style-guide.md`. Цитируй конкретные коды (`R-SHUT-CFG-1`, `R-SHUT-K8S-X1`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - `application*.yml` — `server.shutdown`, `spring.lifecycle.*`, `spring.kafka.listener.shutdown-*`, `spring.task.scheduling.shutdown.*`, `management.endpoint.health.probes.*`.
   - `**/k8s/**/*.yaml`, `helm/**/templates/deployment.yaml` — `terminationGracePeriodSeconds`, `lifecycle.preStop`, `readinessProbe`, `livenessProbe`, `strategy.rollingUpdate`.
   - Java-конфигурации с `ThreadPoolTaskExecutor`/`TaskScheduler`-bean — `setWaitForTasksToCompleteOnShutdown`, `setAwaitTerminationSeconds`.
   - Java-классы с `@EventListener(ContextClosedEvent.class)` или `ContextClosedEvent`/`@PreDestroy` — кастомные shutdown-хуки.
   - Outbox-relay, @Scheduled, @KafkaListener — для проверки cascade-времени и связи с `ApplicationAvailability`.
   - `git diff` на недавно изменённые файлы из перечисленного.

3. **Прогон по подгруппам кодов.**

   ### `R-SHUT-CFG-*` — JVM/Spring
   - `application.yml`: `server.shutdown: graceful`? — `R-SHUT-CFG-1`.
   - `spring.lifecycle.timeout-per-shutdown-phase` явно прописан 20-30s? Дефолт-30s ОК но без записи легко не заметить — заметка `R-SHUT-CFG-2`.
   - SIGTERM-listener существует и переключает `readinessState`? Spring Boot 2.3+ делает это автоматически — но если в коде есть кастомный `ContextClosedEvent`-listener без `AvailabilityChangeEvent` — заметка `R-SHUT-CFG-3`.
   - `management.endpoint.health.probes.enabled`, `management.health.livenessstate.enabled`, `management.health.readinessstate.enabled` — все три = `true`? — `R-SHUT-CFG-4`.
   - Поиск `AtomicBoolean shuttingDown` / `volatile boolean isShuttingDown` в коде → `R-SHUT-CFG-X1`.

   ### `R-SHUT-HTTP-*`
   - При наличии `R-SHUT-CFG-1` — graceful HTTP работает автоматически. Главное — нет ли в коде `WebServerCustomizer` с `forceShutdown()` или `awaitTermination(0, ...)` — `R-SHUT-HTTP-X1`.
   - HTTP-эндпоинты с тайм-аутом >10 сек должны быть `@Async` или async-pattern (202 Accepted) — `R-SHUT-HTTP-3`. Проверь по `@GetMapping`/`@PostMapping`-методам с явными `Thread.sleep` или долгими внешними вызовами.

   ### `R-SHUT-KFK-*`
   - `spring.kafka.listener.shutdown-timeout: <N>s` явно (10-20s)? — `R-SHUT-KFK-1`.
   - `spring.kafka.listener.ack-mode: BATCH` или `RECORD`? Если `MANUAL_IMMEDIATE` — обоснование? — `R-SHUT-KFK-3`.
   - `spring.kafka.consumer.enable-auto-commit: true` — критическое нарушение `R-SHUT-KFK-X1` (потеря offsets).
   - Внутри `@KafkaListener`-методов есть retry-cascade на 30+ секунд? — `R-SHUT-KFK-2` (не уложится в shutdown-timeout).
   - Raw `KafkaProducer` (не Spring) — есть ли `producer.close(Duration.ofSeconds(...))` в `@PreDestroy`? — `R-SHUT-KFK-4`.

   ### `R-SHUT-DB-*`
   - Поиск `@PreDestroy` на классах, инжектящих `DataSource`/`HikariDataSource` — кастомное закрытие? — `R-SHUT-DB-X1`.
   - Активные транзакции в long-running операциях защищены через `R-SHUT-HTTP-1`/`R-SHUT-SCHED-1`/`R-SHUT-KFK-1` — это уже покрыто другими подгруппами.

   ### `R-SHUT-SCHED-*`
   - `spring.task.scheduling.shutdown.await-termination: true` + `await-termination-period: 20-25s`? — `R-SHUT-SCHED-1`.
   - Кастомные `ThreadPoolTaskExecutor`-bean'ы — `setWaitForTasksToCompleteOnShutdown(true)` и `setAwaitTerminationSeconds(N)` явно? Без них — `R-SHUT-SCHED-2`/`R-SHUT-SCHED-X1`.
   - Outbox-relay (типичный паттерн UCP) с `while(true)` без проверки `availability.isReadinessAccepting()` — `R-SHUT-SCHED-3` потенциально не остановится.

   ### `R-SHUT-K8S-*`
   - `terminationGracePeriodSeconds: 60` (или ≥ суммы Spring/Kafka/Sched timeouts)? Дефолт 30 — критика `R-SHUT-K8S-X2`.
   - `lifecycle.preStop` существует со `sleep 10` (или больше)? Отсутствие — критика `R-SHUT-K8S-X1`.
   - `readinessProbe` → `/actuator/health/readiness`, `livenessProbe` → `/actuator/health/liveness`? Не путаются? — `R-SHUT-K8S-2`.
   - `strategy.rollingUpdate.maxSurge: 1`, `maxUnavailable: 0` для production? — `R-SHUT-K8S-3`.

   ### `R-SHUT-IDEM-*`
   - In-flight write-операции (HTTP POST money-related, @KafkaListener side-effects, money-adapter cascade) защищены идемпотентностью? Cross-ref на `AUTH-19`, `R-RES-RE-X1`. Нарушения — критика `R-SHUT-IDEM-X1`.
   - Outbox-pattern — есть либо двух-фазный статус (`pending → publishing → published`), либо `processed_event(event_id)`-дедуп на consumer? Если ни того ни другого — `R-SHUT-IDEM-1` потенциально нарушен.

   ### `R-SHUT-OBS-*`
   - Сумма timeouts (preStop + Spring graceful + TaskScheduler + Kafka) ≤ `terminationGracePeriodSeconds`? Если суммарно >60s — критика `R-SHUT-OBS-1` (риск SIGKILL посередине).
   - Метрика `app_shutdown_duration_seconds` или эквивалент через Micrometer? — `R-SHUT-OBS-2`.
   - Лог `graceful shutdown started/completed` на INFO в `ContextClosedEvent`-listener? — `R-SHUT-OBS-2`/`R-SHUT-OBS-X1`.
   - Поиск `log.error("Closing JPA EntityManagerFactory")` или `log.error("HikariPool")` — `R-SHUT-OBS-X1` (нормальные события на ERROR).

4. **При ревью кода ищи паттерны-нарушения:**
   - `application.yml` без `server.shutdown` блока — дефолт-`immediate`, нарушает `R-SHUT-CFG-1`.
   - `spring.lifecycle.timeout-per-shutdown-phase: 60s` или больше — может выйти за `terminationGracePeriodSeconds`, `R-SHUT-OBS-1`.
   - k8s манифест без `lifecycle:` секции — критика `R-SHUT-K8S-X1`.
   - `terminationGracePeriodSeconds: 30` (дефолт) — критика `R-SHUT-K8S-X2`.
   - `setWaitForTasksToCompleteOnShutdown(false)` явно — `R-SHUT-SCHED-X1`.
   - `enable.auto.commit: true` в kafka consumer — `R-SHUT-KFK-X1`.
   - Money-операция (наличие `Money`/`Amount`/`PaymentCommand` в сигнатуре) без `Idempotency-Key` в HTTP-handler или без `processed_event`-проверки в Kafka-listener — `R-SHUT-IDEM-X1`.
   - В коде свой `volatile boolean shuttingDown` — `R-SHUT-CFG-X1`.

5. **Cross-check с другими гайдами:**
   - Money-операция без `Idempotency-Key` → также сошлись на `AUTH-19` для подкрепления.
   - `@Retry` на write без идемпотентности → `R-RES-RE-X1` (resilience-style-guide).
   - `Thread.sleep`-loop в @Scheduled или @Async → `R-RES-ASYNC-X1`.
   - Kafka `enable.auto.commit: true` пересекается с outbox-pattern из `BS-15`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-SHUT-K8S-X1`, `R-SHUT-CFG-1`).

7. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — потеря данных или 502 для клиента под нагрузкой:
     - `R-SHUT-CFG-1` (server.shutdown ≠ graceful) — все in-flight HTTP-запросы получают 502 на каждом deploy
     - `R-SHUT-K8S-X1` (нет preStop) — 5-15s 502s на каждом deploy
     - `R-SHUT-K8S-X2` (terminationGracePeriodSeconds: 30 при больших timeouts) — SIGKILL посередине дрейна
     - `R-SHUT-KFK-X1` (auto-commit Kafka) — потеря offset → потеря/дубль сообщений
     - `R-SHUT-IDEM-X1` (money без Idempotency-Key) — двойное списание при retry клиента
     - `R-SHUT-DB-X1` (DataSource closed early) — частичные коммиты
   - **Предупреждение** — деградация без явной потери:
     - `R-SHUT-CFG-X1` (свой AtomicBoolean) — k8s балансер не узнаёт о shutdown
     - `R-SHUT-SCHED-X1` (await-termination=false) — частично выполненные таски
     - `R-SHUT-HTTP-X1` (forceShutdown в кастомном WebServerCustomizer)
     - `R-SHUT-OBS-1` (сумма timeouts > terminationGracePeriodSeconds)
   - **Замечание** — стилистика и недокрытие:
     - `R-SHUT-OBS-X1` (нормальные события на ERROR)
     - отсутствие метрики `app_shutdown_duration_seconds` (`R-SHUT-OBS-2`)
     - не явно прописанный `spring.lifecycle.timeout-per-shutdown-phase` (использование дефолта)

## Что не входит

- **Startup ordering** (Liquibase до Kafka, accept-traffic после warmup) — `ucp-bootstrap-design`/`ucp-bootstrap-review`.
- **Health-check содержание** (что именно проверять в readiness — внешние системы, БД) — частично `R-RES-HC-*` (`ucp-resilience-review`).
- **Saga compensation на отказе** — `ucp-distributed-review`.
- **Crash-recovery** (OOM, SIGKILL без graceful) — реализуется через идемпотентность; покрывается через `R-SHUT-IDEM-*` cross-ref на `AUTH-19`/`R-RES-*`.
- **Observability metrics в целом** — `ucp-observability-review` (этот скилл проверяет только shutdown-аспект `R-SHUT-OBS-*`).

$ARGUMENTS
