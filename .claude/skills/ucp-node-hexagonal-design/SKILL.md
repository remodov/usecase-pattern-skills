---
name: ucp-node-hexagonal-design
lang: node
description: Сгенерировать или реструктурировать NestJS-сервис под Hexagonal Architecture (коды R-HEX-*) — папки core/adapters/app, контракт dependency-cruiser, порты + Symbol-токены в core/<bc>/port/out/, контроллеры через Dispatcher, app/ composition root.
when_to_use: Старт сервиса Уровня 3 или upgrade 2→3. Триггеры — «hexagonal layout на ноде», «реструктурируй под core/adapters».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(depcruise*) Bash(eslint*)
---

# Hexagonal Architecture — проектирование (Node / папки + dependency-cruiser)

Ты генерируешь раскладку сервиса по **общему контракту** `backend/hexagonal/hexagonal-rules.md` (`R-HEX-*`) и
**Node-реализации** `backend/hexagonal/node/hexagonal-style-guide.md`. Изоляция границ — через dependency-cruiser (или eslint-plugin-boundaries), не gradle-модули.

## Инструкции

1. **Прочитай** контракт `backend/hexagonal/hexagonal-rules.md` + Node-style-guide. Коды `R-HEX-*` в design-обосновании, не в коде. Связанные: `backend/usecase-pattern/node/...` (Dispatcher/UseCase/порты), `backend/ddd-tactical/node/...` (домен в core/), `backend/node/typeorm/typeorm-rules.md` (out-persistence), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-5/6/15`).

2. **Реши уровень** (`R-HEX-WHEN-*`): Уровень 3 (DDD + ports/adapters) → полная раскладка; Уровень 1–2 → плоский `app/`, не плоди ceremony. Назови выбор в начале.

3. **Произведи дерево папок** (`R-HEX-MOD-*`):
   ```
   src/core/<bc>/{aggregate,entity,value-object,event,port,usecases,service}/
   src/adapters/in/http/          # user-контроллеры
   src/adapters/in/http-admin/    # admin (отдельный Guard)
   src/adapters/out/{persistence,<system>}/
   src/app/   # main.ts, AppModule, типизированный конфиг
   ```
   `core/` — без `@nestjs/*`/`typeorm`/`class-validator` и без NestJS-декораторов; стрелка `app → adapters → core`.

4. **Контракт dependency-cruiser** — `.dependency-cruiser.cjs` с правилами `core-pure` (core не импортит adapters/app/инфраструктуру), `adapters-independent` (in не импортит out), `nobody-depends-on-app`. Это обязательный enforcement (`R-HEX-TEST-1`), не опционально; `depcruise --validate` в CI как required check.

5. **Порты** (`R-HEX-PORT-*`) — интерфейс + Symbol-токен в `core/<bc>/port/out/` (интерфейсы TS стираются в runtime — токен обязателен для DI), domain-типы в сигнатурах, port-исключения базового типа в `core/`. **In-adapter** (`R-HEX-AIN-*`) — контроллер через `Dispatcher`, маппер REST-DTO↔command/response отдельным файлом. **Out-adapter** (`R-HEX-AOUT-*`) — реализует порт (биндинг `{ provide: TOKEN, useClass: ... }`, `NESTBOOT-6`), маппер domain↔DTO, per-system папка. **app/** (`R-HEX-BOOT-*`) — только композиция: handlers в `core/` — plain classes, wiring через `useFactory`-провайдеры; все порты забинжены (`R-HEX-BOOT-3`).

6. **Placeholder-файлы**: `app/main.ts` (`NestFactory.create` + `enableShutdownHooks`), `app/app.module.ts`, `core/<bc>/` каркас, `.dependency-cruiser.cjs`, скрипт `depcruise` в `package.json`, CI-шаг. Самопроверка по §9 + предложи `ucp-node-hexagonal-review`.

## Антипаттерны, которые НЕ генерировать

- Отсутствие dependency-cruiser-контракта (`R-HEX-MOD-X1`); `core/` импортит фреймворк/декораторы (`R-HEX-CORE-X1/X2`); TypeORM-Entity/class-validator-DTO как domain в core (`R-HEX-CORE-X4/X5`).
- Порт в out-adapter (`R-HEX-PORT-X1`); порт-класс с реализацией вместо интерфейса+токена (`R-HEX-PORT-X4`); контроллер зовёт репозиторий (`R-HEX-AIN-X2`); адаптеры зависят друг от друга (`R-HEX-AIN-X4`/`R-HEX-AOUT-X4`).
- Бизнес-логика в адаптере (`R-HEX-AIN-X1`/`R-HEX-AOUT-X2`) или в `app/` (`R-HEX-BOOT-X1`).

После работы скилла — обязательно `ucp-node-hexagonal-review`.

$ARGUMENTS
