---
name: ucp-go-integration-review
lang: go
description: Ревью outbound-интеграции Go-сервиса (net/http + chi) по UCP (требования resilience/*) — interface-порт в core/, gobreaker/semaphore/retry-go на public-методе, mapper domain↔DTO, oapi-codegen из OpenAPI, секреты через envconfig, health с TTL-кешем.
when_to_use: Изменения в adapter/out/<system>/ (adapter, client, mapper), портах core/<bc>/port/out/, конфиге out-adapter'а и DI-wiring в bootstrap/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью outbound-интеграции (Go / net/http + chi)

Ты ревьюишь скелет интеграции с внешней системой в Go-сервисе. Оркестрирует несколько контрактов;
своих кодов нет — цитируешь `R-RES-*`/`R-HEX-*`/`AUTH-*`/`GOBOOT-*`. Фокус: **структура**
(port-interface / adapter / mapper) и связность с resilience. Парадигма Go: ошибки — значения
(`apperr.Kind` + `errors.As` + `%w`), DI — конструкторная, resilience — `gobreaker`/`retry-go`/`semaphore`
на public-методе адаптера.

## Зависимости (по секциям)

- **`backend/resilience/references/go/implementation.md`** (`R-RES-ISO-*`, `R-RES-OAS-*`, `R-RES-CB-*`, `R-RES-RE-*`, `R-RES-HC-*`) — per-system isolation, CB/retry на public-методе, mapper generated→domain, TTL-кеш health.
- **`backend/hexagonal/references/go/implementation.md`** (`R-HEX-PORT-*`, `R-HEX-AOUT-*`, `R-HEX-MOD-*`) — порт в `core/`, compile-time assertion, mapper в адаптере, стрелка импортов.
- **`backend/auth-patterns/references/go/implementation.md`** (`auth-patterns/no-secrets-in-repository` секреты, `auth-patterns/money-commands-need-idempotency-key` idempotency) — креды через env/Vault, write-retry только с Idempotency-Key.
- **`backend/go/go-bootstrap/spec.md`** (`GOBOOT-*` wiring/config) — конструкторная сборка в `bootstrap/`, `envconfig`, нет глобальных синглтонов.

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `hexagonal/outbound-port-interface-in-core`, `auth-patterns/no-secrets-in-repository`, `go-bootstrap/dependencies-via-constructors`), не префикс.

2. **Скоп.** `adapter/out/<system>/` (`*_adapter.go`, `*_client*.go`, `*_mapper.go`, `errors.go`), порт в
   `core/<bc>/port/out/`, `config.go` out-adapter'а, `openapi/<system>.openapi.yaml`, wiring в `bootstrap/main.go`; `git diff`.

   **Grep-поиск антипаттернов:**
   - `var _ out\.` — проверить наличие compile-time assertion для каждого адаптера
   - `http\.DefaultClient` — нарушение `resilience/client-per-external-system`
   - `&http\.Client\{\}` без `Transport` — нарушение `resilience/client-per-external-system`
   - `return .*, nil` в `if err != nil` — проглатывание ошибки `error-handling/catch-does-not-swallow`
   - `retry\.Do` вместе с write-методами без `Idempotency-Key` — `resilience/retry-only-when-safe`

3. **Прогон.**

   ### Структура (`R-HEX-*`)
   - Порт — `interface` в `core/<bc>/port/out/`; не в адаптере (`hexagonal/outbound-port-interface-in-core`).
   - Port-методы принимают/возвращают domain-типы (`Money`, `OrderID`), не DTO внешней системы — `hexagonal/port-speaks-domain-types`.
   - `var _ out.XxxPort = (*XxxAdapter)(nil)` — compile-time assertion в адаптере (`hexagonal/out-adapter-per-system`).
   - Адаптер — per-system пакет `adapter/out/<system>/`; не реализует порты разных BC (`hexagonal/out-adapter-per-system`).
   - `adapter/out/<system>/` не импортирует другой `adapter/out/<other>/` (`hexagonal/adapters-do-not-know-each-other`).

   ### Mapper (`resilience/mapper-between-client-and-port`, `hexagonal/adapter-maps-not-decides`)
   - `ToSystemRequest` / `ToDomainResult` — отдельная структура `<System>Mapper` в пакете адаптера.
   - DTO внешней системы (generated или ручной) не утекает из port-метода (`R-RES-OAS-X3`/`hexagonal/port-speaks-domain-types`).
   - Port-метод возвращает domain-тип из `core/<bc>/port/out/`, не generated struct — `R-RES-OAS-X3`.

   ### Resilience-обвязка
   - `gobreaker.CircuitBreaker`, `semaphore.Weighted`, `retry.Do` — на **public-методе** адаптера, не на
     сгенерированном клиенте (`resilience/breaker-on-adapter-method`) и не на репозитории (`resilience/no-protection-around-local-operations`).
   - Per-system isolation: отдельный `*http.Client` + `*http.Transport` + `gobreaker` + `semaphore` (`resilience/client-per-external-system`).
   - `retry.Do` — только на идемпотентных вызовах; `retry.RetryIf` фильтрует транзиентные ошибки (не 4xx,
     не `gobreaker.ErrOpenState`) (`resilience/retry-only-when-safe`, `resilience/retry-only-when-safe`).
   - Детально (параметры CB/retry/bulkhead) — делегируй `ucp-go-resilience-review`.

   ### Клиент
   - Для новых интеграций — клиент из OpenAPI-спеки (`oapi-codegen`); спека в
     `adapter/out/<system>/openapi/<system>.openapi.yaml`; codegen в `internal/generated/<system>/`, не коммитится (`resilience/client-generated-from-contract`).
   - Ручной клиент без OpenAPI-спеки — замечание `resilience/client-generated-from-contract`.

   ### Секреты/конфиг (`auth-patterns/no-secrets-in-repository`, `go-bootstrap/config-is-typed-and-validated`)
   - URL, ключи, токены — через `envconfig`-поля с тегом `required:"true"`; не в коде, не в `*.yaml`-в-репо.
   - Per-system конфиг-структура (`SberClientConfig`) с `envconfig`-тегами и `default:`; prefix-конвенция.

   ### Ошибки в адаптере
   - Адаптер оборачивает транспортные/статус-ошибки во `<System>Error{Op, Err}` с `Unwrap() error` и
     `Kind() apperr.Integration` — маппит транспорт, не принимает бизнес-решение (`hexagonal/adapter-maps-not-decides`).
   - `errors.As` + `%w` — не `err.Error()` строкой, не `fmt.Errorf("...: %v", err)` (`error-handling/catch-does-not-swallow`).
   - Port-ошибки (`PaymentPortError`) объявлены в `core/<bc>/port/out/errors.go`; handler ловит через
     `errors.As(*out.PaymentPortError)`, не через `*SberError` напрямую.

   ### Wiring (`go-bootstrap/dependencies-via-constructors`)
   - `New<System>Adapter(cfg)` — конструктор в адаптере; вызывается только из `bootstrap/main.go`.
   - Нет `init()`, нет глобальных `var client *http.Client` на уровне пакета (`go-bootstrap/dependencies-via-constructors`).

   ### Health-check
   - На каждую систему — `<System>HealthChecker` с TTL-кешем (`sync.Mutex` + `lastCheck time.Time`),
     probe `GET /health` или `HEAD /`, TTL ≈ 30s (`resilience/cached-health-probe-per-system`, `resilience/cached-health-probe-per-system`, `resilience/cached-health-probe-per-system`).

4. **Cross-check:** resilience-параметры детально — `ucp-go-resilience-review`; структура портов/адаптеров —
   `ucp-go-hexagonal-review`; JWT-аутентификация к внешней системе (Client Credentials) — `ucp-go-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — секреты в коде/конфиге (`auth-patterns/no-secrets-in-repository`); port-метод принимает/возвращает DTO внешней системы
     (`R-RES-OAS-X3`/`hexagonal/port-speaks-domain-types`); `retry.Do` на write без `Idempotency-Key` (`resilience/retry-only-when-safe`);
     `http.DefaultClient` / shared `*http.Client` для нескольких систем (`resilience/client-per-external-system`);
     бизнес-решение в адаптере (`hexagonal/adapter-maps-not-decides`); проглатывание ошибки `return ..., nil` (`error-handling/catch-does-not-swallow`).
   - **Предупреждение** — порт-interface в адаптере, а не в `core/` (`hexagonal/outbound-port-interface-in-core`); нет compile-time
     assertion `var _ out.XxxPort = (*XxxAdapter)(nil)` (`hexagonal/out-adapter-per-system`); нет маппера (DTO как domain);
     `gobreaker`/`retry.Do` на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); wiring в пакете адаптера,
     а не в `bootstrap/` (`go-bootstrap/dependencies-via-constructors`); `fmt.Errorf("...: %v", err)` теряет тип (`error-handling/catch-does-not-swallow`).
   - **Замечание** — ручной клиент вместо oapi-codegen из OpenAPI (`resilience/client-generated-from-contract`); нет health-checker'а
     для системы; нет `OnStateChange`-лога на CB-переход (`resilience/resilience-state-is-observable`).

## Что не входит

- Resilience-параметры (timeout/CB-окно/retry-count) — `ucp-go-resilience-review`.
- Структура слоёв core/port/adapter глубже этого скопа — `ucp-go-hexagonal-review`.
- JWT / Client Credentials к внешней системе — `ucp-go-auth-review`.
- Конфигурация сервера, graceful shutdown — `ucp-go-bootstrap-review`.

$ARGUMENTS
