---
name: ucp-node-integration-design
lang: node
description: Сгенерировать скелет outbound-интеграции NestJS-сервиса (Node, undici/axios) с внешней системой по UCP (коды R-RES-*) — порт + Symbol-токен в core/, клиент из OpenAPI, out-adapter с cockatiel CB/bulkhead/retry, mapper DTO→domain, terminus health.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При подключении внешней системы.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# Outbound-интеграция — проектирование (Node / undici + cockatiel + hexagonal)

Ты генерируешь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; **главный** —
resilience. Сам новых правил не вводит.

## Зависимости (читай по нужным секциям, не весь файл)

- **`backend/resilience/node/resilience-style-guide.md`** (`R-RES-*`) — главный: per-system client, cockatiel CB/bulkhead/retry, mapper, health.
- **`backend/hexagonal/node/hexagonal-style-guide.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер реализует порт.
- **`backend/auth-patterns/auth-patterns-rules.md`** (`AUTH-19` idempotency для retry, `AUTH-17` секреты не в коде).
- **`backend/rest-api/rest-api-rules.md`** (`R-API-OAS-*` для генерации клиента из OpenAPI).
- **`backend/node/nest-bootstrap/nest-bootstrap-rules.md`** (`NESTBOOT-4/6/12` конфиг, DI-биндинг порта, shutdown-hooks).

## Инструкции

1. **Прочитай** нужные секции выше. Коды в обосновании, не в коде.

2. **Уровень зрелости:** outbound с domain-портом в `core/` — Уровень 3 (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в Handler напрямую, без порт-абстракции; упрости вывод.

3. **Произведи скелет** (per-system папка `adapters/out/<system>/`):
   - **Порт** — интерфейс + Symbol-токен в `core/<bc>/port/out/<system>-port.ts`, domain-типы в сигнатурах, базовое port-исключение в `core/` (`R-HEX-PORT-1/3`).
   - **Клиент** — per-system undici `Agent` (`connections`/`connectTimeout`/`headersTimeout`/`bodyTimeout`) либо `axios.create` с собственным агентом; типы/клиент сгенерированы из OpenAPI-спеки (`openapi-typescript` + `openapi-fetch` или openapi-generator `typescript-axios`), спека в `adapters/out/<system>/openapi/`, codegen в `generated/` (`.gitignore`) (`R-RES-ISO-1`, `R-RES-OAS-2/3`).
   - **Adapter** — реализует порт; cockatiel-композиция `wrap(retry, circuitBreaker, bulkhead, timeout)` на public-методе (retry только при идемпотентности); `BrokenCircuitError`→port-исключение (`R-RES-CB-*`/`R-RES-BH-*`/`R-RES-RE-1`).
   - **Mapper** — `toDomain`/`toExternal` DTO ↔ domain; адаптер не пробрасывает DTO наверх (`R-RES-OAS-4`).
   - **Health-check** — custom indicator `@nestjs/terminus` per-system, TTL-кеш ~30s, лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `<System>ClientConfig` (zod/class-validator, `NESTBOOT-4`), секреты не в коде (`AUTH-17`).
   - **DI-wiring** — клиент/policy/адаптер — провайдеры в feature-модуле, биндинг порта на токен (`NESTBOOT-6`); закрытие клиента — `enableShutdownHooks` + `OnApplicationShutdown` (`NESTBOOT-12`).

4. **Самопроверка** + предложи `ucp-node-integration-review` (и `ucp-node-resilience-review` для resilience-обвязки).

## Антипаттерны, которые НЕ генерировать

- Порт в out-adapter (`R-HEX-PORT-X1`); порт-метод возвращает/принимает DTO внешней системы (`R-RES-OAS-X3`).
- Обёртки CB/retry на сгенерированном клиенте (`R-RES-OAS-X1`); shared client/CB на несколько систем (`R-RES-ISO-X1`); стихийные авто-retry (axios-retry, got-дефолты) вне cockatiel-композиции (`R-RES-RE-X4`).
- Retry write без `Idempotency-Key` (`R-RES-RE-X1`); бизнес-логика в адаптере (`R-HEX-AOUT-X2`); секреты в коде/конфиге (`AUTH-17`).

После работы скилла — обязательно `ucp-node-integration-review`.

$ARGUMENTS
