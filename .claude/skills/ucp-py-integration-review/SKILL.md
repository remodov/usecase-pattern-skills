---
name: ucp-py-integration-review
lang: python
description: Ревью outbound-интеграции FastAPI-сервиса на Python (коды R-RES-*, R-HEX-*, AUTH-*) — порт-Protocol в core/, adapter мапит DTO→domain, resilience на public-методе, httpx из OpenAPI, секреты не в коде, health-check.
when_to_use: Изменения в adapters/out/<system> (adapter, client, mapper), портах core/<bc>/port/out/, settings и DI-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью outbound-интеграции (Python / httpx + hexagonal)

Ты ревьюишь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; своих кодов нет —
цитируешь `R-RES-*`/`R-HEX-*`/`AUTH-*`. Фокус: **структура** (порт/адаптер/mapper) и связность с resilience.

## Зависимости (по секциям)

- **`backend/resilience/python/resilience-style-guide.md`** (`R-RES-ISO/OAS-*`) — per-system isolation, mapper, DTO не утекает.
- **`backend/hexagonal/python/hexagonal-style-guide.md`** (`R-HEX-PORT/AOUT-*`) — порт в `core/`, адаптер→порт.
- **`backend/auth-patterns/auth-patterns-rules.md`** (`AUTH-17` секреты, `AUTH-19` idempotency).
- **`backend/python/python-bootstrap/python-bootstrap-rules.md`** (`PYBOOT-*` wiring/lifespan).

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `R-HEX-PORT-X1`, `AUTH-17`), не префикс.

2. **Скоп.** `adapters/out/<system>/**` (`*_adapter.py`, `*_client*.py`, `*_mapper.py`), порт в `core/<bc>/port/out/`, `<system>_settings.py`, openapi-спека, DI-wiring в `app/`; `git diff`.

3. **Прогон.**
   - **Структура (`R-HEX-*`):** порт — `Protocol` в `core/<bc>/port/out/`, не в адаптере (`R-HEX-PORT-X1`); адаптер реализует порт, per-system пакет; не реализует порты разных доменов (`R-HEX-AOUT-X3`); не инжектит другой адаптер (`R-HEX-AOUT-X4`).
   - **Mapper (`R-RES-OAS-4`):** `to_domain`/`to_external` есть; DTO внешней системы не утекает из порт-метода (`R-RES-OAS-X3`); domain-типы в сигнатуре порта (`R-HEX-PORT-X2`).
   - **Resilience-обвязка:** CB/semaphore/retry на public-методе адаптера, не на сгенерированном клиенте (`R-RES-OAS-X1`); per-system isolation (`R-RES-ISO-X1`); retry только при идемпотентности (`R-RES-RE-X1`). Детально — делегируй `ucp-py-resilience-review`.
   - **Клиент:** httpx из OpenAPI-спеки (`R-RES-OAS-2`), спека в `adapters/out/<system>/openapi/`, codegen не коммитится.
   - **Секреты/конфиг (`AUTH-17`):** креды не в коде/`pyproject`/yaml-в-репо; через env/secret-store.
   - **Бизнес-логика:** решения (`if response.code == 1`) в адаптере → `R-HEX-AOUT-X2` (адаптер мапит, решает handler).
   - **Wiring (`PYBOOT-*`):** клиент создаётся/закрывается в lifespan, не на уровне модуля (`PYBOOT-X2`).

4. **Cross-check:** resilience-обвязка детально — `ucp-py-resilience-review`; структура портов/адаптеров — `ucp-py-hexagonal-review`; схема аутентификации к внешней системе — `ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — секреты в коде/конфиге (`AUTH-17`), порт-метод принимает/возвращает DTO внешней системы (`R-RES-OAS-X3`/`R-HEX-PORT-X2`), retry write без идемпотентности (`R-RES-RE-X1`), shared client на несколько систем (`R-RES-ISO-X1`).
   - **Предупреждение** — порт в адаптере (`R-HEX-PORT-X1`), нет mapper'а (DTO как domain), обёртки на сгенерированном клиенте (`R-RES-OAS-X1`), бизнес-логика в адаптере (`R-HEX-AOUT-X2`), клиент на уровне модуля (`PYBOOT-X2`).
   - **Замечание** — ручной клиент вместо генерации из OpenAPI (`R-RES-OAS-2`), нет health-check для системы.

## Что не входит

- Resilience-параметры (timeout/CB/retry значения) — `ucp-py-resilience-review`. Структура слоёв — `ucp-py-hexagonal-review`.
- Аутентификация к внешней системе (mTLS/Client Credentials) — `ucp-py-auth-review`.

$ARGUMENTS
