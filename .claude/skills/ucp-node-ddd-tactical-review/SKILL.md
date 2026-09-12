---
name: ucp-node-ddd-tactical-review
lang: node
description: Ревью доменного кода на чистом TypeScript (core/) по UCP DDD Tactical Patterns (требования ddd-tactical/*) — Entity с identity-equals, frozen VO, события в корне агрегата, порт + Symbol-токен, деньги Big.js, core/ без NestJS/TypeORM.
when_to_use: Ревью агрегатов, VO, доменных событий, портов-репозиториев в core/ NestJS-сервиса.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тактических паттернов DDD (Node / чистый core)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/spec.md` (`R-*`)
и **Node-реализации** `backend/ddd-tactical/references/node/implementation.md`. Домен в `core/` — чистый TypeScript без фреймворка.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/spec.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/references/node/implementation.md`** — Node-идиомы (identity-`equals()`, `ValueObject.components()`, branded ids, dependency-cruiser).
- Парные: `backend/usecase-pattern/node/...` (граница TX/события), `backend/node/typeorm/spec.md` (реализация репозитория).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй конкретные коды (`ddd-tactical/events-registered-by-root`, `ddd-tactical/collections-in-values-are-protected`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,value-object,event,port,service,specification}/**`, `core/shared/building-blocks.ts`, `git diff` на `.ts` в `core/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** наследует `Entity<ID>`; id `readonly`, без сеттера; `equals()` не переопределён в наследнике; сравнение через `a.equals(b)`, не `===`; состояние меняется бизнес-методами, не сеттерами; ссылки на другие агрегаты по id. Equality по всем полям (`JSON.stringify(a) === JSON.stringify(b)` / lodash `isEqual`) → `ddd-tactical/entity-equality-by-identity`. Публичные мутабельные поля / сеттеры на всё → `ddd-tactical/entity-constructor-validates`. Анемичная модель (interface с полями + логика в сервисах) → `ddd-tactical/model-is-not-anemic`. Ссылка-объект на чужой агрегат → `ddd-tactical/no-object-references-across-aggregates`.
   - **Value Object (`R-VO-*`):** класс с `ValueObject.components()` (все значимые поля), поля `readonly` + `Object.freeze(this)`; инварианты в конструкторе; мутация возвращает новый экземпляр; одно-полевые id — branded types. VO с id/жизненным циклом → `ddd-tactical/value-has-no-identity`. Primitive obsession (`string`/`number` вместо `Email`/`Money`) → `ddd-tactical/no-primitive-obsession`. Мутабельный массив без копии в VO → `ddd-tactical/collections-in-values-are-protected` (`readonly`-модификатор TS не защищает в runtime; `Object.freeze` не покрывает вложенные). Деньги `number` → нарушение (Big.js/decimal.js обязателен, cross-ref `typeorm/precise-column-types`).
   - **Aggregate Root (`R-AGG-*`):** наследует `AggregateRoot<ID>`; события через `this.registerEvent(...)` в корне; наружу — копии (`[...lines]`); один use case = один агрегат; ссылки по id. Регистрация события вне корня → `ddd-tactical/events-registered-by-root`. `return this.orderLines` без копии → `ddd-tactical/aggregate-root-is-single-entry`. God aggregate → `ddd-tactical/aggregate-stays-small`.
   - **Domain Event (`R-EVT-*`):** наследует `DomainEvent` (`eventId`/`occurredAt`/`aggregateId`), frozen; имя в прошедшем времени (`OrderConfirmed`); только примитивы/VO; публикация после `save` через Outbox в той же транзакции + `pullEvents()`. Ссылка на агрегат/Entity в событии → `ddd-tactical/event-carries-business-context`. Публикация из Handler/контроллера → `ddd-tactical/events-published-after-save`. After-commit фоном (`EventEmitter2`/subscriber) для критичных эффектов → `ddd-tactical/no-after-commit-for-critical-effects` (Outbox).
   - **Repository (`R-REP-*`):** порт — интерфейс + Symbol-токен в `core/<bc>/port/`, методы в доменных терминах, возвращает домен; реализация в `adapters/out/persistence/`. Возврат TypeORM-Entity/raw row наружу → `ddd-tactical/repository-speaks-domain` (cross-ref `typeorm/repository-speaks-domain-types`). Методы под одну таблицу → `ddd-tactical/repository-speaks-domain`. SQL-Specification в репозитории → `ddd-tactical/specification-is-not-a-query-builder`.
   - **Domain Service (`R-DS-*`):** только для логики на ≥2 агрегатах, stateless plain class (без `@Injectable`), доменные объекты. Оркестрация (репозиторий/TX/публикация) в Domain Service → `ddd-tactical/domain-service-only-across-aggregates`. Свалка-сервис при анемичных агрегатах → `ddd-tactical/domain-service-only-across-aggregates`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory только когда конструктора мало, возвращает валидный агрегат с начальными событиями (`ddd-tactical/factory-only-when-needed` — Factory ради Factory). Specification только при переиспользовании/композиции, не для SQL (`ddd-tactical/specification-is-not-a-query-builder`/`X2`).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (нет корневых `entity/`/`service/`/`repository/`); `core/` не импортирует `@nestjs/*`/`typeorm`/`class-validator`/`adapters/*`. Фреймворк в `core/` → `ddd-tactical/packages-grouped-by-domain` (проверь контракт dependency-cruiser/eslint-boundaries).

4. **Cross-check:** граница TX и публикация событий — `ucp-node-pattern-review` (`usecase-pattern/publish-events-after-save`); реализация репозитория — `ucp-node-typeorm-review`; типы колонок — `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — мутабельный VO / массив без копии (`ddd-tactical/collections-in-values-are-protected`), события вне корня (`ddd-tactical/events-registered-by-root`), equality по полям на Entity (`ddd-tactical/entity-equality-by-identity`), ссылка-объект между агрегатами (`ddd-tactical/no-object-references-across-aggregates`), фреймворк в `core/` (`ddd-tactical/packages-grouped-by-domain`), ссылка на агрегат в событии (`ddd-tactical/event-carries-business-context`), деньги `number`.
   - **Предупреждение** — анемичная модель (`ddd-tactical/model-is-not-anemic`), публичные сеттеры (`ddd-tactical/entity-constructor-validates`), порт-репозиторий вне домена (`ddd-tactical/repository-port-in-domain`), after-commit для критичных эффектов (`ddd-tactical/no-after-commit-for-critical-effects`), возврат внутренней коллекции (`ddd-tactical/aggregate-root-is-single-entry`).
   - **Замечание** — primitive obsession (`ddd-tactical/no-primitive-obsession`), Factory/Specification ради абстракции (`ddd-tactical/factory-only-when-needed`/`ddd-tactical/specification-for-reuse`), нейминг события не в прошедшем времени (`ddd-tactical/event-named-in-past-tense`).

## Что не входит

- Граница транзакции и бизнес-операции — `ucp-node-pattern-review`. Реализация репозитория — `ucp-node-typeorm-review`.
- Валидация входа (class-validator) — `ucp-node-validation-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
