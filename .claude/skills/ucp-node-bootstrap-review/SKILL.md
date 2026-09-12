---
name: ucp-node-bootstrap-review
lang: node
description: Ревью bootstrap NestJS-сервиса (Node) по UCP — валидируемый конфиг fail-fast, AppModule без логики, DI-токены портов, Clock/UuidProvider, TypeORM без synchronize, гейтинг Kafka/Redis, health live/ready, core/ без фреймворка.
when_to_use: Изменения в main.ts, app.module.ts, конфиге, data-source/миграционной обвязке или feature-модулях.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью bootstrap (Node / NestJS)

Ты ревьюишь bootstrap-слой NestJS-сервиса на соответствие `backend/node/nest-bootstrap/spec.md` (`NESTBOOT-*`).

## Зависимости

- **`.claude/docs/backend/node/nest-bootstrap/spec.md`** — правила `NESTBOOT-*`.
- Парные: `backend/node/typeorm/spec.md` (`R-TYPEORM-*`), `backend/usecase-pattern/node/...` (DI/Handler), `backend/error-handling/node/...` (filters в композиции), `backend/auth-patterns/spec.md` (`AUTH-16/17`).

## Инструкции

1. **Прочти** `nest-bootstrap/spec.md`. Цитируй конкретные коды (`nest-bootstrap/datasource-and-migrations`), не префикс.

2. **Скоп.** `main.ts`, `app.module.ts`, конфиг (`config.ts`/`ConfigModule`), feature-модули, `data-source.ts`/миграционная обвязка, `package.json`-скрипты, `docker-compose.yml`; `git diff`.

3. **Прогон.**
   - **Конфиг:** `ConfigModule.forRoot({ validate })` с типизированной схемой, `NODE_ENV=local|integration-test|production`, required без default, fail-fast? Секреты не в git? (`NESTBOOT-2/3/4`). `process.env.FOO` россыпью → `nest-bootstrap/profile-from-typed-config`.
   - **Композиция:** `AppModule` — только сборка? Feature-модуль на bounded context? Провайдеры через DI-токены портов из `core/`? (`NESTBOOT-5/6`). Логика/env-ветвления в `@Module`-фабриках → `nest-bootstrap/root-module-is-composition-only`.
   - **DI:** `Clock`/`UuidProvider` за токенами, production-реализации в bootstrap? (`nest-bootstrap/clock-and-ids-behind-tokens`). `new Date()`/`randomUUID()` в домене/хендлере → `nest-bootstrap/clock-and-ids-behind-tokens`.
   - **Persistence:** `TypeOrmModule.forRootAsync` от конфига, один DataSource; миграции отдельной командой, `synchronize: false` (`NESTBOOT-8/9`). `synchronize: true` в production → `nest-bootstrap/datasource-and-migrations`.
   - **Гейтинг:** Kafka/Redis/schedulers подключаются по профилю, off в local/integration-test (`nest-bootstrap/broker-and-cache-are-conditional`). Безусловный `connectMicroservice`/Redis-коннект → `nest-bootstrap/broker-and-cache-are-conditional`.
   - **Server/health:** `enableShutdownHooks()` (`nest-bootstrap/shutdown-hooks-enabled`); `/health/live` + `/health/ready` раздельно через terminus (`nest-bootstrap/liveness-and-readiness-split`). Блокирующий sync-вызов в request-пути → `nest-bootstrap/no-blocking-in-request-path`.
   - **OpenAPI/структура:** Swagger загейчен вне production (`nest-bootstrap/api-docs-outside-production`); раскладка core/adapters/app, `core/` не импортит NestJS/TypeORM/`app/`, eslint + `tsc --noEmit` strict в CI (`nest-bootstrap/layout-directs-dependencies-inward`, cross-ref `hexagonal/core-free-of-framework`).

4. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

5. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `synchronize: true` в production (`nest-bootstrap/datasource-and-migrations`), безусловный брокер/Redis-коннект на старте (`nest-bootstrap/broker-and-cache-are-conditional`), блокирующий sync в request-пути (`nest-bootstrap/no-blocking-in-request-path`), `core/` импортит фреймворк (`nest-bootstrap/layout-directs-dependencies-inward`), секрет в git.
   - **Предупреждение** — `process.env` россыпью (`nest-bootstrap/profile-from-typed-config`), логика в `@Module`-фабриках (`nest-bootstrap/root-module-is-composition-only`), `new Date()`/`randomUUID()` в домене (`nest-bootstrap/clock-and-ids-behind-tokens`), нет раздельных health, миграции на старте приложения (`nest-bootstrap/datasource-and-migrations`).
   - **Замечание** — нет README quickstart (`nest-bootstrap/local-quickstart-documented`), Swagger не загейчен (`nest-bootstrap/api-docs-outside-production`), eslint/tsc не в CI.

## Что не входит

- Бизнес-операции — `ucp-node-pattern-review`. Обработка ошибок — `ucp-node-error-handling-review`. Валидация — `ucp-node-validation-review`. Persistence-детали — `ucp-node-typeorm-review`.

$ARGUMENTS
