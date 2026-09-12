---
name: ucp-node-pattern-review
lang: node
description: Ревью UseCase + Handler в NestJS-сервисе (Node/TypeScript, коды R-UC-*, R-HND-*, R-DSP-*, R-LAY-*) — readonly Command/Query, stateless Handler с TransactionRunner, Dispatcher, тонкий контроллер, порты-интерфейсы в core/, раздельные DTO/домен/Entity.
when_to_use: Изменения в UseCase-классах, Handler-ах, контроллерах, Dispatcher-е или портах core/ в NestJS-сервисе.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью UseCase + Handler (Node / NestJS + TypeScript)

Ты ревьюишь NestJS-сервис на соответствие **общему контракту** `backend/usecase-pattern/spec.md`
(`R-*`, коды едины с Java и Python) и его **Node-реализации** `backend/usecase-pattern/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/spec.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/references/node/implementation.md`** — Node-реализация.
- Парные: `backend/error-handling/spec.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/spec.md`, `backend/pg-types/spec.md`.

## Инструкции

1. **Прочти** контракт и `references/node/implementation.md` (реализация). Цитируй конкретные коды (`usecase-pattern/infrastructure-errors-become-domain`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/*.usecase.ts`, `**/usecases/**/*.ts` — `R-UC-*`.
   - `**/*.handler.ts`, `**/handlers/**/*.ts` — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**`, `**/*.controller.ts` — `R-DSP-*`.
   - `app/dispatcher.ts`, DI-реестр — `R-DSP-1/2`.
   - `core/**/port/**` — `hexagonal/outbound-port-interface-in-core`.
   - `git diff` на изменённые `.ts`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — `readonly`-поля, коллекции `ReadonlyArray`, без логики, имя-операция? — `R-UC-1/2/3`. Mutable-поля/сеттеры → `usecase-pattern/usecase-is-immutable-carrier`. Логика в UseCase → `usecase-pattern/usecase-is-immutable-carrier`. Один класс на 2 операции → `usecase-pattern/one-usecase-one-operation`. Возвращает `void` вместо явного `EmptyResult` → `usecase-pattern/explicit-result-type`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — `@Injectable()`, реализует `Handler<UC, R>` с `execute(uc): Promise<R>`, один UseCase, deps через конструктор по DI-токенам, поля `private readonly`? — `R-HND-1/4/5`.
   - Граница транзакции на Handler (`this.tx.run(...)` / `dataSource.transaction` для команды, без транзакции для запроса), не на репозитории? — `usecase-pattern/transaction-boundary-on-handler`, `usecase-pattern/transaction-boundary-on-handler`.
   - Handler инжектит и вызывает другой Handler напрямую — `usecase-pattern/handlers-do-not-call-handlers`.
   - Наружу летит `QueryFailedError`/axios-ошибка (не mapится в доменную) — `usecase-pattern/infrastructure-errors-become-domain` (cross-ref `R-ERR-WHERE-2b`).
   - Поля, накапливающие состояние между `execute` — `usecase-pattern/handler-is-stateless`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.dispatch(uc)`, не Handler напрямую? — `usecase-pattern/entry-calls-dispatcher`.
   - Endpoint тонкий (Request→UseCase, dispatch, Response, HTTP-код)? Логика/обращение к БД в контроллере → `usecase-pattern/controller-maps-and-dispatches`.
   - `Request`/`ExecutionContext`/`AuthPrincipal`-объект протекает в UseCase вместо `userId`/`tenantId` — `usecase-pattern/no-transport-objects-in-usecase`.

   ### `R-CQRS-*`
   - Команда реализует `Command<R>` (глагол); запрос — `Query<R>` (`Find*/Get*/Search*`) + ViewRepository + без транзакции? — `R-CQRS-1/2/3/4`.
   - Команда возвращает тяжёлый read-DTO со связями — `usecase-pattern/command-returns-minimum`. Запрос пишет (last-seen/counter) — `usecase-pattern/query-does-not-mutate`.

   ### `R-LAY-*`
   - class-validator Request-DTO на edge, домен в core, TypeORM-Entity в `adapters/out/persistence/`; явный маппинг? — `R-LAY-1/2/3`.
   - TypeORM-Entity уходит в JSON-ответ / один класс на API и БД — `usecase-pattern/layer-models-do-not-leak`.
   - `Object.assign`/spread/`plainToInstance` Entity→domain как маппер — `usecase-pattern/explicit-mapper-between-layers` (cross-ref `typeorm/explicit-mapper`).
   - Доменный объект (Aggregate/VO из `core/`) в API-ответе — `usecase-pattern/layer-models-do-not-leak`.

   ### `R-HEX-*`
   - Порты — `interface` + Symbol-токен в `core/<bc>/port/`; `core/` без `import { ... } from '@nestjs/common'`/`'typeorm'`/`'axios'`? — `R-HEX-2/3`. Нарушение импорта → `hexagonal/core-free-of-framework`; `DataSource`/`createQueryBuilder` в `core/` → `hexagonal/outbound-port-interface-in-core`. (Рекомендуй dependency-cruiser или eslint-boundaries.)

4. **Cross-check:** инфра→домен в адаптере → `ucp-node-error-handling-review` (`R-ERR-WHERE-2b`); DDL → `ucp-pg-schema-review`; TypeORM-репозиторий → `ucp-node-typeorm-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — логика в UseCase (`usecase-pattern/usecase-is-immutable-carrier`), Handler→Handler напрямую (`usecase-pattern/handlers-do-not-call-handlers`), endpoint с БД/логикой (`usecase-pattern/controller-maps-and-dispatches`), `core/` импортит `@nestjs/*`/`typeorm` (`hexagonal/core-free-of-framework`), TX на репозитории (`usecase-pattern/transaction-boundary-on-handler`), TypeORM-Entity в JSON-ответе (`usecase-pattern/layer-models-do-not-leak`).
   - **Предупреждение** — mutable-поля в UseCase (`usecase-pattern/usecase-is-immutable-carrier`), `Request`/`ExecutionContext` в UseCase (`usecase-pattern/no-transport-objects-in-usecase`), запрос пишет (`usecase-pattern/query-does-not-mutate`), `Object.assign`/`plainToInstance`-as-mapper (`usecase-pattern/explicit-mapper-between-layers`).
   - **Замечание** — нет явного read-DTO для запроса, Step-кандидат не выделен, имя не выражает операцию, `void` вместо явного `EmptyResult` (`usecase-pattern/explicit-result-type`).

## Что не входит

- Обработка ошибок (иерархия, ProblemDetail) — `ucp-node-error-handling-review`.
- Валидация входа (class-validator constraints) — `ucp-node-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-node-ddd-tactical-review`.
- TypeORM-репозиторий, ViewRepository, raw SQL — `ucp-node-typeorm-review`.

$ARGUMENTS
