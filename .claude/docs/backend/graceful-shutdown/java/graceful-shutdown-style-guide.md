# Graceful Shutdown Style Guide

Правила корректного завершения Spring Boot-сервиса по Use Case Pattern. Каждое правило имеет код `R-SHUT-*` — скилл `ucp-shutdown-review` цитирует их в findings.

Базовый принцип (`R-SHUT-1`): **получив SIGTERM, сервис обязан завершиться без потерь**. Активные HTTP-запросы дожимаются до 200/503; in-flight Kafka-batch коммитится; @Scheduled-таски доводятся до конца текущей итерации; БД-транзакции либо коммитятся, либо откатываются. Pod, который умирает «как есть», создаёт каскад инцидентов: 502 у клиента → retry → дубль (если операция не идемпотентна) → расходы.

`R-SHUT-2` **Total budget — 60 секунд** (`terminationGracePeriodSeconds: 60` в k8s). После этого SIGKILL — никто не ждёт. Из этого budget раскладывается всё ниже: preStop sleep + Spring graceful timeout + Kafka commit + БД-tx. Если суммарно не помещается — переразбейте операции, не увеличивайте budget. Долгое завершение = долгий rolling deploy = окно с двумя версиями кода против одной БД.

`R-SHUT-3` **`ApplicationAvailability` — единственный источник правды о состоянии**. Не свои `AtomicBoolean`-ы, не статические переменные. Health-эндпоинты (`/actuator/health/readiness`, `/actuator/health/liveness`) опираются на него; SIGTERM-listener переключает `readinessState` в `OUT_OF_SERVICE`; k8s endpoints-controller убирает pod из service-роутинга. Без этого balancer продолжает слать трафик в умирающий pod до самого SIGKILL.

---

## 1. JVM/Spring конфигурация — `R-SHUT-CFG-*`

`R-SHUT-CFG-1` **`server.shutdown=graceful`** в `application.yml` — обязательно. Без этого Spring Boot убивает Tomcat/Netty `forceShutdown()` сразу на SIGTERM, активные HTTP-запросы получают `IOException`/`502` на клиенте.

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

`R-SHUT-CFG-2` **`spring.lifecycle.timeout-per-shutdown-phase: 30s`** — максимальное ожидание per-phase Spring-shutdown. Дефолт `30s`, явно прописывается чтобы видеть. Меньше 20s — мало для дрейна Tomcat thread-pool под нагрузкой; больше 45s — рискуете попасть в SIGKILL внутри `terminationGracePeriodSeconds: 60` (`R-SHUT-2`).

`R-SHUT-CFG-3` **Hook на SIGTERM ставит `ApplicationAvailability.readinessState = OUT_OF_SERVICE`** в первую очередь. Это делает Spring Boot 2.3+ автоматически (`GracefulShutdown.AvailabilityState`-listener), но проверять — обязательно. После переключения health/readiness начинает возвращать `503`, k8s через 1-2 секунды убирает pod из endpoints.

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

`R-SHUT-CFG-4` **`management.endpoint.health.probes.enabled=true`** + `management.health.livenessstate.enabled=true` + `management.health.readinessstate.enabled=true`. Spring Boot экспонирует `/actuator/health/liveness` и `/actuator/health/readiness` отдельно — k8s probe-конфиг ссылается на них.

`R-SHUT-CFG-X1` ❌ Свой `AtomicBoolean shuttingDown` или `volatile boolean isShuttingDown` вместо `ApplicationAvailability`. Не интегрируется с health-эндпоинтами, k8s об этом не узнает.

---

## 2. HTTP drain — `R-SHUT-HTTP-*`

`R-SHUT-HTTP-1` **In-flight HTTP-запросы дожимаются до response**, новые принимаются ровно до момента переключения readiness в `OUT_OF_SERVICE`. Spring Boot graceful делает это автоматически — но требует `R-SHUT-CFG-1`.

`R-SHUT-HTTP-2` **`preStop` hook со `sleep 10`** в k8s-манифесте. Это **обязательно** даже при правильном Spring graceful — потому что k8s запускает SIGTERM **до того**, как kube-proxy на других нодах распространит «убрать pod из endpoints». Без `preStop` 5-15 секунд нового трафика приходит на pod, который уже начал shutdown.

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

`R-SHUT-HTTP-3` **Долгие синхронные эндпоинты (>10 сек)** должны иметь `@Async` + `Idempotency-Key` (`AUTH-19`) либо async-pattern «202 Accepted + polling». Иначе при shutdown они либо съедают весь graceful timeout, либо обрываются на полпути.

`R-SHUT-HTTP-X1` ❌ `Tomcat`/`Netty` worker-threads с дефолтным `awaitTermination(0, TimeUnit.SECONDS)` в кастомных `WebServerCustomizer`. Аннулирует graceful.

---

## 3. Kafka shutdown — `R-SHUT-KFK-*`

