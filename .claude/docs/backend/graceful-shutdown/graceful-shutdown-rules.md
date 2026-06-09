# Graceful Shutdown — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/graceful-shutdown-style-guide.md` (Spring/Tomcat/HikariCP) и
> `python/graceful-shutdown-style-guide.md` (uvicorn + lifespan + asyncio); k8s-часть нейтральна. Открывай нужный точечно.
> Коды: `R-SHUT-<GROUP>-<N>` — обязательно, `R-SHUT-<GROUP>-X<N>` — антипаттерн (запрещено). **Коды общие для всех
> языков** — меняется механизм (Spring graceful + `ApplicationAvailability` ↔ uvicorn graceful + lifespan + readiness-флаг).

**MUST:**
- **R-SHUT-1.** Получив SIGTERM, сервис обязан завершиться без потерь: HTTP дожимаются, Kafka-batch коммитится, фоновые задачи доводят итерацию, БД-tx commit/rollback. Pod, умерший «как есть», даёт каскад 502 → retry → дубль.
- **R-SHUT-2.** Total budget — 60 сек (`terminationGracePeriodSeconds: 60`); внутри раскладываются preStop + graceful веб-сервера + Kafka + БД-tx. Не помещается — переразбей операции, не увеличивай budget.
- **R-SHUT-3.** `ApplicationAvailability` — единственный источник правды о состоянии (не свои `AtomicBoolean`); SIGTERM-listener переключает `readinessState` в `OUT_OF_SERVICE`, k8s убирает pod из роутинга.

## 1. Runtime/конфигурация
**MUST:**
- **R-SHUT-CFG-1.** graceful-shutdown веб-сервера обязательно — иначе фреймворк убивает web-сервер `forceShutdown()` сразу, активные HTTP → 502.
- **R-SHUT-CFG-2.** таймаут фазы shutdown задан явно (~30s) (< 20s мало для дрейна, > 45s рискует SIGKILL внутри 60с).
- **R-SHUT-CFG-3.** Hook на SIGTERM ставит `readinessState = OUT_OF_SERVICE` первым (фреймворк делает авто, но проверять); health/readiness → 503, k8s убирает pod из endpoints.
- **R-SHUT-CFG-4.** раздельные liveness/readiness probes включены — отдельные /health/{live,ready}.

**MUST NOT:**
- **R-SHUT-CFG-X1.** Свой `AtomicBoolean shuttingDown` вместо readiness-состояние приложения — не интегрируется с health, k8s не узнает.

## 2. HTTP drain
**MUST:**
- **R-SHUT-HTTP-1.** In-flight HTTP дожимаются до response, новые принимаются до переключения readiness (фреймворк graceful авто при `R-SHUT-CFG-1`).
- **R-SHUT-HTTP-2.** `preStop` hook со `sleep 10` обязателен даже при фреймворк graceful — k8s шлёт SIGTERM до распространения «убрать из endpoints»; без него 5–15с нового трафика на умирающий pod. 10с типично, до 20 на больших кластерах.
- **R-SHUT-HTTP-3.** Долгие синхронные эндпоинты (>10с) — async-задача + `Idempotency-Key` (`AUTH-19`) либо «202 Accepted + polling».

**MUST NOT:**
- **R-SHUT-HTTP-X1.** web-сервер worker-threads с `awaitTermination(0, SECONDS)` в кастомном `WebServerCustomizer` — аннулирует graceful.

## 3. Kafka shutdown
**MUST:**
- **R-SHUT-KFK-1.** consumer дожимает batch и коммитит offset перед остановкой (таймаут остановки consumer ~20s).
- **R-SHUT-KFK-2.** Listener-метод не запускает долгий cascade (chain HTTP с retry на 30с не уложится) — cascade в async-flow или outbox.
- **R-SHUT-KFK-3.** `ack-mode: BATCH` или `RECORD` явно, не `MANUAL_IMMEDIATE` без обоснования; BATCH — один commit на batch, replay защищён идемпотентностью.
- **R-SHUT-KFK-4.** flush + close producer на shutdown.

**MUST NOT:**
- **R-SHUT-KFK-X1.** `enable.auto.commit: true` — часть offset закоммичена до обработки, потеря сообщений (уже запрещено `BS-14`-правилами).

