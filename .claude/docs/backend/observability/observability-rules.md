# Observability — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/observability-style-guide.md` (Micrometer/Logback/OTel-starter) и
> `python/observability-style-guide.md` (structlog/prometheus-client/OTel-SDK); открывай нужный точечно.
> Коды: `R-OBS-<GROUP>-<N>` — обязательно, `R-OBS-<GROUP>-X<N>` — запрещено. **Коды общие для всех языков** —
> меняется инструментарий (Micrometer ↔ prometheus-client, MDC ↔ contextvars/structlog), три столпа (logs/metrics/traces) одни.

## 1. Logging
**MUST:**
- **R-OBS-LOG-1.** **Structured JSON в проде.** Дев-окружение — текстовый логирование-pattern для читаемости; прод — JSON через `logstash-logback-encoder` или фреймворк 3 JSON-энкодер. JSON парсится Loki/ELK/Datadog без regex.
- **R-OBS-LOG-2.** **логгер (DI) через кодоген-аннотации** на классе. Никаких `LoggerFactory.getLogger(MyClass.class)` руками — лишний boilerplate.
- **R-OBS-LOG-3.** **Параметризованные логи** через `{}`-плейсхолдеры: Не string-concat (`"Order created: " + order.getId()`) — выполняет toString даже если уровень disabled.
- **R-OBS-LOG-4.** **Уровни логов:**
- **R-OBS-LOG-5.** **контекст запроса поля** в каждой записи: `traceId`, `spanId` (auto через OTel), `requestId` (из `X-Request-Id` header или generated), `userId` (из JWT через filter). Эти поля автоматически попадают в JSON через контекст запроса-encoder.
- **R-OBS-LOG-6.** **Логи на границах**:
**MUST NOT:**
- **R-OBS-LOG-X1.** **PII в логах.** Email, phone, ФИО, адрес, паспорт, токены, пароли — `R-OBS-LOG-X1` **критическое нарушение**. Маскировать (`***@***.com`) или вообще не логировать. См. `AUTH-16`.
- **R-OBS-LOG-X2.** **`System.out.println` / `e.printStackTrace()` / `System.err.println`.** Не попадают в structured pipeline, теряют контекст запроса, не алертируются.
- **R-OBS-LOG-X3.** **String-concat в log-message** при низком уровне (DEBUG/TRACE). `log.debug("Heavy: " + bigObject.serialize())` выполняет `serialize()` всегда. Используй `log.debug("Heavy: {}", bigObject)` — Slf4j ленив.
- **R-OBS-LOG-X4.** **`log.error(...)` без stack trace** для exception. `log.error("Failed: " + e.getMessage())` теряет stack — используй 2-arg `log.error("Failed: {}", context, e)`.
- **R-OBS-LOG-X5.** **Полный request body в логах** для money/PII-эндпоинтов. Логируй только идентификаторы (`orderId`), не payload.
- **R-OBS-LOG-X6.** **INFO-логи на каждый HTTP-запрос**. Если все handler'ы пишут «Handling request X», выйдет шум. Access-log делает это отдельно с правильным форматированием.

## 2. Metrics
**MUST:**
- **R-OBS-MTR-1.** система метрик — обязательная зависимость через `spring-boot-starter-management` + `io.micrometer:micrometer-registry-prometheus`. Endpoint management-эндпоинт exposed для scraping.
- **R-OBS-MTR-2.** **Стандартные dimensions (tags)** на каждой метрике:
- **R-OBS-MTR-3.** **RED method для HTTP** (auto через management-эндпоинты):
- **R-OBS-MTR-4.** **USE method для resources** (auto через фреймворк):
- **R-OBS-MTR-5.** **Custom business metrics** через `MeterRegistry`:
- **R-OBS-MTR-6.** **Имена метрик** — snake_case, единицы в имени (`payment_duration_seconds`, не просто `payment_duration`). Соглашение Prometheus.
- **R-OBS-MTR-7.** **Tags — низкая cardinality.** Допустимо: `status_code` (3 значения: `success`/`client_error`/`server_error` — не само число), `endpoint` (десятки путей), `payment_method` (CARD/SBP/CRYPTO). Запрещено: `user_id`, `order_id`, `request_id` — миллионы значений = OOM в Prometheus.
**MUST NOT:**
- **R-OBS-MTR-X1.** **High-cardinality tags** (`user_id`, `request_id`, `order_id` как value). Prometheus хранит time series per unique combination tags — миллион ID = миллион time series = OOM.
- **R-OBS-MTR-X2.** **Не-стандартизованные dimensions** (один service пишет `app=foo`, другой `service_name=foo`). Стандарт `service`/`env`/`version` через `management.metrics.tags.*`.
- **R-OBS-MTR-X3.** **`micrometer-core` без registry**. Без Prometheus registry метрики собираются in-memory и теряются на рестарте.
- **R-OBS-MTR-X4.** **management-эндпоинт без auth** в публичной сети. Internal scraper-only через network policy / VPN.

