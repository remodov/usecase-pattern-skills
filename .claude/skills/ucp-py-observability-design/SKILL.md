---
name: ucp-py-observability-design
lang: python
description: Спроектировать наблюдаемость FastAPI-сервиса (Python) по UCP — structlog с contextvars без PII, prometheus-client RED/USE-метрики, OpenTelemetry-трейсинг с sampling, health live/ready, management-порт, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг», «structlog», «prometheus на питоне». При настройке observability.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Observability — проектирование (Python / structlog + prometheus-client + OTel)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Python-реализации** `backend/observability/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `backend/python/python-bootstrap/...` (`python-bootstrap/observability-configured-in-factory` health/wiring), `resilience` (health-check внешних), `auth-patterns` (PII-гигиена `auth-patterns/no-pii-in-logs-and-events`).

2. **Logging** (`R-OBS-LOG-*`): structlog JSON в проде / текст локально; kwargs-поля; `trace_id`/`request_id`/`user_id` через bound contextvars; нет PII; `exc_info`/`log.exception` для ошибок; нет `print`.

3. **Metrics** (`R-OBS-MTR-*`): prometheus-client (`prometheus-fastapi-instrumentator`), `/metrics`; labels `service`/`env`/`version`; RED/USE; бизнес-`Counter`/`Histogram`; snake_case+единица; **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): OTel автоинструментация (fastapi/sqlalchemy/httpx/aiokafka); manual span через `with tracer.start_as_current_span(...)`; атрибуты без PII; sampling 1–10% + 100% errors; `trace_id` в логах.

5. **Health** (`R-OBS-HC-*`): раздельные `/health/live` + `/health/ready`; custom-check внешних с TTL-кешем; `/info`.

6. **Config/Context** (`R-OBS-CFG/CTX-*`): отдельный management-порт/sub-app, explicit endpoints; request-id middleware с `bind_contextvars` + очисткой в `finally`; contextvars проходят через `await` (TaskDecorator не нужен), для thread-offload — `copy_context()`.

7. **SLO** (`R-OBS-SLO-*`): SLO + error budget + multi-window burn-rate alerts + runbook. Самопроверка (§8) + предложи `ucp-py-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`observability/no-pii-in-logs`/`observability/manual-spans-are-closed`); `print`/`traceback.print_exc` (`observability/no-direct-stdout-logging`); `log.error` без `exc_info` (`observability/parameterized-log-messages`).
- High-cardinality labels (`observability/low-cardinality-labels`); нестандартные labels (`observability/standard-metric-dimensions`); `/metrics` без защиты (`observability/management-endpoints-restricted`).
- Sampling 100% в проде (`observability/sampling-strategy`); manual span без context-manager (`observability/manual-spans-are-closed`); liveness зависит от DB/Redis (`observability/liveness-and-readiness-split`); бизнес-состояние в health (`observability/health-check-is-technical`).
- contextvars без очистки между запросами (`observability/context-set-at-edge-and-cleared`); `bind_contextvars` вне middleware (`observability/context-set-at-edge-and-cleared`); один порт business+management (`observability/separate-management-port`); alert на каждый ERROR (`observability/burn-rate-alerting`).

После работы скилла — обязательно `ucp-py-observability-review`.

$ARGUMENTS