`R-SHUT-KFK-1` **`@KafkaListener`-консьюмер дожимает текущий batch и коммитит offset перед остановкой.** Spring Kafka делает это через `ConcurrentMessageListenerContainer.stop(timeout)` — настраивается через `spring.kafka.listener.shutdown-timeout: 20s`.

```yaml
spring:
  kafka:
    listener:
      shutdown-timeout: 20s            # max ожидание per-container
      ack-mode: BATCH                  # commit явный, не auto
```

`R-SHUT-KFK-2` **Listener-метод не должен запускать долгий cascade.** Если внутри `@KafkaListener`-метода идёт chain HTTP-вызовов с retry'ями на 30 секунд — он не уложится в `shutdown-timeout`. Cascade выносится в отдельный async-flow либо в outbox.

`R-SHUT-KFK-3` **`ack-mode: BATCH` или `RECORD` явно**, не `MANUAL_IMMEDIATE` без обоснования. `BATCH` — оптимально: один commit на batch, при shutdown гарантирует, что текущий batch либо закоммичен полностью, либо ни одна запись не считается обработанной (replay при рестарте — идемпотентность защищает, см. `R-SHUT-IDEM-1`).

`R-SHUT-KFK-4` **Producer.flush() на shutdown** — Spring Boot делает автоматически через `KafkaTemplate.destroy()`. Если используется raw `KafkaProducer` — обязательно `producer.close(Duration.ofSeconds(15))`.

`R-SHUT-KFK-X1` ❌ `enable.auto.commit: true`. При shutdown часть offset'ов закоммичена auto-thread'ом до фактической обработки записи — replay невозможен, потеря сообщений. Уже запрещено `BS-14`-связанными правилами, тут — повторение для контекста.

---

## 4. БД и persistence — `R-SHUT-DB-*`

`R-SHUT-DB-1` **HikariCP закрывается после Spring shutdown phases.** Дефолтное поведение Spring Boot правильное — `DataSource.close()` идёт в последней фазе. Не переопределяй `@PreDestroy` на DataSource — может закрыть pool до того, как @Scheduled закончил последний tx.

`R-SHUT-DB-2` **Активные транзакции** на момент SIGTERM:
- HTTP-handler в transaction → graceful HTTP дожимает до commit/rollback (`R-SHUT-HTTP-1`).
- @Scheduled-метод в transaction → ждать завершения текущей итерации (`R-SHUT-SCHED-1`).
- @KafkaListener в transaction → batch завершается, commit (`R-SHUT-KFK-1`).
- @Async в transaction — отдельная боль, см. `R-SHUT-SCHED-2`.

`R-SHUT-DB-3` **Liquibase / Flyway не запускаются на shutdown.** Это про startup, упомянуто чтобы исключить миф «надо что-то очистить при выходе».

`R-SHUT-DB-X1` ❌ `DataSource.close()` или `pool.shutdown()` в кастомном `@PreDestroy` сервиса с `@Order(LOWEST_PRECEDENCE)`. Гарантированно закроет pool до того, как все scheduled-таски доделаются.

---

## 5. Scheduled / @Async / outbox — `R-SHUT-SCHED-*`

`R-SHUT-SCHED-1` **`@Scheduled`-методы завершают текущую итерацию, не начинают новую.** Spring Boot управляет этим через `TaskScheduler.shutdown()` — параметры:

```yaml
spring:
  task:
    scheduling:
      shutdown:
        await-termination: true
        await-termination-period: 25s
```

`await-termination: true` — обязательно, иначе scheduler грохает таски `interrupt()`-ом мгновенно. `25s` — должно умещаться в `R-SHUT-2` budget (60с total) с учётом preStop (10с) + graceful (30с) + Kafka (20с) — суммарно 85с! Поэтому **нельзя** все timeouts держать на максимуме одновременно. Реалистичное распределение бюджета — отдельная таблица в §8.

`R-SHUT-SCHED-2` **`@Async`-таски с долгим cascade** опасны: при SIGTERM ExecutorService по умолчанию делает `interrupt()` через `awaitTermination(timeout)`. Любой `Thread.sleep` или blocking call внутри — `InterruptedException`. Конфигурируем `ThreadPoolTaskExecutor` с `setAwaitTerminationSeconds` явно:

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

`R-SHUT-SCHED-3` **Outbox-relay** (типовой паттерн UCP) на SIGTERM:
- Завершает текущий batch (его в БД через `FOR UPDATE SKIP LOCKED` уже нельзя «потерять» — это атомарно).
- Не начинает новый batch.
- При следующем старте — `SKIP LOCKED` уже не блокирует, новый relay подхватывает.

Это работает «само» при `R-SHUT-SCHED-1` + jOOQ-pattern (`R-JOOQ-LCK-*`). Главное — не запускать relay-цикл с `while(true)` без проверки `availability.isReadinessAccepting()`.

`R-SHUT-SCHED-X1` ❌ `setWaitForTasksToCompleteOnShutdown(false)` без обоснования. Все таски убиты, частичные изменения в БД — без rollback в общем случае (commit мог пройти, side-effect-вызов внешней системы — нет → нерпо unconsistent state).

