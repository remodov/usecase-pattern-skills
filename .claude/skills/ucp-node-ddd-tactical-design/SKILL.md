---
name: ucp-node-ddd-tactical-design
lang: node
description: Спроектировать доменную модель на чистом TypeScript в core/ по UCP DDD Tactical Patterns (коды R-ENT/VO/AGG/EVT/REP-*) — Entity с identity-equality, иммутабельный VO, branded ids, AggregateRoot с событиями, порт + Symbol-токен, деньги Big.js.
when_to_use: Триггеры — «агрегат X на ноде», «доменная модель для Y», «value object Money». При моделировании BC или агрегата на Уровне 3.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# DDD Tactical Patterns — проектирование (Node / чистый core)

Ты проектируешь доменную модель согласно **общему контракту** `backend/ddd-tactical/ddd-tactical-rules.md`
(`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`) и его **Node-реализации** `backend/ddd-tactical/node/ddd-tactical-style-guide.md`.
Домен живёт в `core/` **без фреймворка** (ни NestJS-декораторов, ни TypeORM, ни class-validator) — чистый TypeScript + доменные утилиты (Big.js, uuid).

## Инструкции

1. **Прочитай** контракт `backend/ddd-tactical/ddd-tactical-rules.md` + Node-style-guide `backend/ddd-tactical/node/ddd-tactical-style-guide.md`. Коды `R-*` обязательны; цитируй их в **design-обосновании**, не в комментариях кода. Связанные: `backend/usecase-pattern/node/...` (Handler/граница TX/порты), `backend/node/typeorm/typeorm-rules.md` (реализация репозитория).

2. **Базовые типы.** Если в `core/shared/building-blocks.ts` нет `Entity`/`ValueObject`/`AggregateRoot`/`DomainEvent` — создай тонкие ручные (в Node нет `ddd-building-blocks`); образец — в style-guide. Не тащи их из adapter-слоя.

3. **Уточни модель:** Bounded Context и папку (`core/<bc>/`); корень агрегата и защищаемый инвариант; внутренние Entity; Value Objects (бьём primitive obsession — `Money`/`Email`/`OrderId`); доменные события (прошедшее время); ссылки на другие агрегаты — по id; оправданы ли Factory/Domain Service/Specification (по умолчанию нет).

4. **Произведи код** (TypeScript strict; без комментариев; коды правил не цитируй):
   - **Value Object** — класс, наследует `ValueObject`, поля `readonly` + `Object.freeze(this)` в конструкторе, инварианты в конструкторе, мутация → новый экземпляр; `components()` со всеми значимыми полями; коллекции — `ReadonlyArray` + копия (`R-VO-*`). Одно-полевые id — branded types. Деньги — `Big.js`/`decimal.js`, никогда `number`.
   - **Entity** — класс, наследует `Entity<ID>`, id `readonly`, бизнес-методы (без сеттеров), `equals()` не переопределять; сравнение — `a.equals(b)`, не `===` (`R-ENT-*`). **Не** делать Entity plain-интерфейсом/type — структурная типизация TS убивает identity-семантику.
   - **Aggregate Root** — наследует `AggregateRoot<ID>`, мутирующие методы держат инварианты и зовут `this.registerEvent(...)`; наружу — копии (`[...this.lines]` как `ReadonlyArray`) (`R-AGG-*`).
   - **Domain Event** — класс, наследует `DomainEvent` (`eventId`/`occurredAt`/`aggregateId`), `Object.freeze(this)`, имя в прошедшем времени, только примитивы/VO (`R-EVT-*`).
   - **Repository** — интерфейс + Symbol-токен в `core/<bc>/port/`, методы в доменных терминах, возвращает домен (`R-REP-*`); реализация — отдельно через `ucp-node-typeorm-design`.
   - **Domain Service / Factory / Specification** — только если оправдано; укажи обоснование. Domain Service — plain class без `@Injectable`.

5. **Раскладка по домену** (`R-MOD-*`): `core/<bc>/{aggregate,entity,value-object,event,port,service,specification,usecases}/`. `core/` не импортирует `@nestjs/*`/`typeorm`/`class-validator`/`adapters/*` — предложи контракт dependency-cruiser или eslint-boundaries (`R-HEX-2`, `NESTBOOT-15`).

6. **Самопроверка** (чек-лист §10 style-guide) + предложи `ucp-node-ddd-tactical-review`. Persistence агрегата — `ucp-node-typeorm-design`.

## Антипаттерны, которые НЕ генерировать

- Entity с equality по полям (`JSON.stringify`/lodash `isEqual` — VO-семантика, `R-ENT-X2`); публичные сеттеры на всё (`R-ENT-X3`); анемичная модель (`R-ENT-X5`).
- VO с id/жизненным циклом (`R-VO-X1`); primitive obsession (`R-VO-X2`); мутабельный массив внутри VO без копии (`R-VO-X3`); деньги `number`.
- Регистрация события вне корня (`R-AGG-X4`); возврат внутренней коллекции наружу без копии (`R-AGG-X2`); ссылка на агрегат объектом (`R-ENT-X4`/`R-AGG-5`).
- Событие со ссылкой на агрегат (`R-EVT-X2`); фреймворк/декораторы NestJS в `core/` (`R-MOD-2`); порт-репозиторий вне домена (`R-REP-1`).

После работы скилла — обязательно `ucp-node-ddd-tactical-review`.

$ARGUMENTS
