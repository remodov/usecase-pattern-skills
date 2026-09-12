# Graceful Shutdown — реализация

Правила корректного завершения Spring Boot-сервиса по Use Case Pattern. Каждое правило имеет код `R-SHUT-*` — скилл `ucp-shutdown-review` цитирует их в findings.

Базовый принцип (`graceful-shutdown/no-work-lost-on-sigterm`): **получив SIGTERM, сервис обязан завершиться без потерь**. Активные HTTP-запросы дожимаются до 200/503; in-flight Kafka-batch коммитится; @Scheduled-таски доводятся до конца текущей итерации; БД-транзакции либо коммитятся, либо откатываются. Pod, который умирает «как есть», создаёт каскад инцидентов: 502 у клиента → retry → дубль (если операция не идемпотентна) → расходы.

`graceful-shutdown/shutdown-budget-is-explicit` **Total budget — 60 секунд** (`terminationGracePeriodSeconds: 60` в k8s). После этого SIGKILL — никто не ждёт. Из этого budget раскладывается всё ниже: preStop sleep + Spring graceful timeout + Kafka commit + БД-tx. Если суммарно не помещается — переразбейте операции, не увеличивайте budget. Долгое завершение = долгий rolling deploy = окно с двумя версиями кода против одной БД.

`graceful-shutdown/readiness-off-first` **`ApplicationAvailability` — единственный источник правды о состоянии**. Не свои `AtomicBoolean`-ы, не статические переменные. Health-эндпоинты (`/actuator/health/readiness`, `/actuator/health/liveness`) опираются на него; SIGTERM-listener переключает `readinessState` в `OUT_OF_SERVICE`; k8s endpoints-controller убирает pod из service-роутинга. Без этого balancer продолжает слать трафик в умирающий pod до самого SIGKILL.

---

## 1. JVM/Spring конфигурация — `R-SHUT-CFG-*`

`graceful-shutdown/web-server-graceful-enabled` **`server.shutdown=graceful`** в `application.yml` — обязательно. Без этого Spring Boot убивает Tomcat/Netty `forceShutdown()` сразу на SIGTERM, активные HTTP-запросы получают `IOException`/`502` на клиенте.

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

`graceful-shutdown/shutdown-budget-is-explicit` **`spring.lifecycle.timeout-per-shutdown-phase: 30s`** — максимальное ожидание per-phase Spring-shutdown. Дефолт `30s`, явно прописывается чтобы видеть. Меньше 20s — мало для дрейна Tomcat thread-pool под нагрузкой; больше 45s — рискуете попасть в SIGKILL внутри `terminationGracePeriodSeconds: 60` (`graceful-shutdown/shutdown-budget-is-explicit`).

`graceful-shutdown/readiness-off-first` **Hook на SIGTERM ставит `ApplicationAvailability.readinessState = OUT_OF_SERVICE`** в первую очередь. Это делает Spring Boot 2.3+ автоматически (`GracefulShutdown.AvailabilityState`-listener), но проверять — обязательно. После переключения health/readiness начинает возвращать `503`, k8s через 1-2 секунды убирает pod из endpoints.

```java
@Component
@RequiredArgsConstructor
class ShutdownAvailabilityListener {

    private final ApplicationEventPublisher events;

    @EventListener(ContextClosedEvent.class)
    void onShutdown() {
        events.publishEvent(new AvailabilityChangeEvent<>(this, ReadinessState.REFUSING_TRAFFIC));
    }
}
```

`graceful-shutdown/readiness-off-first` **`management.endpoint.health.probes.enabled=true`** + `management.health.livenessstate.enabled=true` + `management.health.readinessstate.enabled=true`. Spring Boot экспонирует `/actuator/health/liveness` и `/actuator/health/readiness` отдельно — k8s probe-конфиг ссылается на них.

`graceful-shutdown/readiness-off-first` ❌ Свой `AtomicBoolean shuttingDown` или `volatile boolean isShuttingDown` вместо `ApplicationAvailability`. Не интегрируется с health-эндпоинтами, k8s об этом не узнает.

---

## 2. HTTP drain — `R-SHUT-HTTP-*`

`graceful-shutdown/web-server-graceful-enabled` **In-flight HTTP-запросы дожимаются до response**, новые принимаются ровно до момента переключения readiness в `OUT_OF_SERVICE`. Spring Boot graceful делает это автоматически — но требует `graceful-shutdown/web-server-graceful-enabled`.

`graceful-shutdown/prestop-delay` **`preStop` hook со `sleep 10`** в k8s-манифесте. Это **обязательно** даже при правильном Spring graceful — потому что k8s запускает SIGTERM **до того**, как kube-proxy на других нодах распространит «убрать pod из endpoints». Без `preStop` 5-15 секунд нового трафика приходит на pod, который уже начал shutdown.

