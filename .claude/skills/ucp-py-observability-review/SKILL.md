---
name: ucp-py-observability-review
lang: python
description: Ревью наблюдаемости FastAPI-сервиса (Python) по UCP (требования observability/*) — structlog JSON + contextvars, prometheus-client (RED/USE, низкая cardinality), OpenTelemetry, health live/ready, management-порт, request-id middleware, SLO.
when_to_use: Изменения в logging-конфиге, метриках, OTel-setup, middleware, health-эндпоинтах, management-конфиге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Observability (Python / structlog + prometheus-client + OTel)

Ты ревьюишь наблюдаемость на соответствие **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Python-реализации** `backend/observability/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/observability/spec.md`** + **`backend/observability/references/python/implementation.md`**.
- Парные: `backend/python/python-bootstrap/...` (`python-bootstrap/observability-configured-in-factory`), `resilience` (health внешних), `auth-patterns` (`auth-patterns/no-pii-in-logs-and-events` PII).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`observability/no-pii-in-logs`, `observability/low-cardinality-labels`), не префикс.

2. **Скоп.** Logging-конфиг (structlog), метрики (prometheus-client), OTel-setup, middleware (request-id/contextvars), health-эндпоинты, management-конфиг; `git diff`.

3. **Прогон.**
   - **Logging (`R-OBS-LOG-*`):** structlog JSON в проде, kwargs-поля, contextvars trace/request/user. PII в логах → `observability/no-pii-in-logs` (критично). `print`/`traceback.print_exc` → `observability/no-direct-stdout-logging`. `log.error` без `exc_info` → `observability/parameterized-log-messages`. Полный body для money/PII → `observability/no-pii-in-logs`. INFO на каждый запрос → `observability/log-levels-and-noise`.
   - **Metrics (`R-OBS-MTR-*`):** prometheus-client, labels `service`/`env`/`version`, snake_case+единица. High-cardinality label (`user_id`/`order_id`) → `observability/low-cardinality-labels`. Нестандартные labels → `observability/standard-metric-dimensions`. `/metrics` без защиты → `observability/management-endpoints-restricted`.
   - **Tracing (`R-OBS-TRC-*`):** OTel автоинструментация + manual span через context-manager (без → `observability/manual-spans-are-closed`); sampling 1–10%+errors (100% в проде → `observability/sampling-strategy`); PII в атрибутах → `observability/manual-spans-are-closed`; разрыв в `run_in_executor` без `copy_context` → `observability/context-propagated-to-async`.
   - **Health (`R-OBS-HC-*`):** раздельные live/ready; бизнес-состояние → `observability/health-check-is-technical`; liveness зависит от DB/Redis → `observability/liveness-and-readiness-split`; probe бизнес-операцией → `observability/health-check-is-technical`.
   - **Config (`R-OBS-CFG-*`):** отдельный management-порт (один порт → `observability/separate-management-port`); debug-эндпоинты без auth → `observability/management-endpoints-restricted`; всё подряд exposed → `observability/management-endpoints-restricted`.
   - **Context (`R-OBS-CTX-*`):** request-id/user_id через contextvars в middleware с очисткой (без очистки → `observability/context-set-at-edge-and-cleared` — критично, утечка между запросами); `bind` вне middleware → `observability/context-set-at-edge-and-cleared`; thread-offload без `copy_context` → `observability/context-propagated-to-async`.
   - **SLO (`R-OBS-SLO-*`):** SLO+error budget+multi-window alerts+runbook. Alert на каждый ERROR → `observability/burn-rate-alerting`. SLO без бюджета → `observability/slo-with-error-budget`. Без runbook → `observability/alerts-have-runbooks`.

4. **Cross-check:** PII-гигиена — `ucp-py-auth-review` (`auth-patterns/no-pii-in-logs-and-events`); health внешних систем — `ucp-py-resilience-review`; wiring middleware/lifespan — `ucp-py-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — PII в логах/спанах (`observability/no-pii-in-logs`/`observability/manual-spans-are-closed`), contextvars без очистки между запросами (`observability/context-set-at-edge-and-cleared`), high-cardinality labels (`observability/low-cardinality-labels`), liveness зависит от внешних (`observability/liveness-and-readiness-split`), debug-эндпоинты без auth (`observability/management-endpoints-restricted`).
   - **Предупреждение** — `print`/без `exc_info` (`R-OBS-LOG-X2/X4`), sampling 100% в проде (`observability/sampling-strategy`), manual span без context-manager (`observability/manual-spans-are-closed`), один порт business+management (`observability/separate-management-port`), alert на каждый ERROR (`observability/burn-rate-alerting`).
   - **Замечание** — INFO на каждый запрос (`observability/log-levels-and-noise`), нестандартные labels (`observability/standard-metric-dimensions`), нет runbook (`observability/alerts-have-runbooks`).

## Что не входит

- PII-классификация/маскирование политики — `ucp-py-auth-review`. Health внешних систем (TTL/probe) — `ucp-py-resilience-review`.
- Wiring middleware/management в bootstrap — `ucp-py-bootstrap-review`.

$ARGUMENTS
