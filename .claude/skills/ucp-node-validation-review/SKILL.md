---
name: ucp-node-validation-review
lang: node
description: Ревью валидации входа в Node/NestJS (class-validator) по UCP (коды R-VLD-*) — DTO-классы с декораторами на границе, глобальный ValidationPipe, nested через @ValidateNested+@Type, custom ValidatorConstraint, валидируемый конфиг, деньги не number.
when_to_use: Изменения в DTO-классах, контроллерах, common/validation/ или конфиг-валидации.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации (Node / class-validator / NestJS)

Ты ревьюишь валидацию входа на соответствие **общему контракту** `backend/validation/validation-rules.md` (`R-VLD-*`)
и **Node-реализации** `backend/validation/node/validation-style-guide.md`. Помни инверсию: NestJS code-first
(DTO-класс с декораторами = источник, OpenAPI генерирует `@nestjs/swagger`) — актуально «нет дублей правил»,
не «не править generated».

## Зависимости

- **`.claude/docs/backend/validation/validation-rules.md`** — контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/node/validation-style-guide.md`** — class-validator-реализация.
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-MAP-2`), `backend/ddd-tactical/ddd-tactical-rules.md` (инварианты ≠ валидация), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-4` конфиг).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-VLD-WHERE-X1`), не префикс.

2. **Скоп.** `**/*request*.ts`, `**/*dto*.ts`, контроллеры, `common/validation/**`, `main.ts` (ValidationPipe), конфиг-классы/`validate`, `git diff` на `.ts`.

3. **Прогон.**
   - **WHERE:** входной DTO — класс с декораторами в сигнатуре контроллера, глобальный `ValidationPipe({ whitelist, forbidNonWhitelisted, transform })` с `exceptionFactory` → `InputValidationError`? (`R-VLD-WHERE-1`). Nested — `@ValidateNested` + `@Type` (без `@Type` останется plain)? (`R-VLD-WHERE-4`). Ручная `if ...: throw` в Handler → `R-VLD-WHERE-X1`. Декораторы на агрегате → `R-VLD-WHERE-X4`. Конфиг — `ConfigModule.forRoot({ validate })`? (`R-VLD-WHERE-2`/`CFG-1`).
   - **STD:** стандартные декораторы (`@IsEmail`/`@IsUUID`/`@Length`/`@Min`); required ровно одним декоратором; деньги — строка+decimal/`bigint`, не `number` (`R-VLD-STD-1..5`). `@IsDefined` поверх `@IsNotEmpty` → `R-VLD-STD-X1`; email-regex через `@Matches` → `R-VLD-STD-X2`; «всё-в-одном» кастомный валидатор → `R-VLD-STD-X3`.
   - **CC:** custom — пара `@ValidatorConstraint` + `registerDecorator` в `common/validation/`, имя по домену, `true` на null? Фейлит на null → `R-VLD-CC-X1`; в файле DTO → `R-VLD-CC-X2`; ad-hoc `@Validate(...)`-лямбда вместо переиспользуемой пары → `R-VLD-CC-X3`.
   - **XF:** cross-field — class-level custom validator с говорящим именем (`R-VLD-XF-1/2`); в Handler перед dispatch → `R-VLD-XF-X2`.
   - **GRP:** разные сценарии — отдельные классы; один класс с режимами → `R-VLD-GRP-X1`; DTO на 3+ сценария через groups → `R-VLD-GRP-X2`.
   - **OAS (code-first):** контракт = типизированный DTO-класс в сигнатуре (`@Body() req: CreateOrderRequest`), не `any`/интерфейс без декораторов (`R-VLD-OAS-X5` — интерфейсы стираются, пайп молча пропустит); дубли правил (декоратор + ручной чек) → `R-VLD-OAS-X4`; после маппинга в команду повторной валидации нет (`R-VLD-OAS-6`).
   - **CFG:** `validate` на старте fail-fast, required без default, nested валидируется; `process.env.X` для required → `R-VLD-CFG-X2` (`NESTBOOT-X1`); конфиг-класс без `validate` → `R-VLD-CFG-X1`.
   - **MSG:** сообщения на русском, человекочитаемые, плейсхолдеры; английский/тех-термины → `R-VLD-MSG-X1/X2`; копипаст message по полям → `R-VLD-MSG-X3`.

4. **Cross-check:** 400-маппинг/`exceptionFactory` → `ucp-node-error-handling-review` (`R-ERR-MAP-2`); доменные инварианты → `ucp-node-ddd-tactical-review`/`pattern`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — ручная input-валидация в Handler (`R-VLD-WHERE-X1`), inbound как `any`/интерфейс без декораторов (`R-VLD-OAS-X5`), nested без `@ValidateNested`+`@Type` (`R-VLD-WHERE-4`), деньги в `number`, `process.env` для required-конфига (`R-VLD-CFG-X2`).
   - **Предупреждение** — декораторы на агрегате (`R-VLD-WHERE-X4`), дубли правил (`R-VLD-OAS-X4`), констрейнт inline в DTO (`R-VLD-CC-X2`), констрейнт фейлит на null (`R-VLD-CC-X1`), email-regex вместо `@IsEmail` (`R-VLD-STD-X2`), нет глобального ValidationPipe.
   - **Замечание** — английский message (`R-VLD-MSG-X1`), неговорящее имя cross-field-валидатора (`R-VLD-XF-2`), один класс на 3+ сценария (`R-VLD-GRP-X2`), копипаст message (`R-VLD-MSG-X3`).

## Что не входит

- Маппинг ошибки в 400/problem+json — `ucp-node-error-handling-review`.
- Доменные инварианты — `ucp-node-ddd-tactical-review` / `ucp-node-pattern-review`.

$ARGUMENTS
