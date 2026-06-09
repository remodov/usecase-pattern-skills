# Resilience — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/resilience-style-guide.md` (Resilience4j + OkHttp/RestClient) и
> `python/resilience-style-guide.md` (httpx + tenacity + purgatory/aiobreaker + asyncio.Semaphore); открывай нужный точечно.
> Коды: `R-RES-<GROUP>-<N>` — обязательно, `R-RES-<GROUP>-X<N>` — запрещено. **Коды общие для всех языков** —
> меняется реализация (Resilience4j-аннотации ↔ декораторы/обёртки на async-методах out-adapter; semaphore-bulkhead общий по сути).

## 1. Где какая защита
**MUST:**
- **R-RES-WHERE-1.** Защита **outbound HTTP** к внешним системам (платежи, фискализация, страхование, любые сторонние API) — обязательна полным набором: timeout + circuit breaker + bulkhead + (опц.) retry. Без CB первый «slow burn» внешней системы расплескивается на весь пул воркеров сервиса.
- **R-RES-WHERE-2.** Защита **internal service-to-service** (вызовы между нашими микросервисами) — обязательны timeout + circuit breaker. bulkhead — по необходимости (если сервис тяжёлый или критичный).
- **R-RES-WHERE-3.** Защита **schedulers и outbox-relay** делается через **task-queue retry** (DB-driven, см. `R-RES-RE-5`), не через resilience-библиотека. resilience-библиотека покрывает in-memory транзиенты <5s; task-queue — durable retry для долгих отказов (>30s) и переживания рестарта сервиса.
- **R-RES-WHERE-4.** Защита **inbound (наш REST)** — это `rate limiter` и edge-уровень. По умолчанию — на API Gateway (Kong, Istio и т.п.), не в каждом сервисе. rate limiter на контроллерах допустим только если gateway недоступен (legacy-инсталляция).
**MUST NOT:**
- **R-RES-WHERE-X1.** resilience-библиотека вокруг локальных операций (репозиторий, SQL, in-memory вычисления). CB не имеет смысла — нет транзиентов «иногда работает, иногда нет», и любой failure на этом уровне — реальная ошибка, не отказ среды.

## 2. Per-system isolation
**MUST:**
- **R-RES-ISO-1.** На **каждую внешнюю систему** — отдельный HTTP-клиент **с собственным**:
- **R-RES-ISO-2.** Connection pool sizing — per-system: pool = `maxConcurrent` × 1.2 (запас на keep-alive idle). Total pool size всех систем ≤ размер пула БД / 2 (чтобы внешние клиенты не съели соединения с БД).
- **R-RES-ISO-3.** Имя bean'а и инстансов resilience-обёрток — **`<system>`** одинаково для CB / bulkhead / Retry: `sber`, `odnakassa`, `insurance`, `receipt`. Это позволяет адаптеру использовать одно имя в одно и то же имя системы для CB / bulkhead / retry.
**MUST NOT:**
- **R-RES-ISO-X1.** Один shared HTTP-клиент на несколько внешних систем. При зависании одной системы её застрявшие коннекты блокируют ресурсы других.
- **R-RES-ISO-X2.** Дефолтные настройки HTTP-клиент без явных pool/dispatcher без явного pool/dispatcher — приходит global defaults (200 idle), shared между всеми. Анти-паттерн.

## 3. Timeouts
**MUST:**
- **R-RES-TO-1.** Timeout hierarchy: `connectTimeout < readTimeout < callTimeout`.
- **R-RES-TO-2.** Timeouts конфигурируются per-system через типизированный per-system конфиг (`client.<system>`): Расхождения от типовых (`R-RES-TO-1`) — комментарием в yml с обоснованием.
- **R-RES-TO-3.** Если на эндпоинте есть `traceparent` (см. `R-HDR-4` REST guide) и TimeBudget — адаптер уважает оставшееся время. При `remainingBudget < callTimeout` — перехватчик запроса ставит client-side timeout = `min(callTimeout, remainingBudget - 100ms buffer)`.
**MUST NOT:**
- **R-RES-TO-X1.** Один глобальный HTTP-клиент без настроек без timeouts — дефолт ∞. Зависание = поток/таска навсегда.
- **R-RES-TO-X2.** `callTimeout < readTimeout` или `callTimeout < connectTimeout`. Внутреннее противоречие: первый сработает раньше, второй никогда.
- **R-RES-TO-X3.** `readTimeout > 60s` для синхронного вызова из HTTP-handler'а. Перевести в task-queue (`R-RES-WHERE-3`) или async-pattern (`R-ASYNC-1` REST guide).

