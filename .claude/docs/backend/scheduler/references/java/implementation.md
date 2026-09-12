# Background Jobs & Scheduling — реализация на Java (Spring Boot / jOOQ)

Реализация требований `../../spec.md` (`scheduler/*`, коды `R-JOB-*`). Требование говорит, что обязано
быть верно; здесь — как это выглядит на Spring-стеке. Стек по умолчанию: Spring Boot, jOOQ, PostgreSQL,
`@Scheduled` для тика, таблица заданий для очереди.

## Решение по умолчанию (две оси)

Фоновая работа делится на две независимые оси, и смешивать их в один механизм нельзя:

- **Ось A — очередь единиц работы (что делать):** таблица заданий с `FOR UPDATE SKIP LOCKED` — дефолт.
- **Ось B — периодический тик (когда запускать):** `@Scheduled` под ShedLock (`@SchedulerLock`,
  JDBC-провайдер) — дефолт для нескольких реплик. В эталоне так устроены все 14 тиков.

Kafka-очередь берётся, когда работа приходит извне событием, а не порождается своим сервисом.
`@Async` и `ApplicationEventPublisher` после ответа — только для потерь, которые допустимы.

## 1. Выбор механизма (`scheduler/mechanism-matches-work`)

| Природа работы | Решение по умолчанию | Когда |
|---|---|---|
| Очередь единиц работы | таблица заданий + `SKIP LOCKED` | есть PostgreSQL, нужна согласованность задания и данных |
| Периодика | `@Scheduled` + ShedLock | любой периодический прогон на нескольких репликах |
| Работа из внешнего события | `@KafkaListener` + `processed_event` | инициатор — чужой сервис |
| Побочный эффект после ответа | `@TransactionalEventListener(AFTER_COMMIT)` | письмо, инвалидация кеша; потеря допустима |

- **PREFER** `fixedRate` + `initialDelay` под `@SchedulerLock(lockAtLeastFor = interval)`: темп не зависит
  от длительности прогона, а серия догоняющих запусков после длинного прогона схлопывается до одного —
  блокировка держится минимум интервал от захвата, следующие запуски в этом окне пропускаются. `fixedRate`
  без `lockAtLeastFor` копит запуски.
- **PREFER** `fixedDelay` или `cron`, когда обещано «не чаще, чем» — рассылка, отчёт: там даже один
  догоняющий запуск нарушает обещание.
- **PREFER** ShedLock, не advisory lock: `@SchedulerLock` виден ArchUnit, и гейт `ScheduledMethodsAreGuardedTest`
  проверяется; `pg_try_advisory_xact_lock` — вызов внутри метода, тест его не видит.
- **AVOID** Quartz с кластерным хранилищем ради одного расписания: он приносит свою схему и своё время.
- **AVOID** `@Async` для денег и периодики — это ось B, а не A (`scheduler/mechanism-matches-work`).

## 2. Идемпотентность (`scheduler/job-is-idempotent`, `scheduler/read-before-write-by-natural-key`)

```java
@Transactional
public void process(TaskId id) {
    Task task = tasks.findClaimed(id).orElseThrow();

    if (task.isTerminal()) {
        return;
    }

    provider.findByNaturalKey(task.orderId())
        .ifPresentOrElse(task::attachExisting, () -> provider.create(task.toRequest()));

    tasks.markDone(task);
}
```

- **PREFER** естественный ключ операции (`orderId` + тип) как ключ идемпотентности во внешней системе.
- **AVOID** «повтор не случится, у нас гарантированная доставка»: перезапуск и восстановление зависших
  захватов дают повтор всегда.

## 3. Антидубли на репликах (`scheduler/work-unit-claimed-atomically`, `scheduler/single-source-of-tick`)

Захват единицы работы — одним запросом, без «прочитал, потом обновил»:

```java
List<TaskRecord> claim(int batch) {
    return dsl.select(TASK.asterisk())
        .from(TASK)
        .where(TASK.STATUS.eq(NEW).and(TASK.NEXT_ATTEMPT_AT.le(now())))
        .orderBy(TASK.NEXT_ATTEMPT_AT)
        .limit(batch)
        .forUpdate().skipLocked()
        .fetchInto(TaskRecord.class);
}
```

Периодический тик — под ShedLock, чтобы он был один на кластер. Форма из эталона — класс `*Processing`
в `scheduler-in-adapter`: тик только диспатчит команду, единицы работы захватывает handler в core:

```java
@Component
@Slf4j
@RequiredArgsConstructor
public class OutboxDomainEventProcessing {

    private final UseCaseDispatcher dispatcher;
    private final OutboxDomainEventProperties properties;

    @Scheduled(
        fixedRateString = "${outbox-domain-event-processing.interval:PT1S}",
        initialDelayString = "${outbox-domain-event-processing.initial-delay:PT5S}",
        scheduler = "outboxDomainEventScheduler"
    )
    @SchedulerLock(
        name = "SendOutboxDomainEventsProcessing",
        lockAtLeastFor = "${outbox-domain-event-processing.interval:PT1S}",
        lockAtMostFor = "${outbox-domain-event-processing.lock-at-most-for:PT2M}"
    )
    public void processSend() {
        try {
            Integer processed = dispatcher.dispatch(SendOutboxDomainEventsCommand.builder()
                .batchSize(properties.getBatchSize())
                .reclaimAfter(properties.getReclaimAfter())
                .build());
            if (processed != null && processed > 0) {
                log.debug("Published {} entity events", processed);
            }
        } catch (Exception exception) {
            log.error("Failed to publish entity events", exception);
        }
    }
}
```

