---
name: ucp-py-integration-review
lang: python
description: Ревью outbound-интеграции FastAPI-сервиса на Python (требования resilience/*, hexagonal/*) — порт-Protocol в core/, adapter мапит DTO→domain, resilience на public-методе, httpx из OpenAPI, секреты не в коде, health-check.
when_to_use: Изменения в adapters/out/<system> (adapter, client, mapper), портах core/<bc>/port/out/, settings и DI-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью outbound-интеграции (Python / httpx + hexagonal)

Ты ревьюишь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; своих кодов нет —
цитируешь `R-RES-*`/`R-HEX-*`/`AUTH-*`. Фокус: **структура** (порт/адаптер/mapper) и связность с resilience.

## Зависимости (по секциям)

- **`backend/resilience/references/python/implementation.md`** (`R-RES-ISO/OAS-*`) — per-system isolation, mapper, DTO не утекает.
- **`backend/hexagonal/references/python/implementation.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер→порт.
- **`backend/auth-patterns/spec.md`** (`auth-patterns/no-secrets-in-repository` секреты, `auth-patterns/money-commands-need-idempotency-key` idempotency).
- **`backend/python/python-bootstrap/spec.md`** (`PYBOOT-*` wiring/lifespan).

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `hexagonal/outbound-port-interface-in-core`, `auth-patterns/no-secrets-in-repository`), не префикс.

2. **Скоп.** `adapters/out/<system>/**` (`*_adapter.py`, `*_client*.py`, `*_mapper.py`), порт в `core/<bc>/port/out/`, `<system>_settings.py`, openapi-спека, DI-wiring в `app/`; `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-*`):** порт — `Protocol` в `core/<bc>/port/out/`, не в адаптере (`hexagonal/outbound-port-interface-in-core`); адаптер реализует порт, per-system пакет; не реализует порты разных доменов (`hexagonal/out-adapter-per-system`); не инжектит другой адаптер (`hexagonal/adapters-do-not-know-each-other`).
   - **Mapper (`resilience/mapper-between-client-and-port`):** `to_domain`/`to_external` есть; DTO внешней системы не утекает из порт-метода (`R-RES-OAS-X3`); domain-типы в сигнатуре порта (`hexagonal/port-speaks-domain-types`).
   - **Resilience-обвязка:** CB/semaphore/retry на public-методе адаптера, не на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); per-system isolation (`resilience/client-per-external-system`); retry только при идемпотентности (`resilience/retry-only-when-safe`). Детально — делегируй `ucp-py-resilience-review`.
   - **Клиент:** httpx из OpenAPI-спеки (`resilience/client-generated-from-contract`), спека в `adapters/out/<system>/openapi/`, codegen не коммитится.
   - **Секреты/конфиг (`auth-patterns/no-secrets-in-repository`):** креды не в коде/`pyproject`/yaml-в-репо; через env/secret-store.
   - **Бизнес-логика:** решения (`if response.code == 1`) в адаптере → `hexagonal/adapter-maps-not-decides` (адаптер мапит, решает handler).
   - **Wiring (`PYBOOT-*`):** клиент создаётся/закрывается в lifespan, не на уровне модуля (`python-bootstrap/resources-in-lifespan`).

4. **Cross-check:** resilience-обвязка детально — `ucp-py-resilience-review`; структура портов/адаптеров — `ucp-py-hexagonal-review`; схема аутентификации к внешней системе — `ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — секреты в коде/конфиге (`auth-patterns/no-secrets-in-repository`), порт-метод принимает/возвращает DTO внешней системы (`R-RES-OAS-X3`/`hexagonal/port-speaks-domain-types`), retry write без идемпотентности (`resilience/retry-only-when-safe`), shared client на несколько систем (`resilience/client-per-external-system`).
   - **Предупреждение** — порт в адаптере (`hexagonal/outbound-port-interface-in-core`), нет mapper'а (DTO как domain), обёртки на сгенерированном клиенте (`resilience/breaker-on-adapter-method`), бизнес-логика в адаптере (`hexagonal/adapter-maps-not-decides`), клиент на уровне модуля (`python-bootstrap/resources-in-lifespan`).
   - **Замечание** — ручной клиент вместо генерации из OpenAPI (`resilience/client-generated-from-contract`), нет health-check для системы.

## Что не входит

- Resilience-параметры (timeout/CB/retry значения) — `ucp-py-resilience-review`. Структура слоёв — `ucp-py-hexagonal-review`.
- Аутентификация к внешней системе (mTLS/Client Credentials) — `ucp-py-auth-review`.

$ARGUMENTS
