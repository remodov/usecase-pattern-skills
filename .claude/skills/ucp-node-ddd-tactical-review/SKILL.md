---
name: ucp-node-ddd-tactical-review
lang: node
description: Ревью доменного кода на чистом TypeScript (core/) по UCP DDD Tactical Patterns (коды R-ENT/VO/AGG/EVT/REP-*) — Entity с identity-equals, frozen VO, события в корне агрегата, порт + Symbol-токен, деньги Big.js, core/ без NestJS/TypeORM.
when_to_use: Ревью агрегатов, VO, доменных событий, портов-репозиториев в core/ NestJS-сервиса.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тактических паттернов DDD (Node / чистый core)

Ты ревьюишь доменный слой на соответствие **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md` (`R-*`)
и **Node-реализации** `backend/ddd-tactical/node/ddd-tactical-style-guide.md`. Домен в `core/` — чистый TypeScript без фреймворка.

## Зависимости

- **`.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md`** — контракт (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`).
- **`.claude/docs/backend/ddd-tactical/node/ddd-tactical-style-guide.md`** — Node-идиомы (identity-`equals()`, `ValueObject.components()`, branded ids, dependency-cruiser).
- Парные: `backend/usecase-pattern/node/...` (граница TX/события), `backend/node/typeorm/typeorm-rules.md` (реализация репозитория).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй конкретные коды (`R-AGG-X4`, `R-VO-X3`), не префикс.

2. **Скоп.** `core/<bc>/{aggregate,entity,value-object,event,port,service,specification}/**`, `core/shared/building-blocks.ts`, `git diff` на `.ts` в `core/`.

3. **Прогон.**
   - **Entity (`R-ENT-*`):** наследует `Entity<ID>`; id `readonly`, без сеттера; `equals()` не переопределён в наследнике; сравнение через `a.equals(b)`, не `===`; состояние меняется бизнес-методами, не сеттерами; ссылки на другие агрегаты по id. Equality по всем полям (`JSON.stringify(a) === JSON.stringify(b)` / lodash `isEqual`) → `R-ENT-X2`. Публичные мутабельные поля / сеттеры на всё → `R-ENT-X3`. Анемичная модель (interface с полями + логика в сервисах) → `R-ENT-X5`. Ссылка-объект на чужой агрегат → `R-ENT-X4`.
   - **Value Object (`R-VO-*`):** класс с `ValueObject.components()` (все значимые поля), поля `readonly` + `Object.freeze(this)`; инварианты в конструкторе; мутация возвращает новый экземпляр; одно-полевые id — branded types. VO с id/жизненным циклом → `R-VO-X1`. Primitive obsession (`string`/`number` вместо `Email`/`Money`) → `R-VO-X2`. Мутабельный массив без копии в VO → `R-VO-X3` (`readonly`-модификатор TS не защищает в runtime; `Object.freeze` не покрывает вложенные). Деньги `number` → нарушение (Big.js/decimal.js обязателен, cross-ref `R-TYPEORM-ENT-2`).
   - **Aggregate Root (`R-AGG-*`):** наследует `AggregateRoot<ID>`; события через `this.registerEvent(...)` в корне; наружу — копии (`[...lines]`); один use case = один агрегат; ссылки по id. Регистрация события вне корня → `R-AGG-X4`. `return this.orderLines` без копии → `R-AGG-X2`. God aggregate → `R-AGG-X1`.
   - **Domain Event (`R-EVT-*`):** наследует `DomainEvent` (`eventId`/`occurredAt`/`aggregateId`), frozen; имя в прошедшем времени (`OrderConfirmed`); только примитивы/VO; публикация после `save` через Outbox в той же транзакции + `pullEvents()`. Ссылка на агрегат/Entity в событии → `R-EVT-X2`. Публикация из Handler/контроллера → `R-EVT-X3`. After-commit фоном (`EventEmitter2`/subscriber) для критичных эффектов → `R-EVT-X4` (Outbox).
   - **Repository (`R-REP-*`):** порт — интерфейс + Symbol-токен в `core/<bc>/port/`, методы в доменных терминах, возвращает домен; реализация в `adapters/out/persistence/`. Возврат TypeORM-Entity/raw row наружу → `R-REP-X1` (cross-ref `R-TYPEORM-REPO-X1`). Методы под одну таблицу → `R-REP-X2`. SQL-Specification в репозитории → `R-REP-X3`.
   - **Domain Service (`R-DS-*`):** только для логики на ≥2 агрегатах, stateless plain class (без `@Injectable`), доменные объекты. Оркестрация (репозиторий/TX/публикация) в Domain Service → `R-DS-X1`. Свалка-сервис при анемичных агрегатах → `R-DS-X2`.
   - **Factory / Specification (`R-FAC/SPEC-*`):** Factory только когда конструктора мало, возвращает валидный агрегат с начальными событиями (`R-FAC-X1` — Factory ради Factory). Specification только при переиспользовании/композиции, не для SQL (`R-SPEC-X1`/`X2`).
   - **Module (`R-MOD-*`):** группировка по Bounded Context (нет корневых `entity/`/`service/`/`repository/`); `core/` не импортирует `@nestjs/*`/`typeorm`/`class-validator`/`adapters/*`. Фреймворк в `core/` → `R-MOD-2` (проверь контракт dependency-cruiser/eslint-boundaries).

4. **Cross-check:** граница TX и публикация событий — `ucp-node-pattern-review` (`R-TX-3`); реализация репозитория — `ucp-node-typeorm-review`; типы колонок — `ucp-pg-schema-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — мутабельный VO / массив без копии (`R-VO-X3`), события вне корня (`R-AGG-X4`), equality по полям на Entity (`R-ENT-X2`), ссылка-объект между агрегатами (`R-ENT-X4`), фреймворк в `core/` (`R-MOD-2`), ссылка на агрегат в событии (`R-EVT-X2`), деньги `number`.
   - **Предупреждение** — анемичная модель (`R-ENT-X5`), публичные сеттеры (`R-ENT-X3`), порт-репозиторий вне домена (`R-REP-1`), after-commit для критичных эффектов (`R-EVT-X4`), возврат внутренней коллекции (`R-AGG-X2`).
   - **Замечание** — primitive obsession (`R-VO-X2`), Factory/Specification ради абстракции (`R-FAC-X1`/`R-SPEC-X2`), нейминг события не в прошедшем времени (`R-EVT-2`).

## Что не входит

- Граница транзакции и бизнес-операции — `ucp-node-pattern-review`. Реализация репозитория — `ucp-node-typeorm-review`.
- Валидация входа (class-validator) — `ucp-node-validation-review`. Типы БД — `ucp-pg-schema-review`.

$ARGUMENTS
