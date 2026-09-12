---
name: ucp-go-hexagonal-review
lang: go
description: Ревью Hexagonal Architecture Go-сервиса (net/http + chi) по UCP — пакеты core/adapter/bootstrap, архитектурный тест импортов, core без chi/pgx/sqlc, порты-interface в core/port/out, chi-handler → маппер → Handler, per-system адаптеры.
when_to_use: Ревью раскладки Go-сервиса Уровня 3 — internal/core/, internal/adapter/, bootstrap/, архитектурный тест импортов, проверка стрелок зависимостей.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*) Bash(golangci-lint*)
---

# Ревью Hexagonal (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/hexagonal/spec.md` (`R-HEX-*`) и
**Go-реализации** `backend/hexagonal/references/go/implementation.md`. Изоляция — через архитектурный тест импортов
(`packages.Load` + forbidden-list) в CI; в Go нет compile-time module-isolation внутри одного репо, поэтому
enforcement — автоматический тест.

## Зависимости

- **`.claude/docs/backend/hexagonal/spec.md`** — общий контракт (`R-HEX-WHEN-*`/`MOD-*`/`CORE-*`/`PORT-*`/`AIN-*`/`AOUT-*`/`BOOT-*`/`TEST-*`).
- **`.claude/docs/backend/hexagonal/references/go/implementation.md`** — Go-реализация (пакетная раскладка, `apperr.Kind`, `errors.As`, chi-middleware, sqlc-типы, `var _ Port = (*Adapter)(nil)`).
- Парные: `backend/usecase-pattern/go/...` (Handler/Command), `backend/ddd-tactical/go/...` (rich domain), `backend/error-handling/references/go/implementation.md` (apperr, edge-renderer, recover-middleware).

## Инструкции

0. **Проверь, что гейты, обещанные требованиями, включены.** Поле **Гейт** в `spec.md` называет механизм — убедись, что он есть в проекте: `depguard` в конфиге golangci-lint и `bootstrap/architecture_test.go` в CI. Обещанный, но не включённый гейт — **отдельная находка**, и она важнее отдельного нарушения: без него граница держится только на внимательности.
   Требования с гейтом `ревью` (богатый домен, адаптер мапит а не решает, раздельные in-adapter'ы по аудиториям) не поймает никто, кроме тебя — смотри их внимательнее остальных.

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`hexagonal/core-free-of-framework`, `hexagonal/port-speaks-domain-types`), не только префикс.

2. **Скоп.** `internal/core/<bc>/**`, `internal/adapter/in/**`, `internal/adapter/out/**`, `bootstrap/main.go`, `bootstrap/architecture_test.go`, CI-конфиг, `git diff`.

