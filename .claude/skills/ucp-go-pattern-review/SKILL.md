---
name: ucp-go-pattern-review
lang: go
description: Ревью UseCase + Handler в Go-сервисе (net/http + chi) по UCP (коды R-UC-*, R-HND-*, R-DSP-*, R-LAY-*) — immutable struct UseCase, stateless Handler с UnitOfWork, Dispatcher через reflect, тонкий chi-контроллер, sqlc-маппер, порты-interface в core/.
when_to_use: Изменения в *_handler.go, usecases.go, adapters/in/http/, app/dispatcher/ или core/*/port/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью UseCase + Handler (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/usecase-pattern/usecase-pattern-rules.md`
(`R-*`, коды едины с Java/Python) и его **Go-реализации** `backend/usecase-pattern/go/usecase-pattern-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/go/usecase-pattern-style-guide.md`** — Go-реализация.
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/ddd-tactical-rules.md`, `backend/pg-types/pg-types-rules.md`.

## Инструкции

1. **Прочти** контракт (коды) и Go-style-guide (реализация). Цитируй конкретные коды (`R-HND-X2`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/usecases.go`, `**/*usecases*.go` — `R-UC-*`.
   - `**/*_handler.go` (в `core/`) — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**` — `R-DSP-*`.
   - `app/dispatcher/` — `R-DSP-1/2`.
   - `core/**/port/**` — `R-HEX-3`.
   - `git diff` на изменённые `.go`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — plain struct без методов-логики; реализует маркер `Command[R]` или `Query[R]` через приватный метод? — `R-UC-1/2`.
   - Имя выражает операцию (`CreateOrder`, `FindOrderByID`), один struct = одна операция? — `R-UC-3`. Два use case в одном struct → `R-UC-X2`. Логика/вычисления в struct-методе → `R-UC-X1`.
   - Mutable-поля (pointer-slice без copy) или экспортированные сеттеры — `R-UC-X3`. Команда без `VoidResult`-обёртки там, где контроллер ждёт `R` → `R-UC-X4`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — `*NameHandler` с методом `Handle(ctx context.Context, uc UC) (R, error)`, один UseCase, deps через `New*`-конструктор, поля приватные? — `R-HND-1/4/5`.
   - Граница транзакции на Handler: команда через `uow.Do(ctx, func(ctx) error {...})`, запрос read-only без UoW? — `R-HND-3`, `R-TX-1`.
   - Handler зовёт другой Handler напрямую (не через dispatcher / Step) — `R-HND-X1`.
   - Наружу вылетает `pgconn.PgError`/`net.Error`/`context.DeadlineExceeded` без маппинга в доменную — `R-HND-X2` (cross-ref `R-ERR-WHERE-2b`).
   - Поля Handler-а меняются между вызовами (кэш, счётчик) — `R-HND-X3`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.Dispatch(ctx, uc)`, не Handler напрямую? — `R-DSP-1`.
   - Один `Dispatcher` на приложение, регистрация через `dispatcher.Register[UC, R]` при сборке в `app/di.go`? — `R-DSP-2`.
   - Endpoint тонкий: JSON-decode → UseCase → dispatch → JSON-encode → HTTP-код? Логика/обращение к репозиторию в контроллере → `R-DSP-X1`.
   - `*http.Request`/`auth.Principal`-объект уходит в UseCase вместо `UserID`/`TenantID` — `R-DSP-X2`; должно быть `auth.PrincipalFromCtx(r.Context()).UserID`.

   ### `R-CQRS-*`
   - Команда реализует `Command[R]` (имя-глагол: `CreateOrder`, `CancelOrder`); запрос — `Query[R]` (`FindOrderByID`, `SearchOrders`, `GetCustomerBalance`)? — `R-CQRS-1/3`.
   - Команда открывает read-write транзакцию через `UnitOfWork`; запрос — read-only без `UoW.Do`? — `R-CQRS-2`.
   - Чтения возвращают view-struct (`OrderView`, `OrderPage`) через `ViewRepository`; запись — через `OrderRepository` с агрегатом? — `R-CQRS-4`.
   - Команда возвращает `OrderView` со связями — `R-CQRS-X1`; только `OrderID`/`VoidResult`. Запрос пишет (обновляет счётчик, last_seen) — `R-CQRS-X2`.

   ### `R-LAY-*`
   - На входе UseCase — поля из API-DTO или явные VO (`OrderItemInput`), не sqlc-struct (`db.Order`)? — `R-LAY-1`.
   - На выходе UseCase — read-struct (`OrderView`) из `core/`; sqlc-struct в `adapters/out/persistence/`? — `R-LAY-2`.
   - Маппинг — явная функция в том слое, которому принадлежит (`toOrderView(row db.GetOrderRow)` в `adapters/out/`)? — `R-LAY-3`.
   - sqlc-struct (`db.Order`) уходит напрямую в JSON-ответ через контроллер — `R-LAY-X1`. «Маппинг» через `json.Marshal`→`json.Unmarshal` или `reflect`-копирование — `R-LAY-X3`. Доменный агрегат (`core/order/Order`) утекает в HTTP-ответ — `R-LAY-DDD`.

   ### `R-HEX-*`
   - Раскладка пакетов: `core/<bc>/` (UseCase + Handler + Domain + `port/`), `adapters/in/http/`, `adapters/out/persistence/`, `app/di.go`? — `R-HEX-1`.
   - `core/` не импортирует `net/http`, `pgx`, `chi`, `kafka-go`, `go-redis`? Проверить `Grep` по `import` в `core/**/*.go` — `R-HEX-2`. Нарушение → `R-HEX-X2`.
   - Порты — `interface` в `core/<bc>/port/`; реализация в `adapters/out/`? — `R-HEX-3`. Прямой `pgxpool.Pool` в `core/` → `R-HEX-X1`.
   - Один и тот же Handler вызывается из `adapters/in/http/` и `adapters/in/kafka/` (если есть consumer) — без дублирования Handler? — `R-HEX-4`.

   ### `R-STEP-*`
   - Step реализует `Step[I, O]` с методом `Execute(ctx, in I) (O, error)`, stateless? — `R-STEP-1`.
   - Step введён только если логика нужна ≥ 2 Handler-ам — `R-STEP-2`. Step внутри Step → `R-STEP-X1`. Поля Step-а меняются между вызовами → `R-STEP-X2`.

4. **Cross-check:** инфра→домен в адаптере → `ucp-go-error-handling-review` (`R-ERR-WHERE-2b`); DDL/миграции → `ucp-pg-schema-review`; доменная модель → `ucp-go-ddd-tactical-review`. Рекомендуй `go-arch-lint` или import-тест, если ограничений на `core/` нет.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — логика в UseCase-struct (`R-UC-X1`), Handler→Handler напрямую (`R-HND-X1`), endpoint с БД/логикой (`R-DSP-X1`), `core/` импортирует `pgx`/`chi` (`R-HEX-X2`), TX граница на репозитории (`R-TX-1`), sqlc-struct в JSON-ответе (`R-LAY-X1`), инфра-ошибка наружу из Handler (`R-HND-X2`).
   - **Предупреждение** — mutable UseCase (`R-UC-X3`), `*http.Request` в UseCase (`R-DSP-X2`), запрос пишет (`R-CQRS-X2`), `json.Marshal`-маппинг (`R-LAY-X3`), Handler stateful (`R-HND-X3`).
   - **Замечание** — нет явного View-struct для запроса, Step-кандидат не выделен, имя не выражает операцию, нет enforce-теста на импорты `core/`.

## Что не входит

- Обработка ошибок (apperr.Kind, `%w`, problem+json) — `ucp-go-error-handling-review`.
- Валидация входа (go-playground/validator constraints) — `ucp-go-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-go-ddd-tactical-review`.
- Retry/CB-конфигурация (avast/retry-go, gobreaker) — `ucp-go-resilience-review`.

$ARGUMENTS
