---
name: ucp-node-pattern-design
lang: node
description: Спроектировать UseCase + Handler в NestJS-сервисе на Node (коды R-UC-*, R-HND-*, R-LAY-*) — readonly Command/Query, @Injectable Handler с TransactionRunner, Dispatcher-реестр, тонкий контроллер, порты-интерфейсы, слои DTO/домен/TypeORM.
when_to_use: Триггеры — «добавь команду X в NestJS», «новый UseCase на Node», «эндпоинт создания Y». При новом эндпоинте/команде/запросе.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Проектирование UseCase + Handler (Node / NestJS + TypeScript)

Ты проектируешь бизнес-операцию как **UseCase + Handler** согласно **общему контракту**
`backend/usecase-pattern/usecase-pattern-rules.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`)
и его **Node-реализации** `backend/usecase-pattern/node/usecase-pattern-style-guide.md` (NestJS + `@Injectable` + Dispatcher-реестр; роль java-библиотеки `usecase-pattern` играют лёгкие интерфейсы `Command<R>`/`Query<R>`/`Handler<UC,R>`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/usecase-pattern/usecase-pattern-rules.md` — общий контракт, коды `R-*` (цитируй в design-обосновании, **не** в комментариях кода).
   - `.claude/docs/backend/usecase-pattern/node/usecase-pattern-style-guide.md` — Node-реализация (`Command<R>`/`Query<R>`/`Handler<UC,R>`, `Dispatcher`, `TransactionRunner`, тонкий контроллер), открывай точечно.
   - На Уровне 3 — `.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md` (домен).
   - Если есть новая таблица — `.claude/docs/backend/pg-types/pg-types-rules.md` (типы; PostgreSQL-правила язык-нейтральны).

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
   Deps через конструктор по DI-токенам портов (`@Inject(SYMBOL)`), поля `private readonly`; граница транзакции — через `TransactionRunner`-порт: `this.tx.run(async () => { ... })` для команды (read-write), без транзакции для запроса (`R-HND-3`, `R-TX-1`). Один Handler — один UseCase (`R-HND-4`). Инфра-ошибки TypeORM/axios → доменные в адаптере (`R-HND-X2`; cross-ref `error-handling/node`).

   ### 4.3 Регистрация в DI + Dispatcher
   Handler — `@Injectable` + регистрация в feature-модуле; Dispatcher собирается в `app/` как провайдер-фабрика (`Map<constructor, handler>` → `new Dispatcher(registry)`) (`R-HND-2`, `R-DSP-1/2`).

   ### 4.4 Тонкий NestJS-контроллер
   class-validator Request → `new UseCase(principal.userId, ...)` → `this.dispatcher.dispatch(uc)` → Response + HTTP-код. `userId`/`tenantId` — из `@Principal()`, не из Request-объекта (`R-DSP-X2`). Без логики/БД в контроллере (`R-DSP-3`, `R-DSP-X1`).

   ### 4.5 Слои и порты
   DTO на edge (class-validator) ≠ доменные объекты ≠ TypeORM-Entity; явный маппинг функциями (`toDomainItems`, `OrderViewMapper.fromRow`) (`R-LAY-1/2/3`). Внешнее — за портами-интерфейсами + Symbol-токенами в `core/<bc>/port/`; `core/` без `@nestjs/*`/`typeorm`/`axios` (`R-HEX-2/3`). Enforce через dependency-cruiser или eslint-boundaries.

5. **Самопроверка** — чеклист из `node/usecase-pattern-style-guide.md` (§ «Чеклист подключения к новому сервису»).

6. **Финальный шаг:** предложи «запусти `ucp-node-pattern-review`», а для обработки ошибок — `ucp-node-error-handling-design`.

## Антипаттерны, которые НЕ генерировать

- Логика в UseCase / мутабельные поля (`R-UC-X1`/`X3`).
- Handler инжектит и зовёт другой Handler напрямую (`R-HND-X1`); контроллер с бизнес-логикой/БД (`R-DSP-X1`); `Request`/`ExecutionContext`/principal-объект в UseCase (`R-DSP-X2`).
- TypeORM-Entity в JSON-ответе / один класс на API и БД (`R-LAY-X1`); `Object.assign`/`plainToInstance` как маппер (`R-LAY-X3`).
- `import { ... } from '@nestjs/common'` / `'typeorm'` в `core/` (`R-HEX-X2`); `DataSource`/`createQueryBuilder` в `core/` (`R-HEX-X1`).
- Граница транзакции на репозитории вместо Handler (`R-TX-1`).
- Команда возвращает тяжёлый read-DTO со связями (`R-CQRS-X1`); запрос пишет в БД (`R-CQRS-X2`).
- Handler с накапливаемым состоянием между `execute` — Handler stateless (`R-HND-X3`).

После работы скилла — обязательно `ucp-node-pattern-review` для верификации.

$ARGUMENTS