```yaml
spec:
  containers:
    - name: app
      lifecycle:
        preStop:
          exec:
            command: ["sh", "-c", "sleep 10"]
```

10 секунд — типичное значение для kube-proxy iptables-update + balancer cache-flush. На больших кластерах (1000+ nodes) — до 20.

`graceful-shutdown/long-operations-are-async` **Долгие синхронные эндпоинты (>10 сек)** должны иметь `@Async` + `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`) либо async-pattern «202 Accepted + polling». Иначе при shutdown они либо съедают весь graceful timeout, либо обрываются на полпути.

`graceful-shutdown/web-server-graceful-enabled` ❌ `Tomcat`/`Netty` worker-threads с дефолтным `awaitTermination(0, TimeUnit.SECONDS)` в кастомных `WebServerCustomizer`. Аннулирует graceful.

---

## 3. Kafka shutdown — `R-SHUT-KFK-*`

`graceful-shutdown/consumer-finishes-batch` **`@KafkaListener`-консьюмер дожимает текущий batch и коммитит offset перед остановкой.** Spring Kafka делает это через `ConcurrentMessageListenerContainer.stop(timeout)` — настраивается через `spring.kafka.listener.shutdown-timeout: 20s`.

```yaml
spring:
  kafka:
    listener:
      shutdown-timeout: 20s            # max ожидание per-container
      ack-mode: BATCH                  # commit явный, не auto
```

`graceful-shutdown/consumer-finishes-batch` **Listener-метод не должен запускать долгий cascade.** Если внутри `@KafkaListener`-метода идёт chain HTTP-вызовов с retry'ями на 30 секунд — он не уложится в `shutdown-timeout`. Cascade выносится в отдельный async-flow либо в outbox.

`graceful-shutdown/consumer-finishes-batch` **`ack-mode: BATCH` или `RECORD` явно**, не `MANUAL_IMMEDIATE` без обоснования. `BATCH` — оптимально: один commit на batch, при shutdown гарантирует, что текущий batch либо закоммичен полностью, либо ни одна запись не считается обработанной (replay при рестарте — идемпотентность защищает, см. `graceful-shutdown/in-flight-operations-are-retry-safe`).

`graceful-shutdown/consumer-finishes-batch` **Producer.flush() на shutdown** — Spring Boot делает автоматически через `KafkaTemplate.destroy()`. Если используется raw `KafkaProducer` — обязательно `producer.close(Duration.ofSeconds(15))`.

`graceful-shutdown/consumer-finishes-batch` ❌ `enable.auto.commit: true`. При shutdown часть offset'ов закоммичена auto-thread'ом до фактической обработки записи — replay невозможен, потеря сообщений. Уже запрещено `spring-bootstrap/no-double-encoding-of-payload`-связанными правилами, тут — повторение для контекста.

---

## 4. БД и persistence — `R-SHUT-DB-*`

`graceful-shutdown/connection-pool-closes-last` **HikariCP закрывается после Spring shutdown phases.** Дефолтное поведение Spring Boot правильное — `DataSource.close()` идёт в последней фазе. Не переопределяй `@PreDestroy` на DataSource — может закрыть pool до того, как @Scheduled закончил последний tx.

`graceful-shutdown/transactions-finish-in-own-channel` **Активные транзакции** на момент SIGTERM:
- HTTP-handler в transaction → graceful HTTP дожимает до commit/rollback (`graceful-shutdown/web-server-graceful-enabled`).
- @Scheduled-метод в transaction → ждать завершения текущей итерации (`graceful-shutdown/background-tasks-finish-iteration`).
- @KafkaListener в transaction → batch завершается, commit (`graceful-shutdown/consumer-finishes-batch`).
- @Async в transaction — отдельная боль, см. `graceful-shutdown/background-tasks-finish-iteration`.

`graceful-shutdown/transactions-finish-in-own-channel` **Liquibase / Flyway не запускаются на shutdown.** Это про startup, упомянуто чтобы исключить миф «надо что-то очистить при выходе».

`graceful-shutdown/connection-pool-closes-last` ❌ `DataSource.close()` или `pool.shutdown()` в кастомном `@PreDestroy` сервиса с `@Order(LOWEST_PRECEDENCE)`. Гарантированно закроет pool до того, как все scheduled-таски доделаются.

---

## 5. Scheduled / @Async / outbox — `R-SHUT-SCHED-*`

`graceful-shutdown/background-tasks-finish-iteration` **`@Scheduled`-методы завершают текущую итерацию, не начинают новую.** Spring Boot управляет этим через `TaskScheduler.shutdown()` — параметры:

```yaml
spring:
  task:
    scheduling:
      shutdown:
        await-termination: true
        await-termination-period: 25s
```

