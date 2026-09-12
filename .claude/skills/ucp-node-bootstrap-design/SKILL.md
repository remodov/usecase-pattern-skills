---
name: ucp-node-bootstrap-design
lang: node
description: Спроектировать или починить bootstrap NestJS-сервиса — профили NODE_ENV, fail-fast валидация конфига, AppModule composition root, DI-токены портов + Clock/UuidProvider, TypeORM + миграции, гейтинг Kafka/Redis, terminus health.
when_to_use: Триггеры — «настрой bootstrap NestJS», «почему сервис не стартует». При старте сервиса или падении на конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(docker compose*)
---

# Проектирование bootstrap (Node / NestJS)

Ты настраиваешь bootstrap-слой NestJS-сервиса по UCP согласно `backend/node/nest-bootstrap/spec.md`
(`NESTBOOT-*`). Цель — сервис стартует локально одной командой без живых внешних зависимостей кроме Postgres
(`nest-bootstrap/starts-locally-without-externals`), конфиг валидируется fail-fast, композиция декларативна, раскладка core/adapters/app соблюдена.

## Инструкции

1. **Прочитай** `.claude/docs/backend/node/nest-bootstrap/spec.md` (`NESTBOOT-*`). Связанные: `backend/node/typeorm/spec.md` (`R-TYPEORM-*` persistence), `backend/usecase-pattern/references/node/implementation.md` (DI/Handler), `backend/error-handling/references/node/implementation.md` (`APP_FILTER`-регистрация).

2. **Диагноз: починка или с нуля.** Для починки сначала воспроизведи ошибку (`npm run start:dev`); пройди Quickstart-чеклист (§ конец rules) — missing env / Kafka без гейта / миграции не накатаны.

3. **Произведи код** (strict TypeScript; без комментариев; коды правил НЕ цитируй в коде):
   - `app/config.ts` — типизированный `AppConfig` + `ConfigModule.forRoot({ isGlobal: true, validate })` (class-validator-класс или zod-схема), required без default, per-профильные `envFilePath`-оверрайды по `NODE_ENV=local|integration-test|production`; гейты по `AppConfig.env`, не по `process.env` россыпью (`NESTBOOT-2/3/4`).
   - `app/app.module.ts` — composition root: только сборка, ноль бизнес-логики; feature-модуль на bounded context; провайдеры через DI-токены портов `{ provide: ORDER_REPOSITORY, useClass: TypeOrmOrderRepository }` (`NESTBOOT-5/6`).
   - `Clock`/`UuidProvider` — интерфейсы в `core/`, production-реализации в bootstrap-модуле, тест подменяет `overrideProvider` (`nest-bootstrap/clock-and-ids-behind-tokens`).
   - persistence: `TypeOrmModule.forRootAsync` с фабрикой от конфига; `synchronize: false` во всех профилях; миграции `typeorm migration:run` отдельной командой в CI/деплое (`NESTBOOT-8/9`).
   - гейтинг: Kafka-консьюмеры/Redis/schedulers — условно по профилю (динамический модуль/`useFactory`), off в local/integration-test (`nest-bootstrap/broker-and-cache-are-conditional`).
   - `main.ts`: `app.enableShutdownHooks()`; Swagger (`SwaggerModule.setup`) только вне production (`NESTBOOT-12/14`).
   - health: `@nestjs/terminus` — `/health/live` и `/health/ready` раздельно (`nest-bootstrap/liveness-and-readiness-split`).
   - раскладка `core/` (без NestJS/TypeORM-импортов), `adapters/in/http`, `adapters/out/*`, `app/`; `eslint` + `tsc --noEmit` (strict) в CI (`nest-bootstrap/layout-directs-dependencies-inward`); README quickstart `docker compose up -d postgres && npm run migration:run && npm run start:dev` (`nest-bootstrap/local-quickstart-documented`).

4. **Самопроверка** — Quickstart-чеклист из rules.

5. **Финальный шаг:** предложи `ucp-node-bootstrap-review`; для бизнес-операций — `ucp-node-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `process.env.FOO` россыпью вместо типизированного конфига (`nest-bootstrap/profile-from-typed-config`); логика/ветвления окружения в `@Module`-фабриках (`nest-bootstrap/root-module-is-composition-only`).
- `new Date()`/`randomUUID()` напрямую в домене/хендлере вместо `Clock`/`UuidProvider` (`nest-bootstrap/clock-and-ids-behind-tokens`).
- `synchronize: true` в production-конфиге (`nest-bootstrap/datasource-and-migrations`); безусловный `connectMicroservice(...)`/Redis-коннект на старте (`nest-bootstrap/broker-and-cache-are-conditional`).
- Блокирующие sync-вызовы (`fs.readFileSync`, тяжёлый CPU) в request-пути (`nest-bootstrap/no-blocking-in-request-path`); импорт `app/`/`adapters` из `core/` (`nest-bootstrap/layout-directs-dependencies-inward`).

После работы скилла — обязательно `ucp-node-bootstrap-review`.

$ARGUMENTS

## Гейты проекта

Каталог — `.claude/docs/_meta/project-gates.md`. Эти проверки методология
определяет сама, и генерируешь их **ты**: пока их нет в проекте, требования,
которые на них ссылаются, фактически держатся ревью.

Сгенерируй четыре скрипта и привяжи их к общей задаче проверки и в конвейер:

| Скрипт | Что читает | Что делает |
| --- | --- | --- |
| `ddl-check` | файлы миграций | разбирает объявления таблиц, колонок, индексов и ограничений; проверяет типы, именование, безопасность изменений |
| `config-check` | конфигурацию по профилям | сверяет значения, от которых зависит поведение под отказом: брокер, кеш, пул, обслуживание, остановка, устойчивость |
| `manifest-check` | манифесты развёртывания | сверяет бюджет остановки, паузу перед ней, раздельные пробы, правила обновления, запуск не от суперпользователя |
| `test-lint` | исходники тестов | ловит ожидания, обращения к настоящим часам, контейнеры брокера в подготовке, подмену портов в интеграционных тестах |

Полный перечень проверок каждого скрипта — таблицы каталога. Каждая строка
таблицы называет требование, которое проверка закрывает: **проверка без
требования не заводится**, требование без проверки остаётся с гейтом `ревью`.

Структурные правила этого трека — контракт импортов и запреты зависимостей;
их набор перечислен в полях «Гейт» самих требований. Правила, названные
в каталоге для Java, здесь остаются на ревью — это записано в поле «Не ловит»
соответствующих требований, выдумывать им аналоги не нужно.

Проверка, которую сервис не может пройти сразу, заводится **с файлом
исключений** — по образцу подавлений анализаторов: причина и срок. Отключать
проверку целиком нельзя.
