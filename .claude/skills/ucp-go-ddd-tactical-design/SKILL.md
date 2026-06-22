---
name: ucp-go-ddd-tactical-design
lang: go
description: Спроектировать доменную модель на Go (net/http + chi) по UCP DDD Tactical Patterns (коды R-AGG-*, R-VO-*, R-EVT-*, R-REP-*) — EntityBase/AggregateBase embedding, VO-immutable struct, DomainEvent interface, port в core/, sqlc+pgx/v5, decimal.
when_to_use: Триггеры — «агрегат X на Go», «доменная модель для Y», «value object Money на Go». При моделировании BC или агрегата на Уровне 3.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# DDD Tactical Patterns — проектирование (Go / net/http + chi)

Ты проектируешь доменную модель согласно **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md`
(`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`) и его **Go-реализации** `backend/ddd-tactical/go/ddd-tactical-style-guide.md`.
Домен живёт в `core/` **без фреймворка и без ORM** — чистый Go + stdlib; инфраструктурный слой (sqlc, pgx, chi) строго в `adapters/`.

## Инструкции

1. **Прочитай** контракт `backend/ddd-tactical/ddd-tactical-rules.md` + Go-style-guide `backend/ddd-tactical/go/ddd-tactical-style-guide.md`. Коды `R-*` обязательны; цитируй их в **design-обосновании**, не в комментариях кода. Связанные: `backend/usecase-pattern/go/...` (Handler/порты), `backend/error-handling/go/error-handling-style-guide.md` (доменные ошибки с `apperr.Kind`).

2. **Базовые типы.** Если в `core/shared/building_blocks.go` нет `EntityBase[ID]`/`AggregateBase[ID]`/интерфейса `DomainEvent` — создай их по образцу из style-guide (embedding-реализация); не тащи из adapter-слоя.

3. **Уточни модель:** Bounded Context и пакет (`core/<bc>/`); корень агрегата и защищаемый инвариант; внутренние Entity; Value Objects (бьём primitive obsession — `Money`/`Email`/`OrderID`); доменные события (глагол прошедшего времени); ссылки на другие агрегаты — по id (VO-обёртка над `uuid.UUID`); оправданы ли Factory/Domain Service/Specification (по умолчанию нет).

4. **Произведи код** (Go 1.22+; gofmt; без комментариев; коды правил в код не цитируй):
   - **Value Object** — immutable struct, все поля приватны; конструктор-фабрика `New…(…)` проверяет инварианты и возвращает `(VO, error)`; мутирующие операции возвращают новый экземпляр; equality через `==` (все поля comparable) (`R-VO-*`). Деньги — `shopspring/decimal`, никогда `float64`.
   - **Entity** — struct встраивает `EntityBase[ID]` (или живёт внутри агрегата как приватный тип); конструктор `New…` возвращает `(*Entity, error)`; бизнес-методы меняют состояние, публичных сеттеров нет; equality — `EntityBase.Equals()`, не `==` по всем полям (`R-ENT-*`).
   - **Aggregate Root** — struct встраивает `AggregateBase[ID]`; мутирующие методы держат инварианты и вызывают `a.registerEvent(…)`; наружу — копии коллекций (`Lines()` возвращает `[]OrderLine`, не `[]*OrderLine`) (`R-AGG-*`).
   - **Domain Event** — struct с приватными полями реализует интерфейс `DomainEvent` (`EventID`/`OccurredAt`/`AggregateID`); имя глаголом в прошедшем времени (`OrderConfirmed`); конструктор `New…` → value (не указатель); несёт только примитивы/VO (`R-EVT-*`).
   - **Repository** — interface в `core/<bc>/port/`, методы в доменных терминах, возвращает агрегат (`R-REP-*`); реализация — `adapters/out/persistence/` (sqlc + pgx/v5); `Save` в транзакции; `PullEvents()` вызывается после `Commit` для публикации.
   - **Domain Service / Factory / Specification** — только если оправдано; укажи обоснование.

5. **Раскладка по домену** (`R-MOD-*`): `core/<bc>/{aggregate,entity,vo,event,port,service,specification,usecase}/`. Enforce изоляции: `core/<bc>/` не импортирует `adapters/*`, chi, pgx, sqlc, Prometheus — предложи `depguard` или `go-arch-lint` (`R-MOD-2`). Структура импортов: `core` < `adapters` < `app`.

6. **Ошибки доменного слоя** — типизированные struct-значения с `Kind() apperr.Domain`; заворачиваются через `fmt.Errorf("…: %w", err)` при подъёме; не `return nil` при фактической ошибке (cross-ref `backend/error-handling/go/error-handling-style-guide.md`).

7. **Самопроверка** (чек-лист §10 Go style-guide) + предложи `ucp-go-ddd-tactical-review`. Persistence агрегата — `ucp-go-sqlc-design` (если скилл установлен).

## Антипаттерны, которые НЕ генерировать

- Entity с equality по всем полям struct (`==`) — это VO-семантика (`R-ENT-X1/X2`); публичные сеттеры (`R-ENT-X3`); ссылка на агрегат объектом вместо id (`R-ENT-X4`); анемичная модель (`R-ENT-X5`).
- VO с id или жизненным циклом (`R-VO-X1`); primitive obsession: `string` вместо `Email` (`R-VO-X2`); мутабельный slice внутри VO (`R-VO-X3`); деньги `float64`.
- Регистрация события вне корня — в Handler, репозитории, контроллере (`R-AGG-X4`); возврат внутреннего slice наружу (`R-AGG-X2`); изменение чужого агрегата напрямую (`R-AGG-X3`).
- Событие с публичными изменяемыми полями (`R-EVT-X1`); ссылка на агрегат/Entity в событии (`R-EVT-X2`); публикация из контроллера/Handler (`R-EVT-X3`); after-commit-горутина для критичных эффектов (`R-EVT-X4`) — Outbox в той же транзакции.
- Возврат sqlc row-struct наружу из репозитория (`R-REP-X1`); методы под таблицу (`UpdateStatusInDB`) вместо доменных терминов (`R-REP-X2`); Specification как SQL-предикат-строитель в порте (`R-REP-X3`).
- Фреймворк в `core/` (chi, pgx, sqlc, Prometheus) (`R-MOD-2`); пакеты по типу (`core/entity/`), не по BC (`core/order/…`) (`R-MOD-1`).
- Domain Service с загрузкой из репозитория, транзакциями или публикацией событий (`R-DS-X1`).

После работы скилла — обязательно `ucp-go-ddd-tactical-review`.

$ARGUMENTS
