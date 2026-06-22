---
name: ucp-node-bootstrap-design
lang: node
description: Спроектировать или починить bootstrap NestJS-сервиса (коды NESTBOOT-*) — профили NODE_ENV, fail-fast валидация конфига, AppModule composition root, DI-токены портов + Clock/UuidProvider, TypeORM + миграции, гейтинг Kafka/Redis, terminus health.
when_to_use: Триггеры — «настрой bootstrap NestJS», «почему сервис не стартует». При старте сервиса или падении на конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(docker compose*)
---

# Проектирование bootstrap (Node / NestJS)

Ты настраиваешь bootstrap-слой NestJS-сервиса по UCP согласно `backend/node/nest-bootstrap/nest-bootstrap-rules.md`
(`NESTBOOT-*`). Цель — сервис стартует локально одной командой без живых внешних зависимостей кроме Postgres
(`NESTBOOT-1`), конфиг валидируется fail-fast, композиция декларативна, раскладка core/adapters/app соблюдена.

## Инструкции

1. **Прочитай** `.claude/docs/backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-*`). Связанные: `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-*` persistence), `backend/usecase-pattern/node/usecase-pattern-style-guide.md` (DI/Handler), `backend/error-handling/node/error-handling-style-guide.md` (`APP_FILTER`-регистрация).

2. **Диагноз: починка или с нуля.** Для починки сначала воспроизведи ошибку (`npm run start:dev`); пройди Quickstart-чеклист (§ конец rules) — missing env / Kafka без гейта / миграции не накатаны.

3. **Произведи код** (strict TypeScript; без комментариев; коды правил НЕ цитируй в коде):
   - `app/config.ts` — типизированный `AppConfig` + `ConfigModule.forRoot({ isGlobal: true, validate })` (class-validator-класс или zod-схема), required без default, per-профильные `envFilePath`-оверрайды по `NODE_ENV=local|integration-test|production`; гейты по `AppConfig.env`, не по `process.env` россыпью (`NESTBOOT-2/3/4`).
   - `app/app.module.ts` — composition root: только сборка, ноль бизнес-логики; feature-модуль на bounded context; провайдеры через DI-токены портов `{ provide: ORDER_REPOSITORY, useClass: TypeOrmOrderRepository }` (`NESTBOOT-5/6`).
   - `Clock`/`UuidProvider` — интерфейсы в `core/`, production-реализации в bootstrap-модуле, тест подменяет `overrideProvider` (`NESTBOOT-7`).
   - persistence: `TypeOrmModule.forRootAsync` с фабрикой от конфига; `synchronize: false` во всех профилях; миграции `typeorm migration:run` отдельной командой в CI/деплое (`NESTBOOT-8/9`).
   - гейтинг: Kafka-консьюмеры/Redis/schedulers — условно по профилю (динамический модуль/`useFactory`), off в local/integration-test (`NESTBOOT-11`).
   - `main.ts`: `app.enableShutdownHooks()`; Swagger (`SwaggerModule.setup`) только вне production (`NESTBOOT-12/14`).
   - health: `@nestjs/terminus` — `/health/live` и `/health/ready` раздельно (`NESTBOOT-13`).
   - раскладка `core/` (без NestJS/TypeORM-импортов), `adapters/in/http`, `adapters/out/*`, `app/`; `eslint` + `tsc --noEmit` (strict) в CI (`NESTBOOT-15`); README quickstart `docker compose up -d postgres && npm run migration:run && npm run start:dev` (`NESTBOOT-10`).

4. **Самопроверка** — Quickstart-чеклист из rules.

5. **Финальный шаг:** предложи `ucp-node-bootstrap-review`; для бизнес-операций — `ucp-node-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `process.env.FOO` россыпью вместо типизированного конфига (`NESTBOOT-X1`); логика/ветвления окружения в `@Module`-фабриках (`NESTBOOT-X2`).
- `new Date()`/`randomUUID()` напрямую в домене/хендлере вместо `Clock`/`UuidProvider` (`NESTBOOT-X3`).
- `synchronize: true` в production-конфиге (`NESTBOOT-X4`); безусловный `connectMicroservice(...)`/Redis-коннект на старте (`NESTBOOT-X5`).
- Блокирующие sync-вызовы (`fs.readFileSync`, тяжёлый CPU) в request-пути (`NESTBOOT-X6`); импорт `app/`/`adapters` из `core/` (`NESTBOOT-15`).

После работы скилла — обязательно `ucp-node-bootstrap-review`.

$ARGUMENTS
