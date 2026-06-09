---
name: ucp-py-integration-design
lang: python
description: Сгенерировать скелет outbound-интеграции FastAPI-сервиса (Python/httpx) с внешней системой по UCP (коды R-RES-*) — порт-Protocol в core/, httpx-клиент, out-adapter с CB/semaphore/tenacity-retry, mapper DTO→domain, health-check, pydantic-settings.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При подключении внешней системы.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Outbound-интеграция — проектирование (Python / httpx + hexagonal)

Ты генерируешь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; **главный** —
resilience. Сам новых правил не вводит.

## Зависимости (читай по нужным секциям, не весь файл)

- **`backend/resilience/python/resilience-style-guide.md`** (`R-RES-*`) — главный: per-system client, CB/semaphore/retry, mapper, health.
- **`backend/hexagonal/python/hexagonal-style-guide.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер реализует порт.
- **`backend/auth-patterns/auth-patterns-rules.md`** (`AUTH-19` idempotency для retry, `AUTH-17` секреты не в коде).
- **`backend/rest-api/rest-api-rules.md`** (`R-API-OAS-*` для генерации клиента из OpenAPI).
- **`backend/python/python-bootstrap/python-bootstrap-rules.md`** (`PYBOOT-*` DI-wiring клиента в lifespan/container).

## Инструкции

1. **Прочитай** нужные секции выше. Коды в обосновании, не в коде.

2. **Уровень зрелости:** outbound с domain-портом в `core/` — Уровень 3 (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в Handler напрямую, без порт-абстракции; упрости вывод.

3. **Произведи скелет** (per-system пакет `adapters/out/<system>/`):
   - **Порт** — `Protocol` в `core/<bc>/port/out/<system>_port.py`, domain-типы в сигнатурах, базовое port-исключение в `core/` (`R-HEX-PORT-1/3`).
   - **Клиент** — `httpx.AsyncClient` (сгенерированный `openapi-python-client` из спеки `adapters/out/<system>/openapi/`, либо ручной) с `Limits` + `Timeout` (`R-RES-ISO-1`, `R-RES-OAS-2`).
   - **Adapter** — реализует порт; CB (`purgatory`/`aiobreaker`) + `asyncio.Semaphore` + `tenacity`-retry (только при идемпотентности) на public-методе; `CircuitBreakerError`→port-исключение (`R-RES-CB-*`/`R-RES-BH-*`/`R-RES-RE-1`).
   - **Mapper** — `to_domain`/`to_external` DTO ↔ domain; адаптер не пробрасывает DTO наверх (`R-RES-OAS-4`).
   - **Health-check** — per-system, TTL-кеш, лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `<System>ClientSettings` (pydantic-settings), секреты не в коде (`AUTH-17`).
   - **DI-wiring** — клиент/адаптер собираются в `app/container` + закрытие клиента в `lifespan` (`PYBOOT-5/6`).

4. **Самопроверка** + предложи `ucp-py-integration-review` (и `ucp-py-resilience-review` для resilience-обвязки).

## Антипаттерны, которые НЕ генерировать

- Порт в out-adapter (`R-HEX-PORT-X1`); порт-метод возвращает/принимает DTO внешней системы (`R-RES-OAS-X3`).
- Обёртки CB/retry на сгенерированном клиенте (`R-RES-OAS-X1`); shared client/CB на несколько систем (`R-RES-ISO-X1`).
- Retry write без `Idempotency-Key` (`R-RES-RE-X1`); бизнес-логика в адаптере (`R-HEX-AOUT-X2`); секреты в коде/конфиге (`AUTH-17`).

После работы скилла — обязательно `ucp-py-integration-review`.

$ARGUMENTS
