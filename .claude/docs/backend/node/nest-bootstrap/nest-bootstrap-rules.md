# Nest Bootstrap — индекс правил (NestJS)

> **Что это.** Bootstrap-конфигурация NestJS-сервиса по UCP: профили, модульная композиция, DI, конфиг,
> persistence-wiring, server, health. Языко-специфичный concern Node-биндинга (аналог Java `spring-bootstrap` /
> `BS-*` и Python `python-bootstrap` / `PYBOOT-*`) — **только Node**, своя пара кодов `NESTBOOT-*`.
> Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет).
> Коды: `NESTBOOT-<N>` — обязательно, `NESTBOOT-X<N>` — антипаттерн (запрещено).

Базовый принцип (`NESTBOOT-1`): **сервис запускается локально одной командой, без живых внешних зависимостей** (кроме Postgres из docker-compose). Нужен живой Keycloak/Kafka для `npm run start:dev` — баг настройки.

## 1. Профили и конфиг
**MUST:**
- **NESTBOOT-2.** Три состояния через `NODE_ENV=local|integration-test|production`: production (реальные сервисы), local (Postgres docker-compose, auth off, внешние URL на dev), integration-test (Postgres + nock/msw-стабы, фоновые consumers off). Per-профильные оверрайды — `envFilePath` в `ConfigModule` (`.env.local` поверх production-defaults), не дублирование всей конфигурации.
- **NESTBOOT-3.** Профиль не активируется кодом — только через env. Код, специфичный профилю, гейтится по типизированному `AppConfig.env`, не по `process.env.NODE_ENV` россыпью.
- **NESTBOOT-4.** Конфиг валидируется на старте (fail-fast): `ConfigModule.forRoot({ validate })` с class-validator-классом или zod-схемой; required-поля без default, типобезопасно. Секреты — из env/Vault, не в коде и не в `.env` в git (cross-ref `AUTH-17`).

```ts
ConfigModule.forRoot({ isGlobal: true, validate: (env) => AppConfigSchema.parse(env) })
```

**MUST NOT:**
- **NESTBOOT-X1.** `process.env.FOO` россыпью по коду вместо инжектируемого типизированного конфига — нетипизировано, не валидируется, тесты не подменяют.

## 2. Модульная композиция
**MUST:**
- **NESTBOOT-5.** `AppModule` — composition root: только сборка модулей/провайдеров, ноль бизнес-логики. Feature-модуль на bounded context: контроллеры + handlers + порты с реализациями.
- **NESTBOOT-6.** Провайдеры регистрируются через DI-токены портов: `{ provide: ORDER_REPOSITORY, useClass: TypeOrmOrderRepository }`. Handler зависит от токена порта из `core/`, не от класса реализации (cross-ref `R-HND-2`, `R-HEX-2`).

**MUST NOT:**
- **NESTBOOT-X2.** Бизнес-логика или условные ветвления окружения внутри `@Module`-декораторов/фабрик модулей — модуль декларативная сборка, решения — в конфиге.

## 3. DI: детерминизм (Clock / UuidProvider)
**MUST:**
- **NESTBOOT-7.** Источники недетерминизма (время, UUID, random) — за интерфейсом в `core/` (`Clock`, `UuidProvider`), инжектятся как токены; production-реализация — в bootstrap-модуле, тест подменяет через `overrideProvider` (cross-ref `R-HND-5`, `TS-7`).

**MUST NOT:**
- **NESTBOOT-X3.** `new Date()` / `randomUUID()` напрямую в домене/хендлере — недетерминированные тесты; только через `Clock`/`UuidProvider`.

## 4. Persistence-wiring (TypeORM)
**MUST:**
- **NESTBOOT-8.** `TypeOrmModule.forRootAsync` с фабрикой от типизированного конфига; DataSource один на приложение. Persistence-правила — `typeorm-rules.md` (`R-TYPEORM-*`).
- **NESTBOOT-9.** Миграции — отдельной командой `typeorm migration:run` в CI/деплое, не в коде приложения на старте; `synchronize: false` во всех профилях.
- **NESTBOOT-10.** Локальный quickstart документирован в README: `docker compose up -d postgres && npm run migration:run && npm run start:dev`.

**MUST NOT:**
- **NESTBOOT-X4.** `synchronize: true` в production-конфиге — авто-DDL мимо миграций, потеря данных при изменении Entity (cross-ref `PG-M-*`).

## 5. Гейтинг внешних подключений
**MUST:**
- **NESTBOOT-11.** Без живых Kafka/Redis сервис **стартует**: Kafka-консьюмеры, Redis-клиент, schedulers подключаются условно по профилю (динамический модуль/`useFactory` от конфига) — off в local/integration-test. В тестах consumer вызывается напрямую, без embedded broker (cross-ref `BS-13`-интент).

**MUST NOT:**
- **NESTBOOT-X5.** Безусловный `app.connectMicroservice(...)`/Redis-коннект на старте — local-запуск падает без брокера, нарушает `NESTBOOT-1`.

## 6. Server, shutdown, health
**MUST:**
- **NESTBOOT-12.** `app.enableShutdownHooks()` в `main.ts` — закрытие DataSource/клиентов на SIGTERM через `OnApplicationShutdown` (cross-ref graceful-shutdown-интент).
- **NESTBOOT-13.** Health-эндпоинты через `@nestjs/terminus`: `/health/live` (процесс жив) и `/health/ready` (зависимости готовы) — раздельно.

**MUST NOT:**
- **NESTBOOT-X6.** Блокирующие sync-вызовы (`fs.readFileSync`, тяжёлый CPU) в request-пути — блокируют event loop; worker_threads или вынос из горячего пути.

## 7. OpenAPI и структура
**MUST:**
- **NESTBOOT-14.** Swagger (`@nestjs/swagger` + `SwaggerModule.setup`) включается только вне production (гейт по конфигу); контракт — по `rest-api-rules.md` (`R-OAS-*`).
- **NESTBOOT-15.** Раскладка: `core/` (домен + usecases + порты, без NestJS/TypeORM-импортов), `adapters/in/http`, `adapters/out/{persistence,...}`, `app/` (main, AppModule, конфиг). `eslint` + `tsc --noEmit` (strict) в CI. Импорт `app/`/`adapters` из `core/` запрещён (cross-ref `R-HEX-2`).

## Quickstart-чеклист (сервис не стартует)
1. `NODE_ENV` выставлен? (`local` для разработки)
2. Конфиг-валидация — нет ли missing required env (ошибка должна быть на старте, не на первом запросе)?
3. Postgres поднят (`docker compose up -d postgres`)? Миграции накатаны (`npm run migration:run`)?
4. Kafka/Redis-подключения загейчены по профилю (`NESTBOOT-X5`)?
5. На production-старте auth/JWKS — ленивый, сервис стартует без живого IdP (cross-ref `BS-7`-интент).
