---
name: ucp-node-integration-review
lang: node
description: Ревью outbound-интеграции NestJS-сервиса на Node (коды R-RES-*, R-HEX-*, AUTH-*) — порт + Symbol-токен в core/, adapter мапит DTO→domain, cockatiel-обвязка на public-методе, клиент из OpenAPI, секреты не в коде, terminus health-check.
when_to_use: Изменения в adapters/out/<system> (adapter, client, mapper), портах core/<bc>/port/out/, конфиге клиента и DI-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью outbound-интеграции (Node / undici + cockatiel + hexagonal)

Ты ревьюишь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; своих кодов нет —
цитируешь `R-RES-*`/`R-HEX-*`/`AUTH-*`. Фокус: **структура** (порт/адаптер/mapper) и связность с resilience.

## Зависимости (по секциям)

- **`backend/resilience/node/resilience-style-guide.md`** (`R-RES-ISO/OAS-*`) — per-system isolation, mapper, DTO не утекает.
- **`backend/hexagonal/node/hexagonal-style-guide.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер→порт.
- **`backend/auth-patterns/auth-patterns-rules.md`** (`AUTH-17` секреты, `AUTH-19` idempotency).
- **`backend/node/nest-bootstrap/nest-bootstrap-rules.md`** (`NESTBOOT-4/6/12` конфиг, wiring, shutdown).

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `R-HEX-PORT-X1`, `AUTH-17`), не префикс.

2. **Скоп.** `adapters/out/<system>/**` (`*.adapter.ts`, `*client*.ts`, `*.mapper.ts`), порт в `core/<bc>/port/out/`, `<system>-client.config.ts`, openapi-спека, DI-wiring в feature-модуле/`app/`; `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-*`):** порт — интерфейс + Symbol-токен в `core/<bc>/port/out/`, не в адаптере (`R-HEX-PORT-X1`); адаптер реализует порт и биндится на токен, per-system папка; не реализует порты разных доменов (`R-HEX-AOUT-X3`); не инжектит другой адаптер (`R-HEX-AOUT-X4`).
   - **Mapper (`R-RES-OAS-4`):** `toDomain`/`toExternal` есть; DTO внешней системы не утекает из порт-метода (`R-RES-OAS-X3`); domain-типы в сигнатуре порта (`R-HEX-PORT-X2`).
   - **Resilience-обвязка:** cockatiel `wrap(retry, circuitBreaker, bulkhead, timeout)` на public-методе адаптера, не на сгенерированном клиенте (`R-RES-OAS-X1`); per-system isolation (`R-RES-ISO-X1`); retry только при идемпотентности (`R-RES-RE-X1`); нет стихийных авто-retry (axios-retry/got) вне композиции (`R-RES-RE-X4`). Детально — делегируй `ucp-node-resilience-review`.
   - **Клиент:** типы/клиент из OpenAPI-спеки (`R-RES-OAS-2`), спека в `adapters/out/<system>/openapi/`, codegen в `generated/` не коммитится (`R-RES-OAS-3`); per-system `Agent`/axios-инстанс с явными timeout (`R-RES-ISO-X2`).
   - **Секреты/конфиг (`AUTH-17`):** креды не в коде/`package.json`/yaml-в-репо; через env/secret-store; конфиг типизирован (`NESTBOOT-4`).
   - **Бизнес-логика:** решения (`if (response.code === 1)`) в адаптере → `R-HEX-AOUT-X2` (адаптер мапит, решает handler).
   - **Wiring (`NESTBOOT-*`):** клиент/policy — singleton-провайдеры (`NESTBOOT-6`), не пересоздаются на вызов; закрытие на shutdown (`enableShutdownHooks`/`OnApplicationShutdown`, `NESTBOOT-12`).

4. **Cross-check:** resilience-обвязка детально — `ucp-node-resilience-review`; структура портов/адаптеров — `ucp-node-hexagonal-review`; схема аутентификации к внешней системе — `ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — секреты в коде/конфиге (`AUTH-17`), порт-метод принимает/возвращает DTO внешней системы (`R-RES-OAS-X3`/`R-HEX-PORT-X2`), retry write без идемпотентности (`R-RES-RE-X1`), shared client на несколько систем (`R-RES-ISO-X1`).
   - **Предупреждение** — порт в адаптере (`R-HEX-PORT-X1`), нет mapper-а (DTO как domain), обёртки на сгенерированном клиенте (`R-RES-OAS-X1`), бизнес-логика в адаптере (`R-HEX-AOUT-X2`), клиент без явных pool/timeout (`R-RES-ISO-X2`).
   - **Замечание** — ручной клиент вместо генерации из OpenAPI (`R-RES-OAS-2`), нет health-check для системы.

## Что не входит

- Resilience-параметры (timeout/CB/retry значения) — `ucp-node-resilience-review`. Структура слоёв — `ucp-node-hexagonal-review`.
- Аутентификация к внешней системе (mTLS/Client Credentials) — `ucp-auth-review`.

$ARGUMENTS
