---
name: ucp-go-ddd-tactical-review
lang: go
description: Ревью доменной модели на Go (net/http + chi) по UCP DDD Tactical Patterns (требования ddd-tactical/*) — EntityBase/AggregateBase embedding, VO-immutable struct, DomainEvent interface, port в core/, sqlc+pgx/v5, shopspring/decimal.
when_to_use: Изменения в core/<bc>/{aggregate,entity,vo,event,port,service,specification}/**/*.go или в adapters/out/persistence/*.go с маппером в агрегат.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью тактических паттернов DDD (Go / net/http + chi)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/spec.md` (`R-*`)
и **Go-реализации** `backend/ddd-tactical/references/go/implementation.md`. Домен в `core/` — чистый Go без фреймворка и без ORM;
инфраструктурный слой (sqlc, pgx, chi) строго в `adapters/`.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/spec.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/references/go/implementation.md`** — Go-идиомы (EntityBase/AggregateBase embedding, VO-struct, DomainEvent-interface, sqlc+pgx, decimal).
- Парные: `backend/usecase-pattern/go/...` (граница TX/публикация событий), `backend/error-handling/references/go/implementation.md` (доменные ошибки с `apperr.Kind`).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`ddd-tactical/events-registered-by-root`, `ddd-tactical/collections-in-values-are-protected`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,vo,event,port,service,specification}/**/*.go`, `core/shared/building_blocks.go`, `git diff` на `.go` в `core/` и маппер в `adapters/out/persistence/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** встраивает `EntityBase[ID]` (или живёт внутри агрегата как приватный тип); идентификатор задан конструктором `New…`, публичного сеттера нет; equality — только через `EntityBase.Equals()`, не `==` по всем полям struct; состояние меняется бизнес-методами; ссылки на чужие агрегаты — по id (VO-обёртка над `uuid.UUID`). `==` по всем полям struct вместо `.Equals()` → `ddd-tactical/entity-equality-by-identity` (VO-семантика). Публичные сеттеры → `ddd-tactical/entity-constructor-validates`. Анемичная модель → `ddd-tactical/model-is-not-anemic`. Ссылка объектом на чужой агрегат → `ddd-tactical/no-object-references-across-aggregates`.
   - **Value Object (`R-VO-*`):** immutable struct, все поля приватны; конструктор-фабрика `New…` проверяет инварианты и возвращает `(VO, error)`; мутирующие операции возвращают новый экземпляр; equality через `==` (корректно — все поля comparable). VO с id / жизненным циклом → `ddd-tactical/value-has-no-identity`. Primitive obsession (`string` вместо `Email`, `float64` вместо `Money`) → `ddd-tactical/no-primitive-obsession`. Мутабельный slice внутри VO (`[]string tags`) → `ddd-tactical/collections-in-values-are-protected`. Деньги `float64` — нарушение (обязателен `shopspring/decimal` или `int64` в минорных единицах с явной оговоркой в доменном словаре).
   - **Aggregate Root (`R-AGG-*`):** встраивает `AggregateBase[ID]`; изменения — только через методы корня; наружу — копии коллекций (`Lines()` возвращает `[]OrderLine`, не slice указателей и не `o.lines` напрямую); один use case = один агрегат; ссылки на другие агрегаты по id. Регистрация события вне корня (в Handler, репозитории, контроллере) → `ddd-tactical/events-registered-by-root`. Возврат внутреннего slice напрямую → `ddd-tactical/aggregate-root-is-single-entry`. God aggregate (20+ методов) → `ddd-tactical/aggregate-stays-small`. Изменение чужого агрегата из метода → `ddd-tactical/transaction-boundary-equals-aggregate`.
   - **Domain Event (`R-EVT-*`):** struct с приватными полями + геттерами, реализует интерфейс `DomainEvent` (`EventID`/`OccurredAt`/`AggregateID`); имя глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`); несёт только примитивы и VO, не сам агрегат; конструктор `New…` → value (не указатель); публикуется после `Save` через `PullEvents()`. Публичные поля, изменяемые снаружи → `ddd-tactical/event-is-immutable-record`. Ссылка на агрегат/Entity в событии → `ddd-tactical/event-carries-business-context`. Публикация из Handler/контроллера вместо корня → `ddd-tactical/events-published-after-save`. Критичные эффекты доставляются горутиной after-commit (теряются при крэше) → `ddd-tactical/no-after-commit-for-critical-effects` (нужен Outbox в той же транзакции через sqlc).
   - **Repository (`R-REP-*`):** порт — interface в `core/<bc>/port/`, методы в терминах домена, возвращает агрегат; реализация в `adapters/out/persistence/` (sqlc + pgx/v5); один репозиторий = один корень; `Save` сохраняет агрегат в транзакции (`pool.Begin`/`Commit`/`defer Rollback`); `PullEvents()` — после `Commit`. Возврат `sqlcgen.Order` (row-struct) наружу → `ddd-tactical/repository-speaks-domain`. Методы под одну таблицу (`UpdateStatusInDB`) → `ddd-tactical/repository-speaks-domain`. Specification, генерирующая SQL-предикат в порте → `ddd-tactical/specification-is-not-a-query-builder` (read-side выносится в отдельный ViewRepository, cross-ref `usecase-pattern/reads-via-read-model`).
   - **Domain Service (`R-DS-*`):** только если логика касается ≥ 2 агрегатов и не помещается в один корень; stateless struct; конструктор принимает только доменные зависимости (не репозитории, не HTTP-клиенты). Загрузка из репозитория, транзакции, публикация событий в Domain Service → `ddd-tactical/domain-service-only-across-aggregates` (это слой Application). Domain Service как свалка всей бизнес-логики → `ddd-tactical/domain-service-only-across-aggregates`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory вводится только когда конструктор не справляется (сборка из нескольких источников, выбор подтипа, генерация ID); возвращает `(*Aggregate, error)`, невалидный агрегат не возвращается (`ddd-tactical/factory-only-when-needed` — Factory ради Factory). Specification — struct с методом `IsSatisfiedBy(candidate T) bool`; вводится только при ≥ 2 мест использования или нужна комбинация (`ddd-tactical/specification-is-not-a-query-builder` — SQL-предикат; `ddd-tactical/specification-for-reuse` — один `if` в одном месте).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (`core/order/…`), не по типу (`core/entity/…`); `core/<bc>/` не импортирует `adapters/*`, chi, pgx, sqlc, Prometheus. Enforce через `depguard` или `go-arch-lint`: `core` → `adapters` — запрещено. Пакеты на верхнем уровне `core/` (`entity/`, `service/`, `repository/`) → `ddd-tactical/packages-grouped-by-domain`. Фреймворк/адаптер в `core/` → `ddd-tactical/packages-grouped-by-domain`.

4. **Cross-check:** граница TX/UoW и публикация событий — `ucp-go-pattern-review` / cross-ref `usecase-pattern/publish-events-after-save`; реализация репозитория (sqlc-маппер) — `ucp-go-cqrs-review`; доменные ошибки с `apperr.Kind` — `ucp-go-error-handling-review`; типы колонок — `ucp-pg-schema-review`. Рекомендуй `depguard` / `go-arch-lint` в CI, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `==` по всем полям struct вместо `.Equals()` на Entity (`ddd-tactical/entity-equality-by-identity`), ссылка объектом на чужой агрегат (`ddd-tactical/no-object-references-across-aggregates`), мутабельный slice в VO (`ddd-tactical/collections-in-values-are-protected`), деньги `float64`, событие вне корня (`ddd-tactical/events-registered-by-root`), возврат `sqlcgen`-row наружу (`ddd-tactical/repository-speaks-domain`), ссылка на агрегат в событии (`ddd-tactical/event-carries-business-context`), фреймворк/адаптер в `core/` (`ddd-tactical/packages-grouped-by-domain`).
   - **Предупреждение** — анемичная модель (`ddd-tactical/model-is-not-anemic`), публичные сеттеры (`ddd-tactical/entity-constructor-validates`), возврат внутреннего slice (`ddd-tactical/aggregate-root-is-single-entry`), оркестрация в Domain Service (`ddd-tactical/domain-service-only-across-aggregates`), публикация события из Handler/контроллера (`ddd-tactical/events-published-after-save`), критичные эффекты горутиной after-commit (`ddd-tactical/no-after-commit-for-critical-effects`), пакеты по типу на уровне `core/` (`ddd-tactical/packages-grouped-by-domain`).
   - **Замечание** — primitive obsession (`ddd-tactical/no-primitive-obsession`), Factory/Specification ради абстракции (`ddd-tactical/factory-only-when-needed`/`ddd-tactical/specification-for-reuse`), имя события не в прошедшем времени (`ddd-tactical/event-named-in-past-tense`), отсутствие `depguard`/`go-arch-lint` в CI.

## Что не входит

- Граница транзакции/UoW и бизнес-операции — `ucp-go-pattern-review`. Реализация маппера sqlc — `ucp-go-cqrs-review`.
- Доменные ошибки с `apperr.Kind` — `ucp-go-error-handling-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
