---
name: ucp-py-observability-design
lang: python
description: Спроектировать наблюдаемость FastAPI-сервиса (Python) по UCP (коды R-OBS-*) — structlog с contextvars без PII, prometheus-client RED/USE-метрики, OpenTelemetry-трейсинг с sampling, health live/ready, management-порт, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг», «structlog», «prometheus на питоне». При настройке observability.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Observability — проектирование (Python / structlog + prometheus-client + OTel)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Python-реализации** `backend/observability/python/observability-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/python/python-bootstrap/...` (`PYBOOT-14` health/wiring), `resilience` (health-check внешних), `auth-patterns` (PII-гигиена `AUTH-16`).

2. **Logging** (`R-OBS-LOG-*`): structlog JSON в проде / текст локально; kwargs-поля; `trace_id`/`request_id`/`user_id` через bound contextvars; нет PII; `exc_info`/`log.exception` для ошибок; нет `print`.

3. **Metrics** (`R-OBS-MTR-*`): prometheus-client (`prometheus-fastapi-instrumentator`), `/metrics`; labels `service`/`env`/`version`; RED/USE; бизнес-`Counter`/`Histogram`; snake_case+единица; **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): OTel автоинструментация (fastapi/sqlalchemy/httpx/aiokafka); manual span через `with tracer.start_as_current_span(...)`; атрибуты без PII; sampling 1–10% + 100% errors; `trace_id` в логах.

5. **Health** (`R-OBS-HC-*`): раздельные `/health/live` + `/health/ready`; custom-check внешних с TTL-кешем; `/info`.

6. **Config/Context** (`R-OBS-CFG/CTX-*`): отдельный management-порт/sub-app, explicit endpoints; request-id middleware с `bind_contextvars` + очисткой в `finally`; contextvars проходят через `await` (TaskDecorator не нужен), для thread-offload — `copy_context()`.

7. **SLO** (`R-OBS-SLO-*`): SLO + error budget + multi-window burn-rate alerts + runbook. Самопроверка (§8) + предложи `ucp-py-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`R-OBS-LOG-X1`/`R-OBS-TRC-X2`); `print`/`traceback.print_exc` (`R-OBS-LOG-X2`); `log.error` без `exc_info` (`R-OBS-LOG-X4`).
- High-cardinality labels (`R-OBS-MTR-X1`); нестандартные labels (`R-OBS-MTR-X2`); `/metrics` без защиты (`R-OBS-MTR-X4`).
- Sampling 100% в проде (`R-OBS-TRC-X1`); manual span без context-manager (`R-OBS-TRC-X3`); liveness зависит от DB/Redis (`R-OBS-HC-X2`); бизнес-состояние в health (`R-OBS-HC-X1`).
- contextvars без очистки между запросами (`R-OBS-CTX-X1`); `bind_contextvars` вне middleware (`R-OBS-CTX-X2`); один порт business+management (`R-OBS-CFG-X2`); alert на каждый ERROR (`R-OBS-SLO-X1`).

После работы скилла — обязательно `ucp-py-observability-review`.

$ARGUMENTS