## 3. Tracing
**MUST:**
- **R-OBS-TRC-1.** **OpenTelemetry автоинструментация** через `opentelemetry-spring-boot-starter` (фреймворк). Авто-spans для:
- **R-OBS-TRC-2.** **`traceparent` propagation** (W3C Trace Context, см. `R-HDR-4`). фреймворк + OTel автоматически:
- **R-OBS-TRC-3.** **Manual spans** для use case handlers и значимых операций:
- **R-OBS-TRC-4.** **Span attributes** — business context, не PII:
- **R-OBS-TRC-5.** **Sampling**: 1–10% в проде по умолчанию, **100% для error-traces** (tail-based sampling если поддерживается collector'ом). Это даёт достаточный набор «нормальных» traces и не пропускает ошибки.
- **R-OBS-TRC-6.** **`trace-id` в логах** через контекст запроса. OTel автоматически подставляет `traceId`/`spanId` через OTel-аппендер логов в логирование. Это даёт связку «лог-запись → distributed trace».
**MUST NOT:**
- **R-OBS-TRC-X1.** **Sampling 100% в проде** для среднего/высоконагруженного сервиса. Tracing storage (Tempo, Jaeger) переполняется за часы; стоимость зашкаливает.
- **R-OBS-TRC-X2.** **PII в span attributes** (`customer.email`, `order.detail` с PII). Tracing-данные часто менее защищены чем main DB.
- **R-OBS-TRC-X3.** **Manual span без `try-finally` / try-with-resources**. Span не закроется → утечка spans в коллекторе, искажение traces.
- **R-OBS-TRC-X4.** **Trace context разрывается на async-задача без проброс контекста**. См. `R-OBS-CTX-3`.

## 4. Health checks
**MUST:**
- **R-OBS-HC-1.** management с **разделением liveness и readiness**:
- **R-OBS-HC-2.** **Custom HealthIndicator** для каждой критичной внешней системы (см. `R-RES-HC-1`):
- **R-OBS-HC-3.** **management-эндпоинт** содержит:
**MUST NOT:**
- **R-OBS-HC-X1.** **Business-state в health check** (`if (orderCount > N) return DOWN`). Health — техническое состояние процесса. Бизнес-метрики — отдельные SLO.
- **R-OBS-HC-X2.** **Liveness зависит от внешних систем** (DB/Redis). При временной недоступности K8s рестартует pod, не помогает — после restart те же системы будут недоступны → loop. Только readiness.
- **R-OBS-HC-X3.** **Health-probe делает business-операцию** (`registerTestOrder`). См. `R-RES-HC-X2` — ddos самих себя через health-checks.

## 5. Конфигурация
**MUST:**
- **R-OBS-CFG-1.** **Management port отдельный** от business port: Это позволяет: (а) ограничить /management на сетевом уровне (только internal); (б) не блокировать business-traffic при management-нагрузке.
- **R-OBS-CFG-2.** **Exposed endpoints** — только нужные: Дефолт фреймворк — только management-эндпоинт и management-эндпоинт. Production-grade — explicit list.
- **R-OBS-CFG-3.** **фреймворк defaults** для metrics:
- **R-OBS-CFG-4.** **логирование-конфиг логирования** с двумя профилями:
**MUST NOT:**
- **R-OBS-CFG-X1.** **Exposing management-эндпоинт, management-эндпоинт, management-эндпоинт** в проде без authentication. `env` показывает все configs включая возможные секреты в plain (если они попали туда мимо Vault).
- **R-OBS-CFG-X2.** **Один port для business + management** в проде. Невозможно отделить scraping-traffic от business-traffic.
- **R-OBS-CFG-X3.** **`management.endpoints.web.exposure.include: '*'`** в проде. Открывает `env`, `beans`, `mappings`, `loggers` — security risk.

## 6. Context propagation (контекст запроса)
**MUST:**
- **R-OBS-CTX-1.** **Request-ID filter** populates контекст запроса на каждом входящем HTTP request:
- **R-OBS-CTX-2.** **`traceId` / `spanId` в контекст запроса** — автоматически через OTel логирование appender (`io.opentelemetry.instrumentation.logback-mdc-1.0`). Не добавлять руками.
- **R-OBS-CTX-3.** **Async/CompletableFuture** — пропагация контекста через проброс контекста в задачи:
- **R-OBS-CTX-4.** **`userId` в контекст запроса** — populates после JWT-валидации в Security filter chain:
**MUST NOT:**
- **R-OBS-CTX-X1.** **контекст запроса без `контекст запроса.clear()` в finally**. Утечка context в thread pool — следующий request unrelated user видит чужой `userId` в логах = compliance incident.
- **R-OBS-CTX-X2.** **`контекст запроса.put` в произвольных местах кода** (handler, service). Только в filter / interceptor. Иначе `контекст запроса.clear` логика не очевидна.
- **R-OBS-CTX-X3.** **Async без проброс контекста** для CompletableFuture / async-задачи — traces разрываются на границе thread.

## 7. SLO и алерты
**MUST:**
- **R-OBS-SLO-1.** **Каждый critical-endpoint** имеет SLO:
- **R-OBS-SLO-2.** **Multi-window multi-burn-rate alerts** (см. [Google SRE Workbook](https://sre.google/workbook/alerting-on-slos/)):
- **R-OBS-SLO-3.** **Alert на error budget exhaustion** — отдельный алерт когда бюджет ошибок остался < 10%. Это команда «нужно срочно фокус на reliability, не на features».
- **R-OBS-SLO-4.** **Alerts отдельные от SLO**:
**MUST NOT:**
- **R-OBS-SLO-X1.** **Alert на каждый ERROR** в логах. Alert fatigue → команда игнорирует. Фильтруй: ERROR класса `ServiceUnavailableException` повторяющийся 100 раз в минуту = один алерт; единичные `ValidationException` = не алерт.
- **R-OBS-SLO-X2.** **SLO без error budget**. Если 100% target — нечем оперировать; 99.9% даёт 43 минуты downtime в месяц как бюджет.
- **R-OBS-SLO-X3.** **Алерты без runbook'ов**. PagerDuty в 3 ночи без инструкции «что делать» = эскалация без действия.

## 8. Антипаттерны
