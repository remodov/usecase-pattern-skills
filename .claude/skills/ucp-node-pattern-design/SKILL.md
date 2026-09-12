---
name: ucp-node-pattern-design
lang: node
description: Спроектировать UseCase + Handler в NestJS-сервисе на Node (требования usecase-pattern/*) — readonly Command/Query, @Injectable Handler с TransactionRunner, Dispatcher-реестр, тонкий контроллер, порты-интерфейсы, слои DTO/домен/TypeORM.
when_to_use: Триггеры — «добавь команду X в NestJS», «новый UseCase на Node», «эндпоинт создания Y». При новом эндпоинте/команде/запросе.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Проектирование UseCase + Handler (Node / NestJS + TypeScript)

Ты проектируешь бизнес-операцию как **UseCase + Handler** согласно **общему контракту**
`backend/usecase-pattern/spec.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`)
и его **Node-реализации** `backend/usecase-pattern/references/node/implementation.md` (NestJS + `@Injectable` + Dispatcher-реестр; роль java-библиотеки `usecase-pattern` играют лёгкие интерфейсы `Command<R>`/`Query<R>`/`Handler<UC,R>`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/usecase-pattern/spec.md` — общий контракт, коды `R-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/usecase-pattern/references/node/implementation.md` — Node-реализация (`Command<R>`/`Query<R>`/`Handler<UC,R>`, `Dispatcher`, `TransactionRunner`, тонкий контроллер), открывай точечно.
   - На Уровне 3 — `.claude/docs/backend/ddd-tactical/spec.md` (домен).
   - Если есть новая таблица — `.claude/docs/backend/pg-types/spec.md` (типы; PostgreSQL-правила язык-нейтральны).

2. **Идентифицируй сервис и слой.** Структура UCP на Node: `core/<bc>/` (usecases, handlers, domain, port/), `adapters/in/http/` (NestJS-контроллеры), `adapters/out/` (TypeORM-репозитории, HTTP-клиенты), `app/` (AppModule, dispatcher, конфиг).

3. **Спроектируй операцию.** Для команды/запроса определи: имя (бизнес-операция), вход (поля), результат `R`, командой или запросом.

4. **Произведи код** (полные `.ts`; TypeScript 5+, строгие типы; без комментариев — соответствие через имена/типы/структуру; коды правил НЕ цитируй в коде).

   ### 4.1 UseCase — класс с `readonly`-полями, реализует `Command<R>` или `Query<R>`
   Имя-операция; поля — вход (`ReadonlyArray` для коллекций); без логики (`R-UC-1..4`). Команда / запрос по смыслу (`R-CQRS-1/3`). Фантомное поле `__result?` фиксирует `R` в типе:

   ```ts
   // core/usecase.ts
   export interface Command<R> { readonly __result?: R }
   export interface Query<R>   { readonly __result?: R }
   ```

   ### 4.2 Handler — `@Injectable`-класс, реализует `Handler<UC, R>` с `execute(uc): Promise<R>`
   Deps через конструктор по DI-токенам портов (`@Inject(SYMBOL)`), поля `private readonly`; граница транзакции — через `TransactionRunner`-порт: `this.tx.run(async () => { ... })` для команды (read-write), без транзакции для запроса (`usecase-pattern/transaction-boundary-on-handler`, `usecase-pattern/transaction-boundary-on-handler`). Один Handler — один UseCase (`usecase-pattern/one-handler-one-usecase`). Инфра-ошибки TypeORM/axios → доменные в адаптере (`usecase-pattern/infrastructure-errors-become-domain`; cross-ref `error-handling/node`).

   ### 4.3 Регистрация в DI + Dispatcher
   Handler — `@Injectable` + регистрация в feature-модуле; Dispatcher собирается в `app/` как провайдер-фабрика (`Map<constructor, handler>` → `new Dispatcher(registry)`) (`usecase-pattern/handler-registered-in-container`, `R-DSP-1/2`).

   ### 4.4 Тонкий NestJS-контроллер
   class-validator Request → `new UseCase(principal.userId, ...)` → `this.dispatcher.dispatch(uc)` → Response + HTTP-код. `userId`/`tenantId` — из `@Principal()`, не из Request-объекта (`usecase-pattern/no-transport-objects-in-usecase`). Без логики/БД в контроллере (`usecase-pattern/controller-maps-and-dispatches`, `usecase-pattern/controller-maps-and-dispatches`).

   ### 4.5 Слои и порты
   DTO на edge (class-validator) ≠ доменные объекты ≠ TypeORM-Entity; явный маппинг функциями (`toDomainItems`, `OrderViewMapper.fromRow`) (`R-LAY-1/2/3`). Внешнее — за портами-интерфейсами + Symbol-токенами в `core/<bc>/port/`; `core/` без `@nestjs/*`/`typeorm`/`axios` (`R-HEX-2/3`). Enforce через dependency-cruiser или eslint-boundaries.

5. **Самопроверка** — чеклист из `node/implementation.md` (§ «Чеклист подключения к новому сервису»).

6. **Финальный шаг:** предложи «запусти `ucp-node-pattern-review`», а для обработки ошибок — `ucp-node-error-handling-design`.

## Антипаттерны, которые НЕ генерировать

- Логика в UseCase / мутабельные поля (`usecase-pattern/usecase-is-immutable-carrier`/`X3`).
- Handler инжектит и зовёт другой Handler напрямую (`usecase-pattern/handlers-do-not-call-handlers`); контроллер с бизнес-логикой/БД (`usecase-pattern/controller-maps-and-dispatches`); `Request`/`ExecutionContext`/principal-объект в UseCase (`usecase-pattern/no-transport-objects-in-usecase`).
- TypeORM-Entity в JSON-ответе / один класс на API и БД (`usecase-pattern/layer-models-do-not-leak`); `Object.assign`/`plainToInstance` как маппер (`usecase-pattern/explicit-mapper-between-layers`).
- `import { ... } from '@nestjs/common'` / `'typeorm'` в `core/` (`hexagonal/core-free-of-framework`); `DataSource`/`createQueryBuilder` в `core/` (`hexagonal/outbound-port-interface-in-core`).
- Граница транзакции на репозитории вместо Handler (`usecase-pattern/transaction-boundary-on-handler`).
- Команда возвращает тяжёлый read-DTO со связями (`usecase-pattern/command-returns-minimum`); запрос пишет в БД (`usecase-pattern/query-does-not-mutate`).
- Handler с накапливаемым состоянием между `execute` — Handler stateless (`usecase-pattern/handler-is-stateless`).

После работы скилла — обязательно `ucp-node-pattern-review` для верификации.

$ARGUMENTS
