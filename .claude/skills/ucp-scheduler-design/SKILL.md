---
name: ucp-scheduler-design
description: Спроектировать фоновую обработку Spring Boot-сервиса по требованиям `scheduler/*` — очередь заданий на SKIP LOCKED, тик через @Scheduled под ShedLock, идемпотентность, повторы с паузой, возврат зависших.
when_to_use: Триггеры — «фоновая задача», «периодический прогон», «очередь заданий», «шедулер». После ucp-pattern-design и ucp-jooq-design.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Фоновая обработка — проектирование (Java / Spring Boot)

Ты проектируешь фоновую работу так, чтобы она проходила `ucp-scheduler-review` без находок.

## Инструкции

1. **Прочитай** `.claude/docs/backend/scheduler/spec.md` и `references/java/implementation.md`. Связанные: `backend/pg-runtime/spec.md` (`SKIP LOCKED`, advisory lock), `backend/distributed-patterns/spec.md` (идемпотентность), `backend/resilience/spec.md` (повторы), `backend/observability/spec.md` (метрики).

2. **Определи ось задачи** (`scheduler/mechanism-matches-work`): очередь единиц работы, периодический тик, работа из внешнего события или побочный эффект после ответа. Не смешивай оси в один механизм. Денежная и критичная работа — только очередь или транзакционное задание.

3. **Спроектируй по оси:**
   - **Очередь:** таблица заданий (состояние, попытка, `next_attempt_at`, `claimed_at`, частичный индекс), запрос захвата `forUpdate().skipLocked()`, обработчик как UseCase-хендлер с транзакцией на нём.
   - **Тик:** класс `*Processing` в `scheduler-in-adapter`: `@Scheduled(fixedRateString, initialDelayString, scheduler)` + `@SchedulerLock(name, lockAtLeastFor = interval, lockAtMostFor)`; тик только диспатчит команду в `try/catch`; свойства — `@Validated @ConfigurationProperties` на базе общего `ProcessingProperties`, свой `TaskScheduler` с graceful shutdown; `ShedLockConfig` с `usingDbTime()` и выключателем `scheduling.enabled`. `fixedDelay` / `cron` — когда обещано «не чаще, чем». Без блокировки — только тик, запускающий атомарный захват идемпотентной работы, и только явным исключением в `ScheduledMethodsAreGuardedTest`.
   - **Идемпотентность:** проверка состояния до действия, естественный ключ во внешней системе.
   - **Надёжность:** предел попыток, растущая пауза, состояние разбора, возврат захватов старше порога.
   - **Время:** `Instant`/`OffsetDateTime`, `timestamptz`, источник времени сервиса (`DateTimeUtil` или `Clock`-бин), не `now()`.
   - **Наблюдаемость:** длина очереди, возраст самой старой единицы, число повторов, оповещение по возрасту.

4. **Самопроверка** по требованиям и предложи `ucp-scheduler-review`.

## Чего не генерировать

- `@Scheduled` без блокировки на нескольких репликах (`scheduler/single-source-of-tick`).
- Захват «прочитал, потом обновил» вместо одного запроса (`scheduler/work-unit-claimed-atomically`).
- Побочный эффект после ответа для денег и периодики (`scheduler/mechanism-matches-work`).
- `LocalDateTime.now()` и константы расписания в коде (`scheduler/time-is-timezone-aware`, `job-parameters-are-typed-config`).