3. **Прогон по подгруппам.**

   ### Структура (`R-HEX-MOD-*`)
   - Дерево `internal/core/` / `internal/adapter/in/` / `internal/adapter/out/` / `bootstrap/` присутствует? `hexagonal/module-per-part` если всё в одном пакете без enforcement.
   - `core/<bc>/` не импортирует `adapter/*`? `hexagonal/core-free-of-framework` (стрелка: `bootstrap → adapter → core`).
   - User- и admin-роутеры в отдельных пакетах (`adapter/in/http/user/`, `adapter/in/http/admin/`)? `hexagonal/in-adapter-per-audience` если совмещены.
   - Каждая внешняя система — отдельный пакет (`adapter/out/sber/`, `adapter/out/persistence/`)? `R-HEX-MOD-3/4`.
   - `bootstrap/` — единственное место, где импортируются все адаптеры вместе? `R-HEX-MOD-5`.

   ### Core (`R-HEX-CORE-*`)
   - `core/<bc>/` зависит только от stdlib (`context`, `errors`, `time`, `fmt`) и `core/apperr`? Запрещены `chi`, `pgx`, `sqlc`-types, `slog`, `go-redis`, `kafka-go`. `R-HEX-CORE-X1/X2`.
   - Структура: `aggregate/`, `value_object/`, `event/`, `port/out/`, `usecase/`, `service/` (при необходимости)? `hexagonal/core-structure`.
   - Бизнес-логика внутри агрегата (`order.Confirm(...) error`), не в `*Service`? `hexagonal/rich-domain-model`; анемия — `hexagonal/rich-domain-model`.
   - Sqlc-generated struct (`db.Order`) не используется как доменный тип в `core/`? `hexagonal/no-generated-types-in-core`.
   - HTTP-DTO (`CreateOrderRequest`) отсутствует в `core/`? `hexagonal/no-generated-types-in-core`.
   - Wiring — только через конструкторы в `bootstrap/`; нет `init()`/глобальных синглтонов; нет `var db *pgx.Pool` в `core/`. `hexagonal/di-annotations-in-core`.

   ### Ports (`R-HEX-PORT-*`)
   - Outbound-порт = `interface` в `core/<bc>/port/out/`; port-ошибки (`PaymentPortError` с `Kind() apperr.Integration`) — там же. `R-HEX-PORT-1/3`. Порт не в `adapter/out/`? `hexagonal/outbound-port-interface-in-core`.
   - Port-методы принимают/возвращают domain-типы (`Money`, `OrderID`), не DTO внешней системы (`SberRegisterRequest`)? `hexagonal/port-speaks-domain-types`/`hexagonal/port-speaks-domain-types`.
   - Порт возвращает ошибку с domain-смыслом (`*OrderNotFoundError`), не `(Order, bool)`? `hexagonal/absence-is-not-error`.
   - Порт — `interface`, не `struct`? `hexagonal/outbound-port-interface-in-core`.
   - Handler ловит `*out.PaymentPortError` через `errors.As`, не system-specific `*SberError` напрямую? `hexagonal/port-exceptions-in-core`.
   - В адаптере есть compile-time assertion `var _ out.XxxPort = (*XxxAdapter)(nil)`? `hexagonal/out-adapter-per-system`.

   ### Adapters in (`R-HEX-AIN-*`)
   - chi-handler маппит request-DTO → command через `OrderRequestMapper`, затем вызывает `UseCase.Handle`? `hexagonal/controller-dispatches-only`.
   - Маппер — отдельная структура в пакете адаптера (`order_request_mapper.go`); domain entity не сериализуется напрямую в HTTP-ответ? `hexagonal/rest-mapping-in-adapter`/`hexagonal/rest-mapping-in-adapter`.
   - Handler не инжектит репозиторий напрямую? `hexagonal/controller-dispatches-only`.
   - `adapter/in/http/` не импортирует `adapter/out/*`? `hexagonal/adapters-do-not-know-each-other`.
   - Нет бизнес-логики в handler (проверок бизнес-правил типа `if req.Amount > 100_000`)? `hexagonal/controller-dispatches-only`.
   - Ошибки из `Handle` передаются в `httperr.Write`; нет `w.WriteHeader(200)` при ошибке.

   ### Adapters out (`R-HEX-AOUT-*`)
   - Каждая внешняя система — отдельный пакет; per-system isolation. `hexagonal/out-adapter-per-system`.
   - Адаптер реализует port-interface из `core/`; маппит `domain ↔ system-DTO` в отдельной структуре-маппере (`PaymentMapper`). `R-HEX-AOUT-2/3`.
   - Port-метод не возвращает system-DTO (`SberRegisterResponse`)? `hexagonal/port-speaks-domain-types`.
   - Нет бизнес-логики в адаптере (условных переходов по domain-смыслу)? `hexagonal/adapter-maps-not-decides`.
   - Один адаптер не реализует порты разных доменов? `hexagonal/out-adapter-per-system`.
   - `SberAdapter` не инжектит `OdnaKassaAdapter`? `hexagonal/adapters-do-not-know-each-other`.
   - sqlc-generated types (`db.Order`) используются только внутри `adapter/out/persistence/`, не пробрасываются в `core/`.

   ### Bootstrap (`R-HEX-BOOT-*`)
   - `bootstrap/main.go` — только wiring (конструкторы + chi.Router + http.Server + graceful shutdown), без бизнес-логики и без chi-handler'ов? `hexagonal/bootstrap-composition-only`/`hexagonal/bootstrap-composition-only`.
   - `chi.Router` создаётся только в `bootstrap/`? `hexagonal/bootstrap-composition-only`.
   - `recover`-middleware (`middleware.Recoverer`) подключён на уровне chi-роутера в `bootstrap/`? Не в `core/`.
   - Конфиг загружается через `mustLoadConfig()` / `envconfig`; нет `init()`-сайдэффектов в адаптерах.

   ### Архитектурные тесты (`R-HEX-TEST-*`)
   - Есть `bootstrap/architecture_test.go` (или отдельный пакет) с `packages.Load` + forbidden-imports check? `hexagonal/architecture-tests-required` если только code-review.
   - Тест запускается в CI как required check (`//go:build arch` или безусловно)? `hexagonal/architecture-test-required-check`.
   - Проверяются три инварианта: `core/` не импортирует фреймворки; `adapter/in/` не импортирует `adapter/out/`; `adapter/out/<A>/` не импортирует `adapter/out/<B>/`. `R-HEX-TEST-1/3`.