`await-termination: true` — обязательно, иначе scheduler грохает таски `interrupt()`-ом мгновенно. `25s` — должно умещаться в `graceful-shutdown/shutdown-budget-is-explicit` budget (60с total) с учётом preStop (10с) + graceful (30с) + Kafka (20с) — суммарно 85с! Поэтому **нельзя** все timeouts держать на максимуме одновременно. Реалистичное распределение бюджета — отдельная таблица в §8.

`graceful-shutdown/background-tasks-finish-iteration` **`@Async`-таски с долгим cascade** опасны: при SIGTERM ExecutorService по умолчанию делает `interrupt()` через `awaitTermination(timeout)`. Любой `Thread.sleep` или blocking call внутри — `InterruptedException`. Конфигурируем `ThreadPoolTaskExecutor` с `setAwaitTerminationSeconds` явно:

```java
@Bean(destroyMethod = "shutdown")
public ThreadPoolTaskExecutor asyncExecutor() {
    var ex = new ThreadPoolTaskExecutor();
    ex.setCorePoolSize(8);
    ex.setMaxPoolSize(16);
    ex.setQueueCapacity(100);
    ex.setWaitForTasksToCompleteOnShutdown(true);
    ex.setAwaitTerminationSeconds(20);
    return ex;
}
```

`graceful-shutdown/outbox-relay-checks-readiness` **Outbox-relay** (типовой паттерн UCP) на SIGTERM:
- Завершает текущий batch (его в БД через `FOR UPDATE SKIP LOCKED` уже нельзя «потерять» — это атомарно).
- Не начинает новый batch.
- При следующем старте — `SKIP LOCKED` уже не блокирует, новый relay подхватывает.

Это работает «само» при `graceful-shutdown/background-tasks-finish-iteration` + jOOQ-pattern (`R-JOOQ-LCK-*`). Главное — не запускать relay-цикл с `while(true)` без проверки `availability.isReadinessAccepting()`.

`graceful-shutdown/background-tasks-finish-iteration` ❌ `setWaitForTasksToCompleteOnShutdown(false)` без обоснования. Все таски убиты, частичные изменения в БД — без rollback в общем случае (commit мог пройти, side-effect-вызов внешней системы — нет → нерпо unconsistent state).

---

## 6. Kubernetes — `R-SHUT-K8S-*`

`graceful-shutdown/shutdown-budget-is-explicit` **`terminationGracePeriodSeconds: 60`** — обязательно прописано в Deployment, не дефолт-30. Внутрь не входит preStop sleep — он отдельный бюджет.

```yaml
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: app
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 10"]
```

`graceful-shutdown/readiness-off-first` **`readinessProbe`** настроен на `/actuator/health/readiness`, `livenessProbe` на `/actuator/health/liveness`. Не путать — `liveness` падение перезапускает pod, `readiness` падение убирает из endpoints без рестарта. На shutdown нужен именно readiness=503.

```yaml
readinessProbe:
  httpGet: { path: /actuator/health/readiness, port: 8080 }
  periodSeconds: 5
  failureThreshold: 2
livenessProbe:
  httpGet: { path: /actuator/health/liveness, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3
```

`graceful-shutdown/rolling-update-keeps-capacity` **`maxSurge: 1, maxUnavailable: 0`** на rolling deploy production-сервисов. Гарантирует, что новый pod уже принимает трафик до того, как старый начал shutdown — нулевой downtime.

`graceful-shutdown/prestop-delay` ❌ Отсутствие `preStop`. Без него 5-15 секунд после SIGTERM kube-proxy ещё льёт трафик — все эти запросы получат 502, даже при идеально настроенном Spring graceful.

`graceful-shutdown/shutdown-budget-is-explicit` ❌ `terminationGracePeriodSeconds: 30` (k8s default) с `R-SHUT-CFG-2: 30s` Spring graceful timeout. preStop (10s) уже не помещается — pod уйдёт в SIGKILL посередине дрейна.

---

## 7. Идемпотентность in-flight операций — `R-SHUT-IDEM-*`

`graceful-shutdown/in-flight-operations-are-retry-safe` **In-flight операции, которые SIGTERM может прервать, обязаны быть retry-safe.** Это сшивка с `auth-patterns/money-commands-need-idempotency-key`: write-операции с `Idempotency-Key`, money-cascade в task-queue (`R-RES-ASYNC-*`), Kafka-handler через outbox + dedup-таблица (`processed_event` на event_id).

Граничные случаи:
- HTTP POST без `Idempotency-Key` + shutdown посередине → клиент ретрается → дубль. Защита: контракт требует `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`).
- Kafka-listener закоммитил offset, но не завершил side-effect → replay создаёт дубль side-effect-а. Защита: `processed_event(event_id)`-таблица в той же tx, что и side-effect.
- Outbox-relay отправил в Kafka, но не пометил row `published=true` → следующий relay отправит повторно. Защита: либо двух-фаза (`pending → publishing → published`), либо `processed_event`-дедуп на consumer-стороне.

