---
name: ucp-py-payment-integration-design
lang: python
description: Спроектировать outbound-интеграцию с внешним платёжным провайдером по UCP (коды R-PAYINT-*) — идемпотентный флоу (register→charge→finalize, read-before-write по natural key, charge-if-not-terminal), advisory-lock на конкурентные оплаты заказа, единый anti-corruption status-mapper, разделение транспорт/бизнес-ошибок, reconciliation незавершённых через scheduler, Decimal+округление копеек. Триггеры — «интеграция с платёжным провайдером», «оплата по привязке», «эквайринг на FastAPI».
when_to_use: После ucp-py-pattern-design (есть Handler/порт) и ucp-py-sqlalchemy-design (репозиторий). Для сервисов, списывающих деньги через внешнего провайдера.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование платёжной интеграции (Python / FastAPI + httpx)

Ты проектируешь outbound-оплату согласно `backend/payment-integration/payment-integration-rules.md` (`R-PAYINT-*`)
и `backend/payment-integration/python/payment-integration-style-guide.md`. Оплата через провайдера —
at-least-once: корректность держится на идемпотентности, различении транспорт/бизнес-ошибок и едином доменном
статусе.

## Инструкции

1. **Прочитай** `.claude/docs/backend/payment-integration/payment-integration-rules.md` (`R-PAYINT-*`) и `.claude/docs/backend/payment-integration/python/payment-integration-style-guide.md`. Связанные: `backend/scheduler/scheduler-rules.md` (`R-JOB-*` — reconciliation/claim), `backend/distributed-patterns/distributed-patterns-rules.md` (`R-DIST-IDEM-*`), `backend/resilience/resilience-rules.md` (`R-RES-*`), `backend/error-handling/error-handling-rules.md` (`R-ERR-*`), `backend/integration` (структура out-adapter).

2. **Вход:** доменный заказ/платёж, провайдер (его вызовы register/status/charge), привязка/способ оплаты.

3. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Out-adapter провайдера** на `BaseHttpAdapter`, креды из `pydantic-settings`; транспорт/5xx → `provider_unavailable()`, бизнес-код → port-specific exception (`R-PAYINT-10`).
   - **Идемпотентный флоу:** `resolve_provider_order_id` (read-before-write по natural key, `R-PAYINT-2`), `execute_if_not_terminal` (charge только при не-терминальном статусе, `R-PAYINT-3`).
   - **Сериализация** конкурентных оплат заказа — advisory-lock методом репозитория (`R-PAYINT-4`).
   - **Единый `to_domain_status`-маппер** (одна точка интерпретации кодов, `R-PAYINT-5`); partial-update `exclude_none` (`R-PAYINT-7`); DTO провайдера не утекают (`R-PAYINT-X4`).
   - **Транспорт vs бизнес:** транспортная ошибка → не финализировать в FAIL, добрать позже (`R-PAYINT-8`); бизнес-отказ → терминал (`R-PAYINT-9`).
   - **Reconciliation:** фоновый тик (см. `ucp-py-scheduler-design`) добирает незавершённые (claim SKIP LOCKED + UTC TTL, `R-PAYINT-11/12`).
   - **Деньги:** `Decimal`, минорные единицы `ROUND_HALF_UP` (`R-PAYINT-13`).
   - **Наблюдаемость:** метрики/логи с идентификатором, без PAN/секретов (`R-PAYINT-14/15`).

4. **Самопроверка** + предложи `ucp-py-payment-integration-review`. Фоновый дозабор — `ucp-py-scheduler-design`; resilience-обвязку клиента — `ucp-py-resilience-design`.

## Антипаттерны, которые НЕ генерировать

- `register()` без `find_status` (`R-PAYINT-X1`); `charge()` без проверки статуса (`R-PAYINT-X2`).
- Дублирование интерпретации кодов провайдера (`R-PAYINT-X3`); утечка DTO провайдера в домен (`R-PAYINT-X4`).
- Финализация FAILED по таймауту/5xx (`R-PAYINT-X5`); единый `except` без различения транспорт/бизнес (`R-PAYINT-X6`).
- Только онлайн-путь без reconciliation (`R-PAYINT-X7`); `float`/`int(float*100)` для денег (`R-PAYINT-X8`).
- PAN/секреты в логах (`R-PAYINT-X9`); денежная операция без аудит-следа (`R-PAYINT-X10`).

После работы скилла — обязательно `ucp-py-payment-integration-review`.

$ARGUMENTS