4. **Grep-проверки:**
   ```
   Grep "pgx|chi|go-redis|kafka-go|sqlc" internal/core/
   Grep 'var _ out\.' internal/adapter/out/   # compile-time assertions
   Grep 'init()' internal/adapter/
   Grep 'os.Exit' internal/core/
   ```

5. **Cross-check:** бизнес-логика в Handler/Command — `ucp-go-pattern-review`; DDD-инварианты/агрегат — `ucp-go-ddd-tactical-review`; apperr.Kind + edge-renderer + `httperr.Write` — `ucp-go-error-handling-review`; per-system gobreaker/retry — `ucp-go-resilience-review`.

6. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

7. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `core/` импортирует фреймворк/pgx/sqlc-types (`R-HEX-CORE-X1/X2`), нет архитектурного теста (`hexagonal/architecture-tests-required`), `core/` → `adapter/*` (`hexagonal/core-free-of-framework`), handler инжектит репозиторий напрямую (`hexagonal/controller-dispatches-only`), port-метод принимает/возвращает system-DTO (`hexagonal/port-speaks-domain-types`/`hexagonal/port-speaks-domain-types`), нет recover-middleware.
   - **Предупреждение** — анемичный агрегат (`hexagonal/rich-domain-model`), порт-struct вместо interface (`hexagonal/outbound-port-interface-in-core`), бизнес-логика в адаптере (`hexagonal/controller-dispatches-only`/`hexagonal/adapter-maps-not-decides`), адаптеры зависят друг от друга (`hexagonal/adapters-do-not-know-each-other`/`hexagonal/adapters-do-not-know-each-other`), нет compile-time assertion, архитектурный тест не в CI (`hexagonal/architecture-test-required-check`).
   - **Замечание** — user/admin-роутеры не разделены (`hexagonal/in-adapter-per-audience`), domain entity напрямую в HTTP-ответе (`hexagonal/rest-mapping-in-adapter`), `init()` в адаптере (нет explicit DI), маппер не вынесен в отдельную структуру.

## Что не входит

- Бизнес-операции / Handler / Command — `ucp-go-pattern-review`.
- DDD-инварианты агрегата — `ucp-go-ddd-tactical-review`.
- sqlc-запросы / pgx-пул — `ucp-go-sqlc-review`.
- Resilience внешних вызовов (gobreaker, avast/retry-go) — `ucp-go-resilience-review`.
- apperr.Kind / httperr.Write / problem+json — `ucp-go-error-handling-review`.

$ARGUMENTS
