---
name: ucp-py-payment-integration-design
lang: python
description: Спроектировать outbound-интеграцию с платёжным провайдером по UCP (требования payment-integration/*) — идемпотентный флоу register→charge→finalize, advisory-lock на конкурентные оплаты, status-mapper, Decimal.
when_to_use: После ucp-py-pattern-design и ucp-py-sqlalchemy-design. Для сервисов, списывающих деньги через внешнего провайдера.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование платёжной интеграции (Python / FastAPI + httpx)

Ты проектируешь outbound-оплату согласно `backend/payment-integration/spec.md` (`R-PAYINT-*`)
и `backend/payment-integration/references/python/implementation.md`. Оплата через провайдера —
at-least-once: корректность держится на идемпотентности, различении транспорт/бизнес-ошибок и едином доменном
статусе.

## Инструкции

1. **Прочитай** `.claude/docs/backend/payment-integration/spec.md` (`R-PAYINT-*`) и `.claude/docs/backend/payment-integration/references/python/implementation.md`. Связанные: `backend/scheduler/spec.md` (`R-JOB-*` — reconciliation/claim), `backend/distributed-patterns/spec.md` (`R-DIST-IDEM-*`), `backend/resilience/spec.md` (`R-RES-*`), `backend/error-handling/spec.md` (`R-ERR-*`), `backend/integration` (структура out-adapter).

2. **Вход:** доменный заказ/платёж, провайдер (его вызовы register/status/charge), привязка/способ оплаты.

3. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Out-adapter провайдера** на `BaseHttpAdapter`, креды из `pydantic-settings`; транспорт/5xx → `provider_unavailable()`, бизнес-код → port-specific exception (`payment-integration/transport-and-business-errors-differ`).
   - **Идемпотентный флоу:** `resolve_provider_order_id` (read-before-write по natural key, `payment-integration/read-before-write`), `execute_if_not_terminal` (charge только при не-терминальном статусе, `payment-integration/act-only-if-not-terminal`).
   - **Сериализация** конкурентных оплат заказа — advisory-lock методом репозитория (`payment-integration/concurrent-attempts-serialized`).
   - **Единый `to_domain_status`-маппер** (одна точка интерпретации кодов, `payment-integration/single-status-mapper`); partial-update `exclude_none` (`payment-integration/partial-update-of-domain-record`); DTO провайдера не утекают (`payment-integration/domain-values-outside-adapter`).
   - **Транспорт vs бизнес:** транспортная ошибка → не финализировать в FAIL, добрать позже (`payment-integration/transport-error-keeps-operation-retryable`); бизнес-отказ → терминал (`payment-integration/business-decline-is-terminal`).
   - **Reconciliation:** фоновый тик (см. `ucp-py-scheduler-design`) добирает незавершённые (claim SKIP LOCKED + UTC TTL, `R-PAYINT-11/12`).
   - **Деньги:** `Decimal`, минорные единицы `ROUND_HALF_UP` (`payment-integration/money-is-decimal`).
   - **Наблюдаемость:** метрики/логи с идентификатором, без PAN/секретов (`R-PAYINT-14/15`).

4. **Самопроверка** + предложи `ucp-py-payment-integration-review`. Фоновый дозабор — `ucp-py-scheduler-design`; resilience-обвязку клиента — `ucp-py-resilience-design`.

## Антипаттерны, которые НЕ генерировать

- `register()` без `find_status` (`payment-integration/read-before-write`); `charge()` без проверки статуса (`payment-integration/act-only-if-not-terminal`).
- Дублирование интерпретации кодов провайдера (`payment-integration/single-status-mapper`); утечка DTO провайдера в домен (`payment-integration/domain-values-outside-adapter`).
- Финализация FAILED по таймауту/5xx (`payment-integration/transport-error-keeps-operation-retryable`); единый `except` без различения транспорт/бизнес (`payment-integration/transport-and-business-errors-differ`).
- Только онлайн-путь без reconciliation (`payment-integration/reconciliation-pass`); `float`/`int(float*100)` для денег (`payment-integration/money-is-decimal`).
- PAN/секреты в логах (`payment-integration/no-sensitive-payment-data-in-logs`); денежная операция без аудит-следа (`payment-integration/money-operations-leave-trace`).

После работы скилла — обязательно `ucp-py-payment-integration-review`.

$ARGUMENTS
