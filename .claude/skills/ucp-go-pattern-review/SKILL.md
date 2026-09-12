---
name: ucp-go-pattern-review
lang: go
description: Ревью UseCase + Handler в Go-сервисе (net/http + chi) по UCP (требования usecase-pattern/*) — immutable struct UseCase, stateless Handler с UnitOfWork, Dispatcher через reflect, тонкий chi-контроллер, sqlc-маппер, порты-interface в core/.
when_to_use: Изменения в *_handler.go, usecases.go, adapters/in/http/, app/dispatcher/ или core/*/port/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью UseCase + Handler (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/usecase-pattern/spec.md`
(`R-*`, коды едины с Java/Python) и его **Go-реализации** `backend/usecase-pattern/references/go/implementation.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/spec.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/references/go/implementation.md`** — Go-реализация.
- Парные: `backend/error-handling/spec.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/spec.md`, `backend/pg-types/spec.md`.

## Инструкции

1. **Прочти** контракт и `references/go/implementation.md` (реализация). Цитируй конкретные коды (`usecase-pattern/infrastructure-errors-become-domain`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/usecases.go`, `**/*usecases*.go` — `R-UC-*`.
   - `**/*_handler.go` (в `core/`) — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**` — `R-DSP-*`.
   - `app/dispatcher/` — `R-DSP-1/2`.
   - `core/**/port/**` — `hexagonal/outbound-port-interface-in-core`.
   - `git diff` на изменённые `.go`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — plain struct без методов-логики; реализует маркер `Command[R]` или `Query[R]` через приватный метод? — `R-UC-1/2`.
   - Имя выражает операцию (`CreateOrder`, `FindOrderByID`), один struct = одна операция? — `usecase-pattern/one-usecase-one-operation`. Два use case в одном struct → `usecase-pattern/one-usecase-one-operation`. Логика/вычисления в struct-методе → `usecase-pattern/usecase-is-immutable-carrier`.
   - Mutable-поля (pointer-slice без copy) или экспортированные сеттеры — `usecase-pattern/usecase-is-immutable-carrier`. Команда без `VoidResult`-обёртки там, где контроллер ждёт `R` → `usecase-pattern/explicit-result-type`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — `*NameHandler` с методом `Handle(ctx context.Context, uc UC) (R, error)`, один UseCase, deps через `New*`-конструктор, поля приватные? — `R-HND-1/4/5`.
   - Граница транзакции на Handler: команда через `uow.Do(ctx, func(ctx) error {...})`, запрос read-only без UoW? — `usecase-pattern/transaction-boundary-on-handler`, `usecase-pattern/transaction-boundary-on-handler`.
   - Handler зовёт другой Handler напрямую (не через dispatcher / Step) — `usecase-pattern/handlers-do-not-call-handlers`.
   - Наружу вылетает `pgconn.PgError`/`net.Error`/`context.DeadlineExceeded` без маппинга в доменную — `usecase-pattern/infrastructure-errors-become-domain` (cross-ref `R-ERR-WHERE-2b`).
   - Поля Handler-а меняются между вызовами (кэш, счётчик) — `usecase-pattern/handler-is-stateless`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.Dispatch(ctx, uc)`, не Handler напрямую? — `usecase-pattern/entry-calls-dispatcher`.
   - Один `Dispatcher` на приложение, регистрация через `dispatcher.Register[UC, R]` при сборке в `app/di.go`? — `usecase-pattern/single-dispatcher`.
   - Endpoint тонкий: JSON-decode → UseCase → dispatch → JSON-encode → HTTP-код? Логика/обращение к репозиторию в контроллере → `usecase-pattern/controller-maps-and-dispatches`.
   - `*http.Request`/`auth.Principal`-объект уходит в UseCase вместо `UserID`/`TenantID` — `usecase-pattern/no-transport-objects-in-usecase`; должно быть `auth.PrincipalFromCtx(r.Context()).UserID`.

   ### `R-CQRS-*`
   - Команда реализует `Command[R]` (имя-глагол: `CreateOrder`, `CancelOrder`); запрос — `Query[R]` (`FindOrderByID`, `SearchOrders`, `GetCustomerBalance`)? — `R-CQRS-1/3`.
   - Команда открывает read-write транзакцию через `UnitOfWork`; запрос — read-only без `UoW.Do`? — `usecase-pattern/transaction-boundary-on-handler`.
   - Чтения возвращают view-struct (`OrderView`, `OrderPage`) через `ViewRepository`; запись — через `OrderRepository` с агрегатом? — `usecase-pattern/reads-via-read-model`.
   - Команда возвращает `OrderView` со связями — `usecase-pattern/command-returns-minimum`; только `OrderID`/`VoidResult`. Запрос пишет (обновляет счётчик, last_seen) — `usecase-pattern/query-does-not-mutate`.

   ### `R-LAY-*`
   - На входе UseCase — поля из API-DTO или явные VO (`OrderItemInput`), не sqlc-struct (`db.Order`)? — `usecase-pattern/layer-models-do-not-leak`.
   - На выходе UseCase — read-struct (`OrderView`) из `core/`; sqlc-struct в `adapters/out/persistence/`? — `usecase-pattern/layer-models-do-not-leak`.
   - Маппинг — явная функция в том слое, которому принадлежит (`toOrderView(row db.GetOrderRow)` в `adapters/out/`)? — `usecase-pattern/explicit-mapper-between-layers`.
   - sqlc-struct (`db.Order`) уходит напрямую в JSON-ответ через контроллер — `usecase-pattern/layer-models-do-not-leak`. «Маппинг» через `json.Marshal`→`json.Unmarshal` или `reflect`-копирование — `usecase-pattern/explicit-mapper-between-layers`. Доменный агрегат (`core/order/Order`) утекает в HTTP-ответ — `usecase-pattern/layer-models-do-not-leak`.

   ### `R-HEX-*`
   - Раскладка пакетов: `core/<bc>/` (UseCase + Handler + Domain + `port/`), `adapters/in/http/`, `adapters/out/persistence/`, `app/di.go`? — `hexagonal/module-per-part`.
   - `core/` не импортирует `net/http`, `pgx`, `chi`, `kafka-go`, `go-redis`? Проверить `Grep` по `import` в `core/**/*.go` — `hexagonal/core-free-of-framework`. Нарушение → `hexagonal/core-free-of-framework`.
   - Порты — `interface` в `core/<bc>/port/`; реализация в `adapters/out/`? — `hexagonal/outbound-port-interface-in-core`. Прямой `pgxpool.Pool` в `core/` → `hexagonal/outbound-port-interface-in-core`.
   - Один и тот же Handler вызывается из `adapters/in/http/` и `adapters/in/kafka/` (если есть consumer) — без дублирования Handler? — `usecase-pattern/one-usecase-many-inbound-adapters`.

   ### `R-STEP-*`
   - Step реализует `Step[I, O]` с методом `Execute(ctx, in I) (O, error)`, stateless? — `usecase-pattern/step-for-reuse-only`.
   - Step введён только если логика нужна ≥ 2 Handler-ам — `usecase-pattern/step-for-reuse-only`. Step внутри Step → `usecase-pattern/steps-flat-and-stateless`. Поля Step-а меняются между вызовами → `usecase-pattern/steps-flat-and-stateless`.

4. **Cross-check:** инфра→домен в адаптере → `ucp-go-error-handling-review` (`R-ERR-WHERE-2b`); DDL/миграции → `ucp-pg-schema-review`; доменная модель → `ucp-go-ddd-tactical-review`. Рекомендуй `go-arch-lint` или import-тест, если ограничений на `core/` нет.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — логика в UseCase-struct (`usecase-pattern/usecase-is-immutable-carrier`), Handler→Handler напрямую (`usecase-pattern/handlers-do-not-call-handlers`), endpoint с БД/логикой (`usecase-pattern/controller-maps-and-dispatches`), `core/` импортирует `pgx`/`chi` (`hexagonal/core-free-of-framework`), TX граница на репозитории (`usecase-pattern/transaction-boundary-on-handler`), sqlc-struct в JSON-ответе (`usecase-pattern/layer-models-do-not-leak`), инфра-ошибка наружу из Handler (`usecase-pattern/infrastructure-errors-become-domain`).
   - **Предупреждение** — mutable UseCase (`usecase-pattern/usecase-is-immutable-carrier`), `*http.Request` в UseCase (`usecase-pattern/no-transport-objects-in-usecase`), запрос пишет (`usecase-pattern/query-does-not-mutate`), `json.Marshal`-маппинг (`usecase-pattern/explicit-mapper-between-layers`), Handler stateful (`usecase-pattern/handler-is-stateless`).
   - **Замечание** — нет явного View-struct для запроса, Step-кандидат не выделен, имя не выражает операцию, нет enforce-теста на импорты `core/`.

## Что не входит

- Обработка ошибок (apperr.Kind, `%w`, problem+json) — `ucp-go-error-handling-review`.
- Валидация входа (go-playground/validator constraints) — `ucp-go-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-go-ddd-tactical-review`.
- Retry/CB-конфигурация (avast/retry-go, gobreaker) — `ucp-go-resilience-review`.

$ARGUMENTS
