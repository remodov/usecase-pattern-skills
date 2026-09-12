---
name: ucp-py-integration-design
lang: python
description: Сгенерировать скелет outbound-интеграции FastAPI-сервиса (Python/httpx) с внешней системой по UCP — порт-Protocol в core/, httpx-клиент, out-adapter с CB/semaphore/tenacity-retry, mapper DTO→domain, health-check, pydantic-settings.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При подключении внешней системы.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Outbound-интеграция — проектирование (Python / httpx + hexagonal)

Ты генерируешь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; **главный** —
resilience. Сам новых правил не вводит.

## Зависимости (читай по нужным секциям, не весь файл)

- **`backend/resilience/references/python/implementation.md`** (`R-RES-*`) — главный: per-system client, CB/semaphore/retry, mapper, health.
- **`backend/hexagonal/references/python/implementation.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер реализует порт.
- **`backend/auth-patterns/spec.md`** (`auth-patterns/money-commands-need-idempotency-key` idempotency для retry, `auth-patterns/no-secrets-in-repository` секреты не в коде).
- **`backend/rest-api/spec.md`** (`R-API-OAS-*` для генерации клиента из OpenAPI).
- **`backend/python/python-bootstrap/spec.md`** (`PYBOOT-*` DI-wiring клиента в lifespan/container).

## Инструкции

1. **Прочитай** нужные секции выше. Коды в обосновании, не в коде.

2. **Уровень зрелости:** outbound с domain-портом в `core/` — Уровень 3 (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в Handler напрямую, без порт-абстракции; упрости вывод.

3. **Произведи скелет** (per-system пакет `adapters/out/<system>/`):
   - **Порт** — `Protocol` в `core/<bc>/port/out/<system>_port.py`, domain-типы в сигнатурах, базовое port-исключение в `core/` (`R-HEX-PORT-1/3`).
   - **Клиент** — `httpx.AsyncClient` (сгенерированный `openapi-python-client` из спеки `adapters/out/<system>/openapi/`, либо ручной) с `Limits` + `Timeout` (`resilience/client-per-external-system`, `resilience/client-generated-from-contract`).
   - **Adapter** — реализует порт; CB (`purgatory`/`aiobreaker`) + `asyncio.Semaphore` + `tenacity`-retry (только при идемпотентности) на public-методе; `CircuitBreakerError`→port-исключение (`R-RES-CB-*`/`R-RES-BH-*`/`resilience/retry-only-when-safe`).
   - **Mapper** — `to_domain`/`to_external` DTO ↔ domain; адаптер не пробрасывает DTO наверх (`resilience/mapper-between-client-and-port`).
   - **Health-check** — per-system, TTL-кеш, лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `<System>ClientSettings` (pydantic-settings), секреты не в коде (`auth-patterns/no-secrets-in-repository`).
   - **DI-wiring** — клиент/адаптер собираются в `app/container` + закрытие клиента в `lifespan` (`PYBOOT-5/6`).

4. **Самопроверка** + предложи `ucp-py-integration-review` (и `ucp-py-resilience-review` для resilience-обвязки).

## Антипаттерны, которые НЕ генерировать

- Порт в out-adapter (`hexagonal/outbound-port-interface-in-core`); порт-метод возвращает/принимает DTO внешней системы (`R-RES-OAS-X3`).
- Обёртки CB/retry на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); shared client/CB на несколько систем (`resilience/client-per-external-system`).
- Retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`); бизнес-логика в адаптере (`hexagonal/adapter-maps-not-decides`); секреты в коде/конфиге (`auth-patterns/no-secrets-in-repository`).

После работы скилла — обязательно `ucp-py-integration-review`.

$ARGUMENTS