## 4. Circuit Breaker
**MUST:**
- **R-RES-CB-1.** circuit breaker (per-system) — на **public-методе out-adapter**, который вызывает внешнюю систему. Не на сгенерированном клиенте (см. `R-RES-OAS-2`), не на handler'е, не на репозитории.
- **R-RES-CB-2.** Sliding window — **count-based**, не time-based (для outbound в БД-нагруженных сервисах). Размер окна и минимум вызовов до открытия — типовые значения в биндинге.
- **R-RES-CB-3.** Порог failure-rate открывает CB; для критичных систем (платежи) — ниже («лучше быстро открыть, чем тянуть»). Конкретные значения — в биндинге.
- **R-RES-CB-4.** В open-state — строгий fast-fail на заданную паузу (ни одного вызова), затем half-open с несколькими пробными вызовами: все успешны — closed, иначе — назад в open. Длительности/счётчики — в биндинге.
- **R-RES-CB-5.** Порог slow-call ниже timeout (ловит «медленно, но ещё не сломано») — срабатывает раньше самой ошибки по timeout. Значение — в биндинге.
- **R-RES-CB-6.** При open-state CB — выбрасывается исключение open-state CB. Адаптер маппит его в port-specific исключение (`...SystemUnavailable`), а handler — в `503 Service Unavailable` или `409 Conflict` (зависит от UC).
**MUST NOT:**
- **R-RES-CB-X1.** circuit breaker на репозитории, вызове репозитория, внутреннем сервисе. Локальный код не имеет «транзиентного» режима.
- **R-RES-CB-X2.** Custom CB на try/catch + ручной счётчик ошибок. Изобретать собственный — гарантированный bug-source. resilience-библиотека отлажена, интегрирована с метриками.
- **R-RES-CB-X3.** circuit breaker без `name` или с одним общим `name = "default"` для разных систем. Sber и OdnaKassa делят CB-state — открытие одной закрывает другую.

## 5. Retry
**MUST:**
- **R-RES-RE-1.** retry (per-system) допустим **только** при одном из условий: 1. Метод — read (GET-эквивалент): `findOrder`, `getStatus`. Чтение идемпотентно. 2. Команда выполняется с `Idempotency-Key` (см. `AUTH-19`). Внешняя система обязана сама дедуплицировать.
- **R-RES-RE-2.** Конфиг retry:
- **R-RES-RE-3.** Малое число попыток (типовое ~3, верхний предел ~5; включая первую). Больше — это уже task-queue. Точные значения — в биндинге.
- **R-RES-RE-4.** Граница in-memory retry vs task-queue:
- **R-RES-RE-5.** Task-queue retry — отдельный паттерн через таблицу `*_task` с полями `status`, `retry_count`, `next_attempt_at`, `last_error`. Scheduler периодически poll'ит по `status='IN_PROGRESS' AND next_attempt_at <= now()`. После N неудачных попыток — `status='FAILED'` + alert. Пример: `OrderConfirmationTask`, `ReceiptCreationTask`.
**MUST NOT:**
- **R-RES-RE-X1.** retry на write-методе без `Idempotency-Key`. На 5xx ответ может быть «не дошло» или «дошло и завершилось, ответ потерялся». Retry = двойная операция = двойной платёж.
- **R-RES-RE-X2.** retry на `4xx`-ответы. Это контрактные ошибки клиента — повтор не поможет.
- **R-RES-RE-X3.** retry без exponential backoff. Линейный retry бьёт пачкой подряд, удваивает нагрузку на и без того лежачую внешнюю систему.
- **R-RES-RE-X4.** legacy retry-механизм фреймворка для outbound. Legacy-механизм без интеграции с CB и bulkhead. Использовать resilience-библиотека.

## 6. bulkhead
**MUST:**
- **R-RES-BH-1.** bulkhead (per-system) — обязательный слой **отдельно** от connection pool. Connection pool ограничивает TCP-соединения; bulkhead — одновременные вызовы. Это два разных уровня защиты:
- **R-RES-BH-2.** Тип — **semaphore-based**, не thread-pool. Причина: thread-pool bulkhead создаёт собственный пул и теряет контекст (trace/security) без явного проброса. Semaphore работает в текущем thread.
- **R-RES-BH-3.** Лимит одновременных вызовов — ниже размера пула (bulkhead срабатывает **раньше** исчерпания пула); ожидание короткое/немедленный fail. Конкретные значения — в биндинге.
**MUST NOT:**
- **R-RES-BH-X1.** Thread-pool bulkhead (`type: THREADPOOL`) для outbound. Создаёт second pool, контекст (trace/security) теряется без ручного проброса. Semaphore-based достаточен.

## 7. Fallback
**MUST:**
- **R-RES-FB-1.** Fallback допустим в трёх случаях:
- **R-RES-FB-2.** Контракт fallback-метода: same return type, дополнительный last-параметр `Throwable` (или конкретное исключение). Сигнатура:
**MUST NOT:**
- **R-RES-FB-X1.** Fallback с `null` / `0` / пустой `Money` для money-операций. Возврат `Money.ZERO` за «не удалось списать» = бизнес-баг.
- **R-RES-FB-X2.** Fallback, который тихо проглатывает ошибку и возвращает «success». Клиент не узнает, что операция не выполнена, пока не наступит несоответствие в данных.
- **R-RES-FB-X3.** Fallback, делающий другой outbound-вызов (например, во второй провайдер платежей) без обёртки этого второго вызова в свой CB. Cascading failure.

