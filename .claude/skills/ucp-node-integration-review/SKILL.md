---
name: ucp-node-integration-review
lang: node
description: Ревью outbound-интеграции NestJS-сервиса на Node (требования resilience/*, hexagonal/*) — порт + Symbol-токен в core/, adapter мапит DTO→domain, cockatiel-обвязка на public-методе, клиент из OpenAPI, секреты не в коде, terminus health-check.
when_to_use: Изменения в adapters/out/<system> (adapter, client, mapper), портах core/<bc>/port/out/, конфиге клиента и DI-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью outbound-интеграции (Node / undici + cockatiel + hexagonal)

Ты ревьюишь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; своих кодов нет —
цитируешь `R-RES-*`/`R-HEX-*`/`AUTH-*`. Фокус: **структура** (порт/адаптер/mapper) и связность с resilience.

## Зависимости (по секциям)

- **`backend/resilience/references/node/implementation.md`** (`R-RES-ISO/OAS-*`) — per-system isolation, mapper, DTO не утекает.
- **`backend/hexagonal/references/node/implementation.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер→порт.
- **`backend/auth-patterns/spec.md`** (`auth-patterns/no-secrets-in-repository` секреты, `auth-patterns/money-commands-need-idempotency-key` idempotency).
- **`backend/node/nest-bootstrap/spec.md`** (`NESTBOOT-4/6/12` конфиг, wiring, shutdown).

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `hexagonal/outbound-port-interface-in-core`, `auth-patterns/no-secrets-in-repository`), не префикс.

2. **Скоп.** `adapters/out/<system>/**` (`*.adapter.ts`, `*client*.ts`, `*.mapper.ts`), порт в `core/<bc>/port/out/`, `<system>-client.config.ts`, openapi-спека, DI-wiring в feature-модуле/`app/`; `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-*`):** порт — интерфейс + Symbol-токен в `core/<bc>/port/out/`, не в адаптере (`hexagonal/outbound-port-interface-in-core`); адаптер реализует порт и биндится на токен, per-system папка; не реализует порты разных доменов (`hexagonal/out-adapter-per-system`); не инжектит другой адаптер (`hexagonal/adapters-do-not-know-each-other`).
   - **Mapper (`resilience/mapper-between-client-and-port`):** `toDomain`/`toExternal` есть; DTO внешней системы не утекает из порт-метода (`R-RES-OAS-X3`); domain-типы в сигнатуре порта (`hexagonal/port-speaks-domain-types`).
   - **Resilience-обвязка:** cockatiel `wrap(retry, circuitBreaker, bulkhead, timeout)` на public-методе адаптера, не на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); per-system isolation (`resilience/client-per-external-system`); retry только при идемпотентности (`resilience/retry-only-when-safe`); нет стихийных авто-retry (axios-retry/got) вне композиции (`resilience/retry-with-backoff-and-limit`). Детально — делегируй `ucp-node-resilience-review`.
   - **Клиент:** типы/клиент из OpenAPI-спеки (`resilience/client-generated-from-contract`), спека в `adapters/out/<system>/openapi/`, codegen в `generated/` не коммитится (`resilience/client-generated-from-contract`); per-system `Agent`/axios-инстанс с явными timeout (`resilience/client-per-external-system`).
   - **Секреты/конфиг (`auth-patterns/no-secrets-in-repository`):** креды не в коде/`package.json`/yaml-в-репо; через env/secret-store; конфиг типизирован (`nest-bootstrap/config-validated-at-startup`).
   - **Бизнес-логика:** решения (`if (response.code === 1)`) в адаптере → `hexagonal/adapter-maps-not-decides` (адаптер мапит, решает handler).
   - **Wiring (`NESTBOOT-*`):** клиент/policy — singleton-провайдеры (`nest-bootstrap/inject-by-port-tokens`), не пересоздаются на вызов; закрытие на shutdown (`enableShutdownHooks`/`OnApplicationShutdown`, `nest-bootstrap/shutdown-hooks-enabled`).

4. **Cross-check:** resilience-обвязка детально — `ucp-node-resilience-review`; структура портов/адаптеров — `ucp-node-hexagonal-review`; схема аутентификации к внешней системе — `ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — секреты в коде/конфиге (`auth-patterns/no-secrets-in-repository`), порт-метод принимает/возвращает DTO внешней системы (`R-RES-OAS-X3`/`hexagonal/port-speaks-domain-types`), retry write без идемпотентности (`resilience/retry-only-when-safe`), shared client на несколько систем (`resilience/client-per-external-system`).
   - **Предупреждение** — порт в адаптере (`hexagonal/outbound-port-interface-in-core`), нет mapper-а (DTO как domain), обёртки на сгенерированном клиенте (`resilience/breaker-on-adapter-method`), бизнес-логика в адаптере (`hexagonal/adapter-maps-not-decides`), клиент без явных pool/timeout (`resilience/client-per-external-system`).
   - **Замечание** — ручной клиент вместо генерации из OpenAPI (`resilience/client-generated-from-contract`), нет health-check для системы.

## Что не входит

- Resilience-параметры (timeout/CB/retry значения) — `ucp-node-resilience-review`. Структура слоёв — `ucp-node-hexagonal-review`.
- Аутентификация к внешней системе (mTLS/Client Credentials) — `ucp-auth-review`.

$ARGUMENTS
