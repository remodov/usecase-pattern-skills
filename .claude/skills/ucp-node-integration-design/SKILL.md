---
name: ucp-node-integration-design
lang: node
description: Сгенерировать скелет outbound-интеграции NestJS-сервиса (Node, undici/axios) с внешней системой по UCP — порт + Symbol-токен в core/, клиент из OpenAPI, out-adapter с cockatiel CB/bulkhead/retry, mapper DTO→domain, terminus health.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При подключении внешней системы.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# Outbound-интеграция — проектирование (Node / undici + cockatiel + hexagonal)

Ты генерируешь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; **главный** —
resilience. Сам новых правил не вводит.

## Зависимости (читай по нужным секциям, не весь файл)

- **`backend/resilience/references/node/implementation.md`** (`R-RES-*`) — главный: per-system client, cockatiel CB/bulkhead/retry, mapper, health.
- **`backend/hexagonal/references/node/implementation.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер реализует порт.
- **`backend/auth-patterns/spec.md`** (`auth-patterns/money-commands-need-idempotency-key` idempotency для retry, `auth-patterns/no-secrets-in-repository` секреты не в коде).
- **`backend/rest-api/spec.md`** (`R-API-OAS-*` для генерации клиента из OpenAPI).
- **`backend/node/nest-bootstrap/spec.md`** (`NESTBOOT-4/6/12` конфиг, DI-биндинг порта, shutdown-hooks).

## Инструкции

1. **Прочитай** нужные секции выше. Коды в обосновании, не в коде.

2. **Уровень зрелости:** outbound с domain-портом в `core/` — Уровень 3 (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в Handler напрямую, без порт-абстракции; упрости вывод.

3. **Произведи скелет** (per-system папка `adapters/out/<system>/`):
   - **Порт** — интерфейс + Symbol-токен в `core/<bc>/port/out/<system>-port.ts`, domain-типы в сигнатурах, базовое port-исключение в `core/` (`R-HEX-PORT-1/3`).
   - **Клиент** — per-system undici `Agent` (`connections`/`connectTimeout`/`headersTimeout`/`bodyTimeout`) либо `axios.create` с собственным агентом; типы/клиент сгенерированы из OpenAPI-спеки (`openapi-typescript` + `openapi-fetch` или openapi-generator `typescript-axios`), спека в `adapters/out/<system>/openapi/`, codegen в `generated/` (`.gitignore`) (`resilience/client-per-external-system`, `R-RES-OAS-2/3`).
   - **Adapter** — реализует порт; cockatiel-композиция `wrap(retry, circuitBreaker, bulkhead, timeout)` на public-методе (retry только при идемпотентности); `BrokenCircuitError`→port-исключение (`R-RES-CB-*`/`R-RES-BH-*`/`resilience/retry-only-when-safe`).
   - **Mapper** — `toDomain`/`toExternal` DTO ↔ domain; адаптер не пробрасывает DTO наверх (`resilience/mapper-between-client-and-port`).
   - **Health-check** — custom indicator `@nestjs/terminus` per-system, TTL-кеш ~30s, лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `<System>ClientConfig` (zod/class-validator, `nest-bootstrap/config-validated-at-startup`), секреты не в коде (`auth-patterns/no-secrets-in-repository`).
   - **DI-wiring** — клиент/policy/адаптер — провайдеры в feature-модуле, биндинг порта на токен (`nest-bootstrap/inject-by-port-tokens`); закрытие клиента — `enableShutdownHooks` + `OnApplicationShutdown` (`nest-bootstrap/shutdown-hooks-enabled`).

4. **Самопроверка** + предложи `ucp-node-integration-review` (и `ucp-node-resilience-review` для resilience-обвязки).

## Антипаттерны, которые НЕ генерировать

- Порт в out-adapter (`hexagonal/outbound-port-interface-in-core`); порт-метод возвращает/принимает DTO внешней системы (`R-RES-OAS-X3`).
- Обёртки CB/retry на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); shared client/CB на несколько систем (`resilience/client-per-external-system`); стихийные авто-retry (axios-retry, got-дефолты) вне cockatiel-композиции (`resilience/retry-with-backoff-and-limit`).
- Retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`); бизнес-логика в адаптере (`hexagonal/adapter-maps-not-decides`); секреты в коде/конфиге (`auth-patterns/no-secrets-in-repository`).

После работы скилла — обязательно `ucp-node-integration-review`.

$ARGUMENTS
