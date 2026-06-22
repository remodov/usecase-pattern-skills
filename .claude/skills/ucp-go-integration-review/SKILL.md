---
name: ucp-go-integration-review
lang: go
description: Ревью outbound-интеграции Go-сервиса (net/http + chi) по UCP (коды R-RES-*, R-HEX-*) — interface-порт в core/, gobreaker/semaphore/retry-go на public-методе, mapper domain↔DTO, oapi-codegen из OpenAPI, секреты через envconfig, health с TTL-кешем.
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

- **`backend/resilience/go/resilience-style-guide.md`** (`R-RES-ISO-*`, `R-RES-OAS-*`, `R-RES-CB-*`, `R-RES-RE-*`, `R-RES-HC-*`) — per-system isolation, CB/retry на public-методе, mapper generated→domain, TTL-кеш health.
- **`backend/hexagonal/go/hexagonal-style-guide.md`** (`R-HEX-PORT-*`, `R-HEX-AOUT-*`, `R-HEX-MOD-*`) — порт в `core/`, compile-time assertion, mapper в адаптере, стрелка импортов.
- **`backend/auth-patterns/go/auth-patterns-style-guide.md`** (`AUTH-17` секреты, `AUTH-19` idempotency) — креды через env/Vault, write-retry только с Idempotency-Key.
- **`backend/go/go-bootstrap/go-bootstrap-rules.md`** (`GOBOOT-*` wiring/config) — конструкторная сборка в `bootstrap/`, `envconfig`, нет глобальных синглтонов.

## Инструкции

1. **Прочти** нужные секции. Цитируй конкретные коды (`R-RES-OAS-X3`, `R-HEX-PORT-X1`, `AUTH-17`, `GOBOOT-X2`), не префикс.

2. **Скоп.** `adapter/out/<system>/` (`*_adapter.go`, `*_client*.go`, `*_mapper.go`, `errors.go`), порт в
   `core/<bc>/port/out/`, `config.go` out-adapter'а, `openapi/<system>.openapi.yaml`, wiring в `bootstrap/main.go`; `git diff`.

   **Grep-поиск антипаттернов:**
   - `var _ out\.` — проверить наличие compile-time assertion для каждого адаптера
   - `http\.DefaultClient` — нарушение `R-RES-ISO-X1`
   - `&http\.Client\{\}` без `Transport` — нарушение `R-RES-ISO-X2`
   - `return .*, nil` в `if err != nil` — проглатывание ошибки `R-ERR-WHERE-X3`
   - `retry\.Do` вместе с write-методами без `Idempotency-Key` — `R-RES-RE-X1`

