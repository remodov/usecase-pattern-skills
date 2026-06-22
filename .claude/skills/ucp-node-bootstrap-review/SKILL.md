---
name: ucp-node-bootstrap-review
lang: node
description: Ревью bootstrap NestJS-сервиса (Node) по UCP (коды NESTBOOT-*) — валидируемый конфиг fail-fast, AppModule без логики, DI-токены портов, Clock/UuidProvider, TypeORM без synchronize, гейтинг Kafka/Redis, health live/ready, core/ без фреймворка.
when_to_use: Изменения в main.ts, app.module.ts, конфиге, data-source/миграционной обвязке или feature-модулях.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью bootstrap (Node / NestJS)

Ты ревьюишь bootstrap-слой NestJS-сервиса на соответствие `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-*`).

## Зависимости

- **`.claude/docs/backend/node/nest-bootstrap/nest-bootstrap-rules.md`** — правила `NESTBOOT-*`.
- Парные: `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-*`), `backend/usecase-pattern/node/...` (DI/Handler), `backend/error-handling/node/...` (filters в композиции), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16/17`).

## Инструкции

1. **Прочти** `nest-bootstrap-rules.md`. Цитируй конкретные коды (`NESTBOOT-X4`), не префикс.

2. **Скоп.** `main.ts`, `app.module.ts`, конфиг (`config.ts`/`ConfigModule`), feature-модули, `data-source.ts`/миграционная обвязка, `package.json`-скрипты, `docker-compose.yml`; `git diff`.

3. **Прогон.**
   - **Конфиг:** `ConfigModule.forRoot({ validate })` с типизированной схемой, `NODE_ENV=local|integration-test|production`, required без default, fail-fast? Секреты не в git? (`NESTBOOT-2/3/4`). `process.env.FOO` россыпью → `NESTBOOT-X1`.
   - **Композиция:** `AppModule` — только сборка? Feature-модуль на bounded context? Провайдеры через DI-токены портов из `core/`? (`NESTBOOT-5/6`). Логика/env-ветвления в `@Module`-фабриках → `NESTBOOT-X2`.
   - **DI:** `Clock`/`UuidProvider` за токенами, production-реализации в bootstrap? (`NESTBOOT-7`). `new Date()`/`randomUUID()` в домене/хендлере → `NESTBOOT-X3`.
   - **Persistence:** `TypeOrmModule.forRootAsync` от конфига, один DataSource; миграции отдельной командой, `synchronize: false` (`NESTBOOT-8/9`). `synchronize: true` в production → `NESTBOOT-X4`.
   - **Гейтинг:** Kafka/Redis/schedulers подключаются по профилю, off в local/integration-test (`NESTBOOT-11`). Безусловный `connectMicroservice`/Redis-коннект → `NESTBOOT-X5`.
   - **Server/health:** `enableShutdownHooks()` (`NESTBOOT-12`); `/health/live` + `/health/ready` раздельно через terminus (`NESTBOOT-13`). Блокирующий sync-вызов в request-пути → `NESTBOOT-X6`.
   - **OpenAPI/структура:** Swagger загейчен вне production (`NESTBOOT-14`); раскладка core/adapters/app, `core/` не импортит NestJS/TypeORM/`app/`, eslint + `tsc --noEmit` strict в CI (`NESTBOOT-15`, cross-ref `R-HEX-2`).

4. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

5. **Серьёзность** (`RFF-12`):
   - **Критично** — `synchronize: true` в production (`NESTBOOT-X4`), безусловный брокер/Redis-коннект на старте (`NESTBOOT-X5`), блокирующий sync в request-пути (`NESTBOOT-X6`), `core/` импортит фреймворк (`NESTBOOT-15`), секрет в git.
   - **Предупреждение** — `process.env` россыпью (`NESTBOOT-X1`), логика в `@Module`-фабриках (`NESTBOOT-X2`), `new Date()`/`randomUUID()` в домене (`NESTBOOT-X3`), нет раздельных health, миграции на старте приложения (`NESTBOOT-9`).
   - **Замечание** — нет README quickstart (`NESTBOOT-10`), Swagger не загейчен (`NESTBOOT-14`), eslint/tsc не в CI.

## Что не входит

- Бизнес-операции — `ucp-node-pattern-review`. Обработка ошибок — `ucp-node-error-handling-review`. Валидация — `ucp-node-validation-review`. Persistence-детали — `ucp-node-typeorm-review`.

$ARGUMENTS