## 4. БД и persistence
**MUST:**
- **R-SHUT-DB-1.** пул соединений БД закрывается после фреймворк shutdown phases (дефолт правильный); не переопределять shutdown-хук на DataSource.
- **R-SHUT-DB-2.** Активные транзакции на SIGTERM завершаются через свой канал: HTTP-handler (graceful HTTP), scheduler (текущая итерация), consumer (batch commit), async-задача (см. `R-SHUT-SCHED-2`).
- **R-SHUT-DB-3.** Миграции схемы не запускаются на shutdown (это startup; нет «очистки при выходе»).

**MUST NOT:**
- **R-SHUT-DB-X1.** ручное закрытие пула БД в shutdown-хуке с низшим приоритетом — закроет pool до завершения scheduled-тасок.

## 5. Фоновые задачи / async / outbox
**MUST:**
- **R-SHUT-SCHED-1.** планировщик завершают текущую итерацию, не начинают новую (ожидание завершения задач ~25s); без этого scheduler грохает `interrupt()`-ом.
- **R-SHUT-SCHED-2.** async-задача с долгим cascade — конфигурировать пул задач с ожиданием завершения на shutdown (иначе принудительное прерывание).
- **R-SHUT-SCHED-3.** Outbox-relay на SIGTERM завершает текущий batch (атомарно через `FOR UPDATE SKIP LOCKED`), не начинает новый; relay-цикл проверяет `availability.isReadinessAccepting()`, не `while(true)`.

**MUST NOT:**
- **R-SHUT-SCHED-X1.** отключение ожидания завершения задач без обоснования — таски убиты, частичные изменения без rollback (inconsistent state).

## 6. Kubernetes
**MUST:**
- **R-SHUT-K8S-1.** `terminationGracePeriodSeconds: 60` явно в Deployment (не дефолт-30); preStop sleep — отдельный бюджет сверху.
- **R-SHUT-K8S-2.** `readinessProbe` → /health/ready, `livenessProbe` → /health/live; на shutdown нужен readiness=503 (liveness-падение перезапускает pod).
- **R-SHUT-K8S-3.** `maxSurge: 1, maxUnavailable: 0` на rolling deploy — новый pod принимает трафик до shutdown старого (нулевой downtime).

**MUST NOT:**
- **R-SHUT-K8S-X1.** Отсутствие `preStop` — 5–15с после SIGTERM kube-proxy ещё льёт трафик → 502.
- **R-SHUT-K8S-X2.** `terminationGracePeriodSeconds: 30` (default) с 30s фреймворк graceful — preStop не помещается, SIGKILL посередине дрейна.

## 7. Идемпотентность in-flight операций
**MUST:**
- **R-SHUT-IDEM-1.** In-flight операции, которые SIGTERM может прервать, обязаны быть retry-safe (сшивка с `AUTH-19`): write с `Idempotency-Key`, money-cascade в task-queue, Kafka-handler через outbox + `processed_event(event_id)`-дедуп.

**MUST NOT:**
- **R-SHUT-IDEM-X1.** Money-операция без `Idempotency-Key` под retry — SIGTERM в момент retry → новый pod спишет ещё раз (уже запрещено `R-RES-RE-X1`).

## 8. Бюджеты и observability
**MUST:**
- **R-SHUT-OBS-1.** Реалистичный cumulative-бюджет: preStop 10s + фреймворк graceful ≤25s + TaskScheduler/async-задачи ≤20s + Kafka ≤15s ≤ 60s; не влезает — сократить scope (batch 100→20), не увеличивать budget.
- **R-SHUT-OBS-2.** Метрика `app_shutdown_duration_seconds` (gauge) + структурный лог начала/конца shutdown.
- **R-SHUT-OBS-3.** Лог факта SIGTERM («получили SIGTERM, начинаем graceful»); причину (deploy/HPA/oom/manual) поднимать из k8s-логов.

**MUST NOT:**
- **R-SHUT-OBS-X1.** Логирование нормального закрытия persistence/пула БД на ERROR — это нормальные INFO-события, иначе alert-канал зашумлён каждым деплоем.