## 8. Конфигурация
**MUST:**
- **R-RES-CFG-1.** Конфиг — декларативный (внешний), не программная сборка в коде. Это позволяет менять параметры через внешний config-store без redeploy.
- **R-RES-CFG-2.** Defaults — в секции `default`, переопределения — per-instance:
- **R-RES-CFG-3.** Имена instances — same as system: `sber`, `odnakassa`, `insurance`, `receipt`. Совпадают с именами beans (`R-RES-ISO-3`).
**MUST NOT:**
- **R-RES-CFG-X1.** Программная конфигурация в коде без причины. Скрытая конфигурация, не управляется через Cloud Config.

## 9. Связка с OpenAPI generator
**MUST:**
- **R-RES-OAS-1.** Аннотации circuit breaker / retry / bulkhead — на **public-методе out-adapter класса**, который оборачивает вызов сгенерированный клиент. Не на сгенерированный клиент, не в `executeCall<T>`-helper.
- **R-RES-OAS-2.** Для **новых сервисов** — генерация HTTP-клиента из OpenAPI-спеки. Это даёт:
- **R-RES-OAS-3.** OpenAPI-спецификация внешнего API хранится в `<system>-client-generator/src/main/resources/openapi/<system>.openapi.yaml`. Codegen в `build/generated/sources/openapi/`, не коммитится. Регенерация — на `compileJava`.
- **R-RES-OAS-4.** Между сгенерированный клиент и port-интерфейсом из `core/` — **обязательно** mapper (явный маппер), который переводит generated DTO в domain-команды. Generated DTO — детали транспорта, не доменные типы. Адаптер использует mapper, не возвращает generated DTO наверх.
**MUST NOT:**
- **R-RES-OAS-X1.** Аннотации на сгенерированный клиент (`<System>Api`). Регенерация затрёт.
- **R-RES-OAS-X2.** circuit breaker в `executeCall<T>` helper с backendName-строкой как параметром. Теряется compile-time проверка имени, ошибки на runtime («unknown circuit breaker «sbr»»).
- **R-RES-OAS-X3.** Возврат generated DTO из public-метода out-adapter (`PaymentPort.register` возвращает `SberRegisterResponse`). Доменный port должен возвращать domain-типы.

## 10. Health checks
**MUST:**
- **R-RES-HC-1.** На каждую внешнюю систему — health-индикатор на систему.
- **R-RES-HC-2.** Health-probe — **с кешем** (TTL — в биндинге). Не каждый health-запрос ходит во внешнюю систему. Реализация: кеш результата probe с TTL.
- **R-RES-HC-3.** Probe-метод — **light**: `GET /health` или `OPTIONS /` (если внешняя система не имеет health-endpoint), не реальный бизнес-вызов. Health-call не должен дёргать `register` или `confirmPayment`.
- **R-RES-HC-4.** Health отражается в `/health` (per-system). liveness — общий, readiness — включая внешние системы. Если Sber down — pod может вылететь из Service backend pool.
**MUST NOT:**
- **R-RES-HC-X1.** Sync-probe на каждый `/health` запрос (без кеша). При высокочастотных K8s probes (каждые 5s) это DDoS внешней системы силами наших же health-check'ов.
- **R-RES-HC-X2.** Health-probe, делающий business-операцию (`registerTestOrder`, `getRealTransactions`). Изменяет состояние, нагружает систему, плодит test-данные.

## 11. Async и polling
**MUST:**
- **R-RES-ASYNC-1.** Если внешняя система требует polling (как страхование из bus-tickets — «отправили запрос → ждём результат»), polling реализуется через **task-queue**, не через блокирующий sleep в синхронном handler'е:
- **R-RES-ASYNC-2.** В sync-методе адаптера допустим блокирующий sleep только если total wait `<2s` (короткий transient retry с фиксированным backoff). Иначе — task-queue.
- **R-RES-ASYNC-3.** Для async outbound (async-возврат из adapter) — time-limiter (per-system) обязателен. Отдельный механизм (retry/bulkhead/CB не покрывают timeout async-вызова сами).
**MUST NOT:**
- **R-RES-ASYNC-X1.** блокирующий sleep в цикле в цикле в синхронном handler'е, опрашивающем внешнюю систему. Блокирует worker-thread на N×iterations секунд. При нагрузке исчерпает пул воркеров за минуты.
- **R-RES-ASYNC-X2.** Любой блокирующий sleep > 5s — это запах «должно было быть task-queue».

## 12. Observability
**MUST:**
- **R-RES-OBS-1.** метрики resilience — через систему метрик. Автоматически экспортирует:
- **R-RES-OBS-2.** OTel-spans на adapter-методах — атрибут `circuit_breaker.state` (current state в момент вызова) и `external.system` (имя системы). Это даёт связку «slow trace → CB был half-open».
- **R-RES-OBS-3.** Логирование — структурированное (см. observability-style-guide, в планах). При каждом state-transition CB — лог уровня WARN с system, prev_state, new_state, failure_rate. Не на каждый успешный call.
**MUST NOT:**
- **R-RES-OBS-X1.** Отключение resilience-метрик без причины. Без них SRE не увидит «у нас CB Sber стабильно half-open» до прода.

## 13. Антипаттерны
