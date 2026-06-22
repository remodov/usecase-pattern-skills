---
name: ucp-go-hexagonal-review
lang: go
description: Ревью Hexagonal Architecture Go-сервиса (net/http + chi) по UCP (коды R-HEX-*) — пакеты core/adapter/bootstrap, архитектурный тест импортов, core без chi/pgx/sqlc, порты-interface в core/port/out, chi-handler → маппер → Handler, per-system адаптеры.
when_to_use: Ревью раскладки Go-сервиса Уровня 3 — internal/core/, internal/adapter/, bootstrap/, архитектурный тест импортов, проверка стрелок зависимостей.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*) Bash(golangci-lint*)
---

# Ревью Hexagonal (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Go-реализации** `backend/hexagonal/go/hexagonal-style-guide.md`. Изоляция — через архитектурный тест импортов
(`packages.Load` + forbidden-list) в CI; в Go нет compile-time module-isolation внутри одного репо, поэтому
enforcement — автоматический тест.

## Зависимости

- **`.claude/docs/backend/hexagonal/hexagonal-rules.md`** — общий контракт (`R-HEX-WHEN-*`/`MOD-*`/`CORE-*`/`PORT-*`/`AIN-*`/`AOUT-*`/`BOOT-*`/`TEST-*`).
- **`.claude/docs/backend/hexagonal/go/hexagonal-style-guide.md`** — Go-реализация (пакетная раскладка, `apperr.Kind`, `errors.As`, chi-middleware, sqlc-типы, `var _ Port = (*Adapter)(nil)`).
- Парные: `backend/usecase-pattern/go/...` (Handler/Command), `backend/ddd-tactical/go/...` (rich domain), `backend/error-handling/go/error-handling-style-guide.md` (apperr, edge-renderer, recover-middleware).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-HEX-CORE-X1`, `R-HEX-PORT-X2`), не только префикс.

2. **Скоп.** `internal/core/<bc>/**`, `internal/adapter/in/**`, `internal/adapter/out/**`, `bootstrap/main.go`, `bootstrap/architecture_test.go`, CI-конфиг, `git diff`.

3. **Прогон по подгруппам.**

   ### Структура (`R-HEX-MOD-*`)
   - Дерево `internal/core/` / `internal/adapter/in/` / `internal/adapter/out/` / `bootstrap/` присутствует? `R-HEX-MOD-X1` если всё в одном пакете без enforcement.
   - `core/<bc>/` не импортирует `adapter/*`? `R-HEX-MOD-X2` (стрелка: `bootstrap → adapter → core`).
   - User- и admin-роутеры в отдельных пакетах (`adapter/in/http/user/`, `adapter/in/http/admin/`)? `R-HEX-MOD-X3` если совмещены.
   - Каждая внешняя система — отдельный пакет (`adapter/out/sber/`, `adapter/out/persistence/`)? `R-HEX-MOD-3/4`.
   - `bootstrap/` — единственное место, где импортируются все адаптеры вместе? `R-HEX-MOD-5`.

   ### Core (`R-HEX-CORE-*`)
   - `core/<bc>/` зависит только от stdlib (`context`, `errors`, `time`, `fmt`) и `core/apperr`? Запрещены `chi`, `pgx`, `sqlc`-types, `slog`, `go-redis`, `kafka-go`. `R-HEX-CORE-X1/X2`.
   - Структура: `aggregate/`, `value_object/`, `event/`, `port/out/`, `usecase/`, `service/` (при необходимости)? `R-HEX-CORE-2`.
   - Бизнес-логика внутри агрегата (`order.Confirm(...) error`), не в `*Service`? `R-HEX-CORE-4`; анемия — `R-HEX-CORE-X3`.
   - Sqlc-generated struct (`db.Order`) не используется как доменный тип в `core/`? `R-HEX-CORE-X4`.
   - HTTP-DTO (`CreateOrderRequest`) отсутствует в `core/`? `R-HEX-CORE-X5`.
   - Wiring — только через конструкторы в `bootstrap/`; нет `init()`/глобальных синглтонов; нет `var db *pgx.Pool` в `core/`. `R-HEX-CORE-3`.

   ### Ports (`R-HEX-PORT-*`)
   - Outbound-порт = `interface` в `core/<bc>/port/out/`; port-ошибки (`PaymentPortError` с `Kind() apperr.Integration`) — там же. `R-HEX-PORT-1/3`. Порт не в `adapter/out/`? `R-HEX-PORT-X1`.
   - Port-методы принимают/возвращают domain-типы (`Money`, `OrderID`), не DTO внешней системы (`SberRegisterRequest`)? `R-HEX-PORT-2`/`R-HEX-PORT-X2`.
   - Порт возвращает ошибку с domain-смыслом (`*OrderNotFoundError`), не `(Order, bool)`? `R-HEX-PORT-X3`.
   - Порт — `interface`, не `struct`? `R-HEX-PORT-X4`.
   - Handler ловит `*out.PaymentPortError` через `errors.As`, не system-specific `*SberError` напрямую? `R-HEX-PORT-3`.
   - В адаптере есть compile-time assertion `var _ out.XxxPort = (*XxxAdapter)(nil)`? `R-HEX-AOUT-2`.

   ### Adapters in (`R-HEX-AIN-*`)
   - chi-handler маппит request-DTO → command через `OrderRequestMapper`, затем вызывает `UseCase.Handle`? `R-HEX-AIN-2`.
   - Маппер — отдельная структура в пакете адаптера (`order_request_mapper.go`); domain entity не сериализуется напрямую в HTTP-ответ? `R-HEX-AIN-3`/`R-HEX-AIN-X3`.
   - Handler не инжектит репозиторий напрямую? `R-HEX-AIN-X2`.
   - `adapter/in/http/` не импортирует `adapter/out/*`? `R-HEX-AIN-X4`.
   - Нет бизнес-логики в handler (проверок бизнес-правил типа `if req.Amount > 100_000`)? `R-HEX-AIN-X1`.
   - Ошибки из `Handle` передаются в `httperr.Write`; нет `w.WriteHeader(200)` при ошибке.

   ### Adapters out (`R-HEX-AOUT-*`)
   - Каждая внешняя система — отдельный пакет; per-system isolation. `R-HEX-AOUT-1`.
   - Адаптер реализует port-interface из `core/`; маппит `domain ↔ system-DTO` в отдельной структуре-маппере (`PaymentMapper`). `R-HEX-AOUT-2/3`.
   - Port-метод не возвращает system-DTO (`SberRegisterResponse`)? `R-HEX-AOUT-X1`.
   - Нет бизнес-логики в адаптере (условных переходов по domain-смыслу)? `R-HEX-AOUT-X2`.
   - Один адаптер не реализует порты разных доменов? `R-HEX-AOUT-X3`.
   - `SberAdapter` не инжектит `OdnaKassaAdapter`? `R-HEX-AOUT-X4`.
   - sqlc-generated types (`db.Order`) используются только внутри `adapter/out/persistence/`, не пробрасываются в `core/`.

   ### Bootstrap (`R-HEX-BOOT-*`)
   - `bootstrap/main.go` — только wiring (конструкторы + chi.Router + http.Server + graceful shutdown), без бизнес-логики и без chi-handler'ов? `R-HEX-BOOT-1`/`R-HEX-BOOT-X1`.
   - `chi.Router` создаётся только в `bootstrap/`? `R-HEX-BOOT-X2`.
   - `recover`-middleware (`middleware.Recoverer`) подключён на уровне chi-роутера в `bootstrap/`? Не в `core/`.
   - Конфиг загружается через `mustLoadConfig()` / `envconfig`; нет `init()`-сайдэффектов в адаптерах.

   ### Архитектурные тесты (`R-HEX-TEST-*`)
   - Есть `bootstrap/architecture_test.go` (или отдельный пакет) с `packages.Load` + forbidden-imports check? `R-HEX-TEST-X1` если только code-review.
   - Тест запускается в CI как required check (`//go:build arch` или безусловно)? `R-HEX-TEST-2`.
   - Проверяются три инварианта: `core/` не импортирует фреймворки; `adapter/in/` не импортирует `adapter/out/`; `adapter/out/<A>/` не импортирует `adapter/out/<B>/`. `R-HEX-TEST-1/3`.

4. **Grep-проверки:**
   ```
   Grep "pgx|chi|go-redis|kafka-go|sqlc" internal/core/
   Grep 'var _ out\.' internal/adapter/out/   # compile-time assertions
   Grep 'init()' internal/adapter/
   Grep 'os.Exit' internal/core/
   ```

5. **Cross-check:** бизнес-логика в Handler/Command — `ucp-go-pattern-review`; DDD-инварианты/агрегат — `ucp-go-ddd-tactical-review`; apperr.Kind + edge-renderer + `httperr.Write` — `ucp-go-error-handling-review`; per-system gobreaker/retry — `ucp-go-resilience-review`.

6. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

7. **Серьёзность** (`RFF-12`):
   - **Критично** — `core/` импортирует фреймворк/pgx/sqlc-types (`R-HEX-CORE-X1/X2`), нет архитектурного теста (`R-HEX-TEST-X1`), `core/` → `adapter/*` (`R-HEX-MOD-X2`), handler инжектит репозиторий напрямую (`R-HEX-AIN-X2`), port-метод принимает/возвращает system-DTO (`R-HEX-PORT-X2`/`R-HEX-AOUT-X1`), нет recover-middleware.
   - **Предупреждение** — анемичный агрегат (`R-HEX-CORE-X3`), порт-struct вместо interface (`R-HEX-PORT-X4`), бизнес-логика в адаптере (`R-HEX-AIN-X1`/`R-HEX-AOUT-X2`), адаптеры зависят друг от друга (`R-HEX-AIN-X4`/`R-HEX-AOUT-X4`), нет compile-time assertion, архитектурный тест не в CI (`R-HEX-TEST-2`).
   - **Замечание** — user/admin-роутеры не разделены (`R-HEX-MOD-X3`), domain entity напрямую в HTTP-ответе (`R-HEX-AIN-X3`), `init()` в адаптере (нет explicit DI), маппер не вынесен в отдельную структуру.

## Что не входит

- Бизнес-операции / Handler / Command — `ucp-go-pattern-review`.
- DDD-инварианты агрегата — `ucp-go-ddd-tactical-review`.
- sqlc-запросы / pgx-пул — `ucp-go-sqlc-review`.
- Resilience внешних вызовов (gobreaker, avast/retry-go) — `ucp-go-resilience-review`.
- apperr.Kind / httperr.Write / problem+json — `ucp-go-error-handling-review`.

$ARGUMENTS
