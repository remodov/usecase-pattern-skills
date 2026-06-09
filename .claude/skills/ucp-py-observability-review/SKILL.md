---
name: ucp-py-observability-review
lang: python
description: Ревью наблюдаемости FastAPI-сервиса (Python) по UCP (коды R-OBS-*) — structlog JSON + contextvars, prometheus-client (RED/USE, низкая cardinality), OpenTelemetry, health live/ready, management-порт, request-id middleware, SLO.
when_to_use: Изменения в logging-конфиге, метриках, OTel-setup, middleware, health-эндпоинтах, management-конфиге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Observability (Python / structlog + prometheus-client + OTel)

Ты ревьюишь наблюдаемость на соответствие **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Python-реализации** `backend/observability/python/observability-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/observability/observability-rules.md`** + **`backend/observability/python/observability-style-guide.md`**.
- Парные: `backend/python/python-bootstrap/...` (`PYBOOT-14`), `resilience` (health внешних), `auth-patterns` (`AUTH-16` PII).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-OBS-LOG-X1`, `R-OBS-MTR-X1`), не префикс.

2. **Скоп.** Logging-конфиг (structlog), метрики (prometheus-client), OTel-setup, middleware (request-id/contextvars), health-эндпоинты, management-конфиг; `git diff`.

3. **Прогон.**
   - **Logging (`R-OBS-LOG-*`):** structlog JSON в проде, kwargs-поля, contextvars trace/request/user. PII в логах → `R-OBS-LOG-X1` (критично). `print`/`traceback.print_exc` → `R-OBS-LOG-X2`. `log.error` без `exc_info` → `R-OBS-LOG-X4`. Полный body для money/PII → `R-OBS-LOG-X5`. INFO на каждый запрос → `R-OBS-LOG-X6`.
   - **Metrics (`R-OBS-MTR-*`):** prometheus-client, labels `service`/`env`/`version`, snake_case+единица. High-cardinality label (`user_id`/`order_id`) → `R-OBS-MTR-X1`. Нестандартные labels → `R-OBS-MTR-X2`. `/metrics` без защиты → `R-OBS-MTR-X4`.
   - **Tracing (`R-OBS-TRC-*`):** OTel автоинструментация + manual span через context-manager (без → `R-OBS-TRC-X3`); sampling 1–10%+errors (100% в проде → `R-OBS-TRC-X1`); PII в атрибутах → `R-OBS-TRC-X2`; разрыв в `run_in_executor` без `copy_context` → `R-OBS-TRC-X4`.
   - **Health (`R-OBS-HC-*`):** раздельные live/ready; бизнес-состояние → `R-OBS-HC-X1`; liveness зависит от DB/Redis → `R-OBS-HC-X2`; probe бизнес-операцией → `R-OBS-HC-X3`.
   - **Config (`R-OBS-CFG-*`):** отдельный management-порт (один порт → `R-OBS-CFG-X2`); debug-эндпоинты без auth → `R-OBS-CFG-X1`; всё подряд exposed → `R-OBS-CFG-X3`.
   - **Context (`R-OBS-CTX-*`):** request-id/user_id через contextvars в middleware с очисткой (без очистки → `R-OBS-CTX-X1` — критично, утечка между запросами); `bind` вне middleware → `R-OBS-CTX-X2`; thread-offload без `copy_context` → `R-OBS-CTX-X3`.
   - **SLO (`R-OBS-SLO-*`):** SLO+error budget+multi-window alerts+runbook. Alert на каждый ERROR → `R-OBS-SLO-X1`. SLO без бюджета → `R-OBS-SLO-X2`. Без runbook → `R-OBS-SLO-X3`.

4. **Cross-check:** PII-гигиена — `ucp-py-auth-review` (`AUTH-16`); health внешних систем — `ucp-py-resilience-review`; wiring middleware/lifespan — `ucp-py-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — PII в логах/спанах (`R-OBS-LOG-X1`/`R-OBS-TRC-X2`), contextvars без очистки между запросами (`R-OBS-CTX-X1`), high-cardinality labels (`R-OBS-MTR-X1`), liveness зависит от внешних (`R-OBS-HC-X2`), debug-эндпоинты без auth (`R-OBS-CFG-X1`).
   - **Предупреждение** — `print`/без `exc_info` (`R-OBS-LOG-X2/X4`), sampling 100% в проде (`R-OBS-TRC-X1`), manual span без context-manager (`R-OBS-TRC-X3`), один порт business+management (`R-OBS-CFG-X2`), alert на каждый ERROR (`R-OBS-SLO-X1`).
   - **Замечание** — INFO на каждый запрос (`R-OBS-LOG-X6`), нестандартные labels (`R-OBS-MTR-X2`), нет runbook (`R-OBS-SLO-X3`).

## Что не входит

- PII-классификация/маскирование политики — `ucp-py-auth-review`. Health внешних систем (TTL/probe) — `ucp-py-resilience-review`.
- Wiring middleware/management в bootstrap — `ucp-py-bootstrap-review`.

$ARGUMENTS