---

## 6. Kubernetes — `R-SHUT-K8S-*`

`R-SHUT-K8S-1` **`terminationGracePeriodSeconds: 60`** — обязательно прописано в Deployment, не дефолт-30. Внутрь не входит preStop sleep — он отдельный бюджет.

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

`R-SHUT-K8S-2` **`readinessProbe`** настроен на `/actuator/health/readiness`, `livenessProbe` на `/actuator/health/liveness`. Не путать — `liveness` падение перезапускает pod, `readiness` падение убирает из endpoints без рестарта. На shutdown нужен именно readiness=503.

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

`R-SHUT-K8S-3` **`maxSurge: 1, maxUnavailable: 0`** на rolling deploy production-сервисов. Гарантирует, что новый pod уже принимает трафик до того, как старый начал shutdown — нулевой downtime.

`R-SHUT-K8S-X1` ❌ Отсутствие `preStop`. Без него 5-15 секунд после SIGTERM kube-proxy ещё льёт трафик — все эти запросы получат 502, даже при идеально настроенном Spring graceful.

`R-SHUT-K8S-X2` ❌ `terminationGracePeriodSeconds: 30` (k8s default) с `R-SHUT-CFG-2: 30s` Spring graceful timeout. preStop (10s) уже не помещается — pod уйдёт в SIGKILL посередине дрейна.

---

## 7. Идемпотентность in-flight операций — `R-SHUT-IDEM-*`

`R-SHUT-IDEM-1` **In-flight операции, которые SIGTERM может прервать, обязаны быть retry-safe.** Это сшивка с `AUTH-19`: write-операции с `Idempotency-Key`, money-cascade в task-queue (`R-RES-ASYNC-*`), Kafka-handler через outbox + dedup-таблица (`processed_event` на event_id).

Граничные случаи:
- HTTP POST без `Idempotency-Key` + shutdown посередине → клиент ретрается → дубль. Защита: контракт требует `Idempotency-Key` (`AUTH-19`).
- Kafka-listener закоммитил offset, но не завершил side-effect → replay создаёт дубль side-effect-а. Защита: `processed_event(event_id)`-таблица в той же tx, что и side-effect.
- Outbox-relay отправил в Kafka, но не пометил row `published=true` → следующий relay отправит повторно. Защита: либо двух-фаза (`pending → publishing → published`), либо `processed_event`-дедуп на consumer-стороне.

`R-SHUT-IDEM-X1` ❌ Money-операция без `Idempotency-Key` в адаптере, защищаемая `@Retry(name = "...")`. При SIGTERM в момент retry первый вызов прошёл (списал деньги), retry в новом pod-е спишет ещё раз. Уже запрещено `R-RES-RE-X1` — здесь напоминание контекста.

---

## 8. Бюджеты и observability — `R-SHUT-OBS-*`

`R-SHUT-OBS-1` **Реалистичный бюджет shutdown** (cumulative, не параллельный):

| Этап | Длительность | Параметр |
|---|---|---|
| preStop sleep (kube-proxy distribution) | 10s | `lifecycle.preStop` |
| Spring graceful (HTTP drain) | до 25s | `spring.lifecycle.timeout-per-shutdown-phase` |
| TaskScheduler / @Async | до 20s | `spring.task.scheduling.shutdown.await-termination-period` |
| Kafka listener container | до 15s | `spring.kafka.listener.shutdown-timeout` |
| **Total** | ≤ **60s** | `terminationGracePeriodSeconds` |

Spring выполняет phases частично параллельно — реальный `wall clock` обычно 30-40s. Бюджет 60s оставляет запас. Если суммарно не влезает — **сократить scope операций** (например, batch Kafka 100→20 сообщений), не увеличивать budget.

`R-SHUT-OBS-2` **Метрика `app_shutdown_duration_seconds` (gauge)** + структурный лог события начала и конца shutdown с временной меткой. Без этого первое падение под нагрузкой = «непонятно почему не успели». Имя метрики стандартное в команде.

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

`R-SHUT-OBS-3` **Лог причины SIGTERM**: deploy/rolling/HPA/oom/manual. Spring сам не различает — но `kubectl describe pod` показывает событие. В логе сервиса записать только сам факт «получили SIGTERM, начинаем graceful». Дальнейший контекст поднимается из k8s-логов.

`R-SHUT-OBS-X1` ❌ Логирование `Closing JPA EntityManagerFactory` / `HikariPool-1 - Shutdown initiated...` на ERROR-уровне. Это нормальные события — INFO. Иначе alert-канал зашумлён каждым деплоем.

---

## 9. Что **не** покрывает этот гайд

- **Startup ordering** (Liquibase до Kafka до accept-traffic) — это `BS-2`/`BS-13`/`BS-15` из bootstrap-style-guide.
- **Health-checks дизайн** (что именно проверять в readiness) — частично в observability-style-guide и `R-RES-HC-*`.
- **Saga / распределённые транзакции при отказе** — distributed-patterns-style-guide (`R-DIST-COMP-*`).
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