Включение — одной конфигурацией на адаптер:

```java
@Configuration
@EnableScheduling
@EnableSchedulerLock(defaultLockAtMostFor = "PT5M")
@ConditionalOnProperty(value = "scheduling.enabled", havingValue = "true", matchIfMissing = true)
public class ShedLockConfig {

    @Bean
    public LockProvider lockProvider(DataSource dataSource) {
        return new JdbcTemplateLockProvider(JdbcTemplateLockProvider.Configuration.builder()
            .withJdbcTemplate(new JdbcTemplate(dataSource))
            .usingDbTime()
            .build());
    }
}
```

- **PREFER** `lockAtMostFor` с запасом над худшим прогоном и `defaultLockAtMostFor` в `@EnableSchedulerLock`:
  упавший узел отпускает блокировку сам.
- **PREFER** `usingDbTime()`: часы реплик в блокировке не участвуют.
- **PREFER** `scheduling.enabled=false` для тестов и профилей без расписания — все тики выключаются разом.
- **PREFER** свой `TaskScheduler` на процессинг (`ThreadPoolTaskScheduler` с `poolSize`, `threadNamePrefix`,
  `setWaitForTasksToCompleteOnShutdown(true)`, `setAwaitTerminationSeconds`): долгий тик не блокирует соседей,
  graceful shutdown дожидается прогона.
- `try/catch` с `log.error` вокруг диспатча — граница для `@Scheduled` (`error-handling`): исключение из тика
  не должно убить расписание.
- Тик без блокировки допустим только там, где он лишь запускает атомарный захват идемпотентных единиц работы
  (`SKIP LOCKED`, ось A): три реплики берут три разные пачки — множится тик, а не работа. Такое исключение
  вносится явно в `ScheduledMethodsAreGuardedTest` с обоснованием, а на ревью проверяются внешняя нагрузка
  (pull из партнёрского API множится на число реплик) и `poolSize × реплики`.
- **AVOID** `@Scheduled` без блокировки, если тик сам выполняет работу — рассылка уйдёт клиенту столько раз,
  сколько экземпляров сервиса.

## 4. Надёжность (`scheduler/bounded-retries-then-parking`, `scheduler/stuck-claims-are-recovered`, `scheduler/transient-versus-business-errors`)

- Повторы ограничены числом попыток и растущей паузой: `next_attempt_at = now() + base * 2^attempt`.
- Исчерпавшее попытки задание уходит в состояние разбора, а не повторяется бесконечно.
- Захват старше порога возвращается в работу отдельным запросом по `claimed_at`.
- Временная ошибка (сеть, тайм-аут, отказ предохранителя) повторяется; бизнес-отказ — конечный,
  повтор не изменит результата.

## 5. Время и настройки (`scheduler/time-is-timezone-aware`, `scheduler/job-parameters-are-typed-config`)

- Время в задании — `Instant`, колонка `timestamptz`, текущее время из источника времени сервиса (`DateTimeUtil` или `Clock`-бин).
- Расписание, размер пакета, пороги повторов — `@ConfigurationProperties` с `@Validated`, не константы в коде.
  Общий базовый класс `ProcessingProperties` (`batchSize`, `poolSize`, `threadNamePrefix`,
  `awaitTerminationSeconds`) + поля процессинга (`reclaimAfter`, `lockAtMostFor`); префикс —
  `<name>-processing`, значения — из `application.yml` через `${ENV:default}`. `@Validated` обязателен:
  `@Positive` на `batchSize` и `poolSize`, `@NotNull` на интервалах — неверное значение роняет старт, а не
  молча делает тик пустым.
- **AVOID** `LocalDateTime.now()` в задании: расписание сдвинется на переходе времени.

## 6. Наблюдаемость (`scheduler/job-is-observable`)

- Метрики: длина очереди, возраст самой старой единицы, число повторов, время прогона.
- В журнал — идентификатор единицы работы и попытка; персональных данных нет.
- Оповещение — на рост возраста очереди, а не на единичный отказ.

## Чеклист подключения (Java / Spring Boot)

1. Таблица заданий: `id`, `status`, `attempt`, `next_attempt_at`, `claimed_at`, полезная нагрузка,
   частичный индекс по `status` и `next_attempt_at`.
2. Репозиторий с запросом захвата `forUpdate().skipLocked()`.
3. Обработчик единицы работы — обычный UseCase-хендлер, транзакция на нём.
4. `*Processing` в `scheduler-in-adapter`: `@Scheduled(fixedRate, initialDelay, scheduler)` +
   `@SchedulerLock(lockAtLeastFor = interval, lockAtMostFor)`, `@Validated @ConfigurationProperties`
   на базе `ProcessingProperties`, свой `TaskScheduler`; `ShedLockConfig` с `usingDbTime()` и `scheduling.enabled`.
5. Возврат зависших захватов отдельным прогоном (`reclaimAfter`).
6. Метрики очереди и оповещение по возрасту.
7. Тест: две параллельные попытки захвата не берут одну единицу дважды.
8. `ScheduledMethodsAreGuardedTest`: каждый `@Scheduled` под `@SchedulerLock`; исключения — явно, с обоснованием.