`graceful-shutdown/in-flight-operations-are-retry-safe` ❌ Money-операция без `Idempotency-Key` в адаптере, защищаемая `@Retry(name = "...")`. При SIGTERM в момент retry первый вызов прошёл (списал деньги), retry в новом pod-е спишет ещё раз. Уже запрещено `resilience/retry-only-when-safe` — здесь напоминание контекста.

---

## 8. Бюджеты и observability — `R-SHUT-OBS-*`

`graceful-shutdown/shutdown-budget-is-explicit` **Реалистичный бюджет shutdown** (cumulative, не параллельный):

| Этап | Длительность | Параметр |
|---|---|---|
| preStop sleep (kube-proxy distribution) | 10s | `lifecycle.preStop` |
| Spring graceful (HTTP drain) | до 25s | `spring.lifecycle.timeout-per-shutdown-phase` |
| TaskScheduler / @Async | до 20s | `spring.task.scheduling.shutdown.await-termination-period` |
| Kafka listener container | до 15s | `spring.kafka.listener.shutdown-timeout` |
| **Total** | ≤ **60s** | `terminationGracePeriodSeconds` |

Spring выполняет phases частично параллельно — реальный `wall clock` обычно 30-40s. Бюджет 60s оставляет запас. Если суммарно не влезает — **сократить scope операций** (например, batch Kafka 100→20 сообщений), не увеличивать budget.

`graceful-shutdown/shutdown-is-observable` **Метрика `app_shutdown_duration_seconds` (gauge)** + структурный лог события начала и конца shutdown с временной меткой. Без этого первое падение под нагрузкой = «непонятно почему не успели». Имя метрики стандартное в команде.

```java
@EventListener(ContextClosedEvent.class)
void onShutdown() {
    long start = System.currentTimeMillis();
    log.info("graceful shutdown started, deadline={}s", terminationGracePeriodSeconds);
    // ... регистрация в Micrometer:
    Metrics.gauge("app_shutdown_duration_seconds", Tags.empty(),
        System.currentTimeMillis() - start, v -> (System.currentTimeMillis() - start) / 1000.0);
}
```

`graceful-shutdown/shutdown-is-observable` **Лог причины SIGTERM**: deploy/rolling/HPA/oom/manual. Spring сам не различает — но `kubectl describe pod` показывает событие. В логе сервиса записать только сам факт «получили SIGTERM, начинаем graceful». Дальнейший контекст поднимается из k8s-логов.

`graceful-shutdown/shutdown-is-observable` ❌ Логирование `Closing JPA EntityManagerFactory` / `HikariPool-1 - Shutdown initiated...` на ERROR-уровне. Это нормальные события — INFO. Иначе alert-канал зашумлён каждым деплоем.

---

## 9. Что **не** покрывает этот гайд

- **Startup ordering** (Liquibase до Kafka до accept-traffic) — это `spring-bootstrap/three-profiles-only`/`spring-bootstrap/service-starts-without-broker`/`spring-bootstrap/stub-publisher-is-overridable` из требований `spring-bootstrap/*`.
- **Health-checks дизайн** (что именно проверять в readiness) — частично в требованиях `observability/*` и `R-RES-HC-*`.
- **Saga / распределённые транзакции при отказе** — требования `distributed-patterns/*` (`R-DIST-COMP-*`).
- **Crash-recovery** (что делать при OOM/Kill -9 без graceful) — отдельная тема, реализуется через идемпотентность и replay (см. `R-SHUT-IDEM-*`).

---

## Чеклист подключения нового сервиса

- [ ] `server.shutdown: graceful` + `spring.lifecycle.timeout-per-shutdown-phase: 30s` в `application.yml`
- [ ] `management.endpoint.health.probes.enabled: true` + readiness/liveness state
- [ ] `spring.task.scheduling.shutdown.await-termination: true` + `await-termination-period: 25s`
- [ ] `spring.kafka.listener.shutdown-timeout: 20s` (если есть @KafkaListener)
- [ ] `setWaitForTasksToCompleteOnShutdown(true)` для всех custom `ThreadPoolTaskExecutor`-bean'ов
- [ ] k8s Deployment: `terminationGracePeriodSeconds: 60`
- [ ] k8s Deployment: `lifecycle.preStop` со sleep 10
- [ ] k8s readinessProbe → `/actuator/health/readiness`, livenessProbe → `/actuator/health/liveness`
- [ ] `maxSurge: 1, maxUnavailable: 0` в RollingUpdate strategy
- [ ] In-flight write-операции (HTTP, Kafka-handler, money-cascade) защищены `Idempotency-Key` или `processed_event`-дедупом
- [ ] Метрика `app_shutdown_duration_seconds` экспонирована
- [ ] Лог `graceful shutdown started/completed` на INFO
