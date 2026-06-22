---
name: ucp-node-pattern-review
lang: node
description: Ревью UseCase + Handler в NestJS-сервисе (Node/TypeScript, коды R-UC-*, R-HND-*, R-DSP-*, R-LAY-*) — readonly Command/Query, stateless Handler с TransactionRunner, Dispatcher, тонкий контроллер, порты-интерфейсы в core/, раздельные DTO/домен/Entity.
when_to_use: Изменения в UseCase-классах, Handler-ах, контроллерах, Dispatcher-е или портах core/ в NestJS-сервисе.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью UseCase + Handler (Node / NestJS + TypeScript)

Ты ревьюишь NestJS-сервис на соответствие **общему контракту** `backend/usecase-pattern/usecase-pattern-rules.md`
(`R-*`, коды едины с Java и Python) и его **Node-реализации** `backend/usecase-pattern/node/usecase-pattern-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md`** — контракт (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`).
- **`.claude/docs/backend/usecase-pattern/node/usecase-pattern-style-guide.md`** — Node-реализация.
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-WHERE-2b` — инфра→домен в адаптере), `backend/ddd-tactical/ddd-tactical-rules.md`, `backend/pg-types/pg-types-rules.md`.

## Инструкции

1. **Прочти** контракт (коды) и Node-style-guide (реализация). Цитируй конкретные коды (`R-HND-X2`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/*.usecase.ts`, `**/usecases/**/*.ts` — `R-UC-*`.
   - `**/*.handler.ts`, `**/handlers/**/*.ts` — `R-HND-*`, `R-TX-*`.
   - `adapters/in/http/**`, `**/*.controller.ts` — `R-DSP-*`.
   - `app/dispatcher.ts`, DI-реестр — `R-DSP-1/2`.
   - `core/**/port/**` — `R-HEX-3`.
   - `git diff` на изменённые `.ts`.

3. **Прогон по подгруппам.**

   ### `R-UC-*`
   - UseCase — `readonly`-поля, коллекции `ReadonlyArray`, без логики, имя-операция? — `R-UC-1/2/3`. Mutable-поля/сеттеры → `R-UC-X3`. Логика в UseCase → `R-UC-X1`. Один класс на 2 операции → `R-UC-X2`. Возвращает `void` вместо явного `EmptyResult` → `R-UC-X4`.

   ### `R-HND-*` / `R-TX-*`
   - Handler — `@Injectable()`, реализует `Handler<UC, R>` с `execute(uc): Promise<R>`, один UseCase, deps через конструктор по DI-токенам, поля `private readonly`? — `R-HND-1/4/5`.
   - Граница транзакции на Handler (`this.tx.run(...)` / `dataSource.transaction` для команды, без транзакции для запроса), не на репозитории? — `R-HND-3`, `R-TX-1`.
   - Handler инжектит и вызывает другой Handler напрямую — `R-HND-X1`.
   - Наружу летит `QueryFailedError`/axios-ошибка (не mapится в доменную) — `R-HND-X2` (cross-ref `R-ERR-WHERE-2b`).
   - Поля, накапливающие состояние между `execute` — `R-HND-X3`.

   ### `R-DSP-*`
   - Контроллер зовёт `dispatcher.dispatch(uc)`, не Handler напрямую? — `R-DSP-1`.
   - Endpoint тонкий (Request→UseCase, dispatch, Response, HTTP-код)? Логика/обращение к БД в контроллере → `R-DSP-X1`.
   - `Request`/`ExecutionContext`/`AuthPrincipal`-объект протекает в UseCase вместо `userId`/`tenantId` — `R-DSP-X2`.

   ### `R-CQRS-*`
   - Команда реализует `Command<R>` (глагол); запрос — `Query<R>` (`Find*/Get*/Search*`) + ViewRepository + без транзакции? — `R-CQRS-1/2/3/4`.
   - Команда возвращает тяжёлый read-DTO со связями — `R-CQRS-X1`. Запрос пишет (last-seen/counter) — `R-CQRS-X2`.

   ### `R-LAY-*`
   - class-validator Request-DTO на edge, домен в core, TypeORM-Entity в `adapters/out/persistence/`; явный маппинг? — `R-LAY-1/2/3`.
   - TypeORM-Entity уходит в JSON-ответ / один класс на API и БД — `R-LAY-X1`.
   - `Object.assign`/spread/`plainToInstance` Entity→domain как маппер — `R-LAY-X3` (cross-ref `R-TYPEORM-MAP-X1`).
   - Доменный объект (Aggregate/VO из `core/`) в API-ответе — `R-LAY-DDD`.

   ### `R-HEX-*`
   - Порты — `interface` + Symbol-токен в `core/<bc>/port/`; `core/` без `import { ... } from '@nestjs/common'`/`'typeorm'`/`'axios'`? — `R-HEX-2/3`. Нарушение импорта → `R-HEX-X2`; `DataSource`/`createQueryBuilder` в `core/` → `R-HEX-X1`. (Рекомендуй dependency-cruiser или eslint-boundaries.)

4. **Cross-check:** инфра→домен в адаптере → `ucp-node-error-handling-review` (`R-ERR-WHERE-2b`); DDL → `ucp-pg-schema-review`; TypeORM-репозиторий → `ucp-node-typeorm-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — логика в UseCase (`R-UC-X1`), Handler→Handler напрямую (`R-HND-X1`), endpoint с БД/логикой (`R-DSP-X1`), `core/` импортит `@nestjs/*`/`typeorm` (`R-HEX-X2`), TX на репозитории (`R-TX-1`), TypeORM-Entity в JSON-ответе (`R-LAY-X1`).
   - **Предупреждение** — mutable-поля в UseCase (`R-UC-X3`), `Request`/`ExecutionContext` в UseCase (`R-DSP-X2`), запрос пишет (`R-CQRS-X2`), `Object.assign`/`plainToInstance`-as-mapper (`R-LAY-X3`).
   - **Замечание** — нет явного read-DTO для запроса, Step-кандидат не выделен, имя не выражает операцию, `void` вместо явного `EmptyResult` (`R-UC-X4`).

## Что не входит

- Обработка ошибок (иерархия, ProblemDetail) — `ucp-node-error-handling-review`.
- Валидация входа (class-validator constraints) — `ucp-node-validation-review`.
- Доменная модель (агрегаты/VO) — `ucp-node-ddd-tactical-review`.
- TypeORM-репозиторий, ViewRepository, raw SQL — `ucp-node-typeorm-review`.

$ARGUMENTS
