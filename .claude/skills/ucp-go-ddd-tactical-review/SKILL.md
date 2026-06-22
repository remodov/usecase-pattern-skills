---
name: ucp-go-ddd-tactical-review
lang: go
description: Ревью доменной модели на Go (net/http + chi) по UCP DDD Tactical Patterns (коды R-AGG-*, R-VO-*, R-EVT-*, R-REP-*) — EntityBase/AggregateBase embedding, VO-immutable struct, DomainEvent interface, port в core/, sqlc+pgx/v5, shopspring/decimal.
when_to_use: Изменения в core/<bc>/{aggregate,entity,vo,event,port,service,specification}/**/*.go или в adapters/out/persistence/*.go с маппером в агрегат.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью тактических паттернов DDD (Go / net/http + chi)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md` (`R-*`)
и **Go-реализации** `backend/ddd-tactical/go/ddd-tactical-style-guide.md`. Домен в `core/` — чистый Go без фреймворка и без ORM;
инфраструктурный слой (sqlc, pgx, chi) строго в `adapters/`.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/go/ddd-tactical-style-guide.md`** — Go-идиомы (EntityBase/AggregateBase embedding, VO-struct, DomainEvent-interface, sqlc+pgx, decimal).
- Парные: `backend/usecase-pattern/go/...` (граница TX/публикация событий), `backend/error-handling/go/error-handling-style-guide.md` (доменные ошибки с `apperr.Kind`).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-AGG-X4`, `R-VO-X3`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,vo,event,port,service,specification}/**/*.go`, `core/shared/building_blocks.go`, `git diff` на `.go` в `core/` и маппер в `adapters/out/persistence/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** встраивает `EntityBase[ID]` (или живёт внутри агрегата как приватный тип); идентификатор задан конструктором `New…`, публичного сеттера нет; equality — только через `EntityBase.Equals()`, не `==` по всем полям struct; состояние меняется бизнес-методами; ссылки на чужие агрегаты — по id (VO-обёртка над `uuid.UUID`). `==` по всем полям struct вместо `.Equals()` → `R-ENT-X2` (VO-семантика). Публичные сеттеры → `R-ENT-X3`. Анемичная модель → `R-ENT-X5`. Ссылка объектом на чужой агрегат → `R-ENT-X4`.
   - **Value Object (`R-VO-*`):** immutable struct, все поля приватны; конструктор-фабрика `New…` проверяет инварианты и возвращает `(VO, error)`; мутирующие операции возвращают новый экземпляр; equality через `==` (корректно — все поля comparable). VO с id / жизненным циклом → `R-VO-X1`. Primitive obsession (`string` вместо `Email`, `float64` вместо `Money`) → `R-VO-X2`. Мутабельный slice внутри VO (`[]string tags`) → `R-VO-X3`. Деньги `float64` — нарушение (обязателен `shopspring/decimal` или `int64` в минорных единицах с явной оговоркой в доменном словаре).
   - **Aggregate Root (`R-AGG-*`):** встраивает `AggregateBase[ID]`; изменения — только через методы корня; наружу — копии коллекций (`Lines()` возвращает `[]OrderLine`, не slice указателей и не `o.lines` напрямую); один use case = один агрегат; ссылки на другие агрегаты по id. Регистрация события вне корня (в Handler, репозитории, контроллере) → `R-AGG-X4`. Возврат внутреннего slice напрямую → `R-AGG-X2`. God aggregate (20+ методов) → `R-AGG-X1`. Изменение чужого агрегата из метода → `R-AGG-X3`.
   - **Domain Event (`R-EVT-*`):** struct с приватными полями + геттерами, реализует интерфейс `DomainEvent` (`EventID`/`OccurredAt`/`AggregateID`); имя глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`); несёт только примитивы и VO, не сам агрегат; конструктор `New…` → value (не указатель); публикуется после `Save` через `PullEvents()`. Публичные поля, изменяемые снаружи → `R-EVT-X1`. Ссылка на агрегат/Entity в событии → `R-EVT-X2`. Публикация из Handler/контроллера вместо корня → `R-EVT-X3`. Критичные эффекты доставляются горутиной after-commit (теряются при крэше) → `R-EVT-X4` (нужен Outbox в той же транзакции через sqlc).
   - **Repository (`R-REP-*`):** порт — interface в `core/<bc>/port/`, методы в терминах домена, возвращает агрегат; реализация в `adapters/out/persistence/` (sqlc + pgx/v5); один репозиторий = один корень; `Save` сохраняет агрегат в транзакции (`pool.Begin`/`Commit`/`defer Rollback`); `PullEvents()` — после `Commit`. Возврат `sqlcgen.Order` (row-struct) наружу → `R-REP-X1`. Методы под одну таблицу (`UpdateStatusInDB`) → `R-REP-X2`. Specification, генерирующая SQL-предикат в порте → `R-REP-X3` (read-side выносится в отдельный ViewRepository, cross-ref `R-CQRS-4`).
   - **Domain Service (`R-DS-*`):** только если логика касается ≥ 2 агрегатов и не помещается в один корень; stateless struct; конструктор принимает только доменные зависимости (не репозитории, не HTTP-клиенты). Загрузка из репозитория, транзакции, публикация событий в Domain Service → `R-DS-X1` (это слой Application). Domain Service как свалка всей бизнес-логики → `R-DS-X2`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory вводится только когда конструктор не справляется (сборка из нескольких источников, выбор подтипа, генерация ID); возвращает `(*Aggregate, error)`, невалидный агрегат не возвращается (`R-FAC-X1` — Factory ради Factory). Specification — struct с методом `IsSatisfiedBy(candidate T) bool`; вводится только при ≥ 2 мест использования или нужна комбинация (`R-SPEC-X1` — SQL-предикат; `R-SPEC-X2` — один `if` в одном месте).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (`core/order/…`), не по типу (`core/entity/…`); `core/<bc>/` не импортирует `adapters/*`, chi, pgx, sqlc, Prometheus. Enforce через `depguard` или `go-arch-lint`: `core` → `adapters` — запрещено. Пакеты на верхнем уровне `core/` (`entity/`, `service/`, `repository/`) → `R-MOD-1`. Фреймворк/адаптер в `core/` → `R-MOD-2`.

4. **Cross-check:** граница TX/UoW и публикация событий — `ucp-go-pattern-review` / cross-ref `R-TX-3`; реализация репозитория (sqlc-маппер) — `ucp-go-cqrs-review`; доменные ошибки с `apperr.Kind` — `ucp-go-error-handling-review`; типы колонок — `ucp-pg-schema-review`. Рекомендуй `depguard` / `go-arch-lint` в CI, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `==` по всем полям struct вместо `.Equals()` на Entity (`R-ENT-X2`), ссылка объектом на чужой агрегат (`R-ENT-X4`), мутабельный slice в VO (`R-VO-X3`), деньги `float64`, событие вне корня (`R-AGG-X4`), возврат `sqlcgen`-row наружу (`R-REP-X1`), ссылка на агрегат в событии (`R-EVT-X2`), фреймворк/адаптер в `core/` (`R-MOD-2`).
   - **Предупреждение** — анемичная модель (`R-ENT-X5`), публичные сеттеры (`R-ENT-X3`), возврат внутреннего slice (`R-AGG-X2`), оркестрация в Domain Service (`R-DS-X1`), публикация события из Handler/контроллера (`R-EVT-X3`), критичные эффекты горутиной after-commit (`R-EVT-X4`), пакеты по типу на уровне `core/` (`R-MOD-1`).
   - **Замечание** — primitive obsession (`R-VO-X2`), Factory/Specification ради абстракции (`R-FAC-X1`/`R-SPEC-X2`), имя события не в прошедшем времени (`R-EVT-2`), отсутствие `depguard`/`go-arch-lint` в CI.

## Что не входит

- Граница транзакции/UoW и бизнес-операции — `ucp-go-pattern-review`. Реализация маппера sqlc — `ucp-go-cqrs-review`.
- Доменные ошибки с `apperr.Kind` — `ucp-go-error-handling-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
