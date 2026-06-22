---
name: ucp-go-integration-design
lang: go
description: Сгенерировать скелет outbound-интеграции Go-сервиса (net/http + chi) с внешней системой по UCP (коды R-RES-*, R-HEX-*) — port-интерфейс в core/, http.Client с gobreaker/semaphore/retry-go, mapper domain↔DTO, health-check, envconfig.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При подключении внешней системы.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Outbound-интеграция — проектирование (Go / net/http + chi)

Ты генерируешь скелет интеграции с внешней системой. Оркестрирует несколько контрактов; **главный** —
resilience. Сам новых правил не вводит.

## Зависимости (читай по нужным секциям, не весь файл)

- **`backend/resilience/go/resilience-style-guide.md`** (`R-RES-*`) — главный: per-system `*http.Client` + `*http.Transport`, gobreaker/semaphore/retry-go, mapper, health.
- **`backend/hexagonal/go/hexagonal-style-guide.md`** (`R-HEX-PORT/AOUT-*`) — port-интерфейс в `core/`, адаптер реализует порт.
- **`backend/auth-patterns/go/auth-patterns-style-guide.md`** (`AUTH-19` идемпотентность при retry, `AUTH-17` секреты не в коде).
- **`backend/rest-api/go/rest-api-style-guide.md`** (`R-API-OAS-*` для генерации клиента из OpenAPI).
- **`backend/go/go-bootstrap/go-bootstrap-rules.md`** (`GOBOOT-5/6` конструкторная DI, сборка в `main.go`).

## Инструкции

1. **Прочитай** нужные секции выше. Коды в обосновании, не в коде.

2. **Уровень зрелости:** outbound с domain-портом в `core/` — Уровень 3 (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в Handler напрямую, без port-абстракции; упрости вывод.

3. **Произведи скелет** (per-system пакет `adapters/out/<system>/`):
   - **Порт** — interface в `core/<bc>/port/out/<system>_port.go`, domain-типы в сигнатурах, port-ошибка рядом с интерфейсом в `core/` (`R-HEX-PORT-1/3`).
   - **Клиент** — отдельный `*http.Client` с явным `*http.Transport` (`R-RES-ISO-1/2`); конфиг через `<System>ClientConfig` (envconfig-теги, типобезопасно `GOBOOT-4`); если внешняя система имеет OpenAPI-спеку — `oapi-codegen` из `adapters/out/<system>/openapi/<system>.openapi.yaml` (`R-RES-OAS-2`).
   - **Adapter** — реализует порт; `gobreaker.CircuitBreaker` + `semaphore.NewWeighted` + `retry.Do` с `retry.RetryIf` (только идемпотентные методы) на public-методе, не на сгенерированном клиенте (`R-RES-CB-*`/`R-RES-BH-*`/`R-RES-RE-1`, `R-RES-OAS-X1`); `gobreaker.ErrOpenState` → port-ошибка с `Kind() Integration` + `%w` (`R-ERR-WHERE-2b`).
   - **Mapper** — функции `toPort`/`toExternal` (generated DTO ↔ domain-тип); адаптер не пробрасывает generated DTO наверх (`R-RES-OAS-4`).
   - **Health-check** — per-system функция-probe + TTL-кеш на `sync.Mutex` + поле `cachedAt time.Time` (`R-RES-HC-*`).
   - **Конфиг** — `<System>ClientConfig` с envconfig-тегами; секреты не в коде и не в git (`AUTH-17`).
   - **DI-wiring** — `New<System>Adapter(cfg, client)` конструктором; клиент создаётся в сборщике `bootstrap/main.go`; `http.Client.CloseIdleConnections()` при shutdown (`GOBOOT-5/6`).

4. **Самопроверка** + предложи `ucp-go-integration-review` (и `ucp-go-resilience-review` для resilience-обвязки).

## Антипаттерны, которые НЕ генерировать

- Порт в out-adapter (`R-HEX-PORT-X1`); port-метод возвращает/принимает generated DTO (`R-RES-OAS-X3`).
- `gobreaker`/`retry.Do` вокруг репозитория или SQL-запроса (`R-RES-WHERE-X1`); один `*http.Client` / один `gobreaker` на несколько систем (`R-RES-ISO-X1`); `&http.Client{}` без явного `Transport` (`R-RES-ISO-X2`).
- Обёртки CB/retry встроены в сгенерированный клиент (`R-RES-OAS-X1`); retry write без `Idempotency-Key` (`AUTH-19`).
- Бизнес-логика в адаптере (`R-HEX-AOUT-X2`); секреты в коде/конфиге (`AUTH-17`).
- `_ = call()` / проглатывание ошибок; `fmt.Errorf("...%v", err)` без `%w` (`R-ERR-WHERE-X1/X2`).

После работы скилла — обязательно `ucp-go-integration-review`.

$ARGUMENTS
