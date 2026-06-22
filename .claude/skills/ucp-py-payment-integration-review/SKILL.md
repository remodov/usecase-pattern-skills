---
name: ucp-py-payment-integration-review
lang: python
description: Проверить outbound-интеграцию с платёжным провайдером по UCP (коды R-PAYINT-*) — идемпотентность (read-before-write по natural key, charge-if-not-terminal), сериализация конкурентных оплат заказа, единый anti-corruption status-mapper без утечки DTO, разделение транспорт/бизнес-ошибок (нет FAILED по таймауту), reconciliation незавершённых, Decimal+округление копеек (не float), отсутствие PAN/секретов в логах. Вызывается на ревью платёжных out-adapter, сервисов оплаты, status-mapper, фоновых дозаборов.
allowed-tools: Read Glob Grep
---

# Ревью платёжной интеграции (Python / FastAPI + httpx)

Ты проверяешь outbound-оплату против `backend/payment-integration/payment-integration-rules.md` (`R-PAYINT-*`) и
`backend/payment-integration/python/payment-integration-style-guide.md`. Формат findings —
`shared/review-finding-format.md` (`RFF-*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/payment-integration/payment-integration-rules.md`, `.claude/docs/backend/payment-integration/python/payment-integration-style-guide.md` и `.claude/docs/shared/review-finding-format.md`. Связанные: `R-JOB-*`, `R-DIST-IDEM-*`, `R-RES-*`, `R-ERR-*`.

2. **Определи объект:** платёжный out-adapter (клиент провайдера), сервис оплаты (register/charge/finalize), status-mapper, репозиторий платежей, фоновый дозабор.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **Идемпотентность** (`R-PAYINT-1..4`): read-before-write по natural key; charge только при не-терминальном статусе; конкурентные оплаты заказа сериализованы (advisory-lock/claim). Нет `register` без `find_status` (`X1`), `charge` без проверки (`X2`).
   - **Anti-corruption** (`R-PAYINT-5..7`): единый stateless status-mapper; наружу доменные типы; partial-update. Нет дублирования маппинга (`X3`), нет утечки DTO провайдера (`X4`).
   - **Транспорт vs бизнес** (`R-PAYINT-8..10`): транспортная ошибка → повтор/не финализировать FAIL; бизнес-отказ → терминал; port-specific исключение. Нет FAILED по таймауту/5xx (`X5`), нет единого `except` без различения (`X6`).
   - **Reconciliation** (`R-PAYINT-11..12`): фоновый дозабор незавершённых (claim SKIP LOCKED + UTC TTL). Нет опоры только на онлайн-путь (`X7`).
   - **Деньги** (`R-PAYINT-13`): `Decimal` + `ROUND_HALF_UP` для минорных единиц. Нет `float`/`int(float*100)` (`X8`).
   - **Аудит/PII** (`R-PAYINT-14..15`): метрики/логи с идентификатором; нет PAN/секретов (`X9`); есть аудит-след (`X10`).

4. **Частые реальные дефекты** (приоритет): финализация FAILED по транспортной ошибке; `int(float(amount)*100)` для копеек; интерпретация кодов провайдера в нескольких местах; отсутствие сериализации конкурентных оплат (двойной платёж); карты/секреты в логах.

5. **Выдай findings** по `RFF-*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-payment-integration-design`.

## Что не входит

- Resilience-механизм клиента (retry/CB/timeout по существу) — `ucp-py-resilience-review`. Структура out-adapter/портов — `ucp-py-integration-review`. Фоновый дозабор как планировщик — `ucp-py-scheduler-review`. Общая идемпотентность/saga — `ucp-py-distributed-review`. PII/секреты вне платёжного контекста — `ucp-py-security-review`.

$ARGUMENTS