3. **Прогон.**

   ### Структура (`R-HEX-*`)
   - Порт — `interface` в `core/<bc>/port/out/`; не в адаптере (`R-HEX-PORT-X1`).
   - Port-методы принимают/возвращают domain-типы (`Money`, `OrderID`), не DTO внешней системы — `R-HEX-PORT-X2`.
   - `var _ out.XxxPort = (*XxxAdapter)(nil)` — compile-time assertion в адаптере (`R-HEX-AOUT-2`).
   - Адаптер — per-system пакет `adapter/out/<system>/`; не реализует порты разных BC (`R-HEX-AOUT-X3`).
   - `adapter/out/<system>/` не импортирует другой `adapter/out/<other>/` (`R-HEX-AOUT-X4`).

   ### Mapper (`R-RES-OAS-4`, `R-HEX-AOUT-3`)
   - `ToSystemRequest` / `ToDomainResult` — отдельная структура `<System>Mapper` в пакете адаптера.
   - DTO внешней системы (generated или ручной) не утекает из port-метода (`R-RES-OAS-X3`/`R-HEX-PORT-X2`).
   - Port-метод возвращает domain-тип из `core/<bc>/port/out/`, не generated struct — `R-RES-OAS-X3`.

   ### Resilience-обвязка
   - `gobreaker.CircuitBreaker`, `semaphore.Weighted`, `retry.Do` — на **public-методе** адаптера, не на
     сгенерированном клиенте (`R-RES-OAS-X1`) и не на репозитории (`R-RES-WHERE-X1`).
   - Per-system isolation: отдельный `*http.Client` + `*http.Transport` + `gobreaker` + `semaphore` (`R-RES-ISO-1`).
   - `retry.Do` — только на идемпотентных вызовах; `retry.RetryIf` фильтрует транзиентные ошибки (не 4xx,
     не `gobreaker.ErrOpenState`) (`R-RES-RE-X1`, `R-RES-RE-X2`).
   - Детально (параметры CB/retry/bulkhead) — делегируй `ucp-go-resilience-review`.

   ### Клиент
   - Для новых интеграций — клиент из OpenAPI-спеки (`oapi-codegen`); спека в
     `adapter/out/<system>/openapi/<system>.openapi.yaml`; codegen в `internal/generated/<system>/`, не коммитится (`R-RES-OAS-2`).
   - Ручной клиент без OpenAPI-спеки — замечание `R-RES-OAS-2`.

   ### Секреты/конфиг (`AUTH-17`, `GOBOOT-4`)
   - URL, ключи, токены — через `envconfig`-поля с тегом `required:"true"`; не в коде, не в `*.yaml`-в-репо.
   - Per-system конфиг-структура (`SberClientConfig`) с `envconfig`-тегами и `default:`; prefix-конвенция.

   ### Ошибки в адаптере
   - Адаптер оборачивает транспортные/статус-ошибки во `<System>Error{Op, Err}` с `Unwrap() error` и
     `Kind() apperr.Integration` — маппит транспорт, не принимает бизнес-решение (`R-HEX-AOUT-X2`).
   - `errors.As` + `%w` — не `err.Error()` строкой, не `fmt.Errorf("...: %v", err)` (`R-ERR-WHERE-X2`).
   - Port-ошибки (`PaymentPortError`) объявлены в `core/<bc>/port/out/errors.go`; handler ловит через
     `errors.As(*out.PaymentPortError)`, не через `*SberError` напрямую.

   ### Wiring (`GOBOOT-6`)
   - `New<System>Adapter(cfg)` — конструктор в адаптере; вызывается только из `bootstrap/main.go`.
   - Нет `init()`, нет глобальных `var client *http.Client` на уровне пакета (`GOBOOT-X2`).

   ### Health-check
   - На каждую систему — `<System>HealthChecker` с TTL-кешем (`sync.Mutex` + `lastCheck time.Time`),
     probe `GET /health` или `HEAD /`, TTL ≈ 30s (`R-RES-HC-1`, `R-RES-HC-2`, `R-RES-HC-X1`).

4. **Cross-check:** resilience-параметры детально — `ucp-go-resilience-review`; структура портов/адаптеров —
   `ucp-go-hexagonal-review`; JWT-аутентификация к внешней системе (Client Credentials) — `ucp-go-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — секреты в коде/конфиге (`AUTH-17`); port-метод принимает/возвращает DTO внешней системы
     (`R-RES-OAS-X3`/`R-HEX-PORT-X2`); `retry.Do` на write без `Idempotency-Key` (`R-RES-RE-X1`);
     `http.DefaultClient` / shared `*http.Client` для нескольких систем (`R-RES-ISO-X1`);
     бизнес-решение в адаптере (`R-HEX-AOUT-X2`); проглатывание ошибки `return ..., nil` (`R-ERR-WHERE-X3`).
   - **Предупреждение** — порт-interface в адаптере, а не в `core/` (`R-HEX-PORT-X1`); нет compile-time
     assertion `var _ out.XxxPort = (*XxxAdapter)(nil)` (`R-HEX-AOUT-2`); нет маппера (DTO как domain);
     `gobreaker`/`retry.Do` на сгенерированном клиенте (`R-RES-OAS-X1`); wiring в пакете адаптера,
     а не в `bootstrap/` (`GOBOOT-X2`); `fmt.Errorf("...: %v", err)` теряет тип (`R-ERR-WHERE-X2`).
   - **Замечание** — ручной клиент вместо oapi-codegen из OpenAPI (`R-RES-OAS-2`); нет health-checker'а
     для системы; нет `OnStateChange`-лога на CB-переход (`R-RES-OBS-3`).

## Что не входит

- Resilience-параметры (timeout/CB-окно/retry-count) — `ucp-go-resilience-review`.
- Структура слоёв core/port/adapter глубже этого скопа — `ucp-go-hexagonal-review`.
- JWT / Client Credentials к внешней системе — `ucp-go-auth-review`.
- Конфигурация сервера, graceful shutdown — `ucp-go-bootstrap-review`.

$ARGUMENTS
