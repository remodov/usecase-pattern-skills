---
name: ucp-node-validation-review
lang: node
description: Ревью валидации входа в Node/NestJS (class-validator) по UCP — DTO-классы с декораторами на границе, глобальный ValidationPipe, nested через @ValidateNested+@Type, custom ValidatorConstraint, валидируемый конфиг, деньги не number.
when_to_use: Изменения в DTO-классах, контроллерах, common/validation/ или конфиг-валидации.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации (Node / class-validator / NestJS)

Ты ревьюишь валидацию входа на соответствие **общему контракту** `backend/validation/spec.md` (`R-VLD-*`)
и **Node-реализации** `backend/validation/references/node/implementation.md`. Помни инверсию: NestJS code-first
(DTO-класс с декораторами = источник, OpenAPI генерирует `@nestjs/swagger`) — актуально «нет дублей правил»,
не «не править generated».

## Зависимости

- **`.claude/docs/backend/validation/spec.md`** — контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/references/node/implementation.md`** — class-validator-реализация.
- Парные: `backend/error-handling/spec.md` (`error-handling/domain-and-validation-mapping`), `backend/ddd-tactical/spec.md` (инварианты ≠ валидация), `backend/node/nest-bootstrap/spec.md` (`nest-bootstrap/config-validated-at-startup` конфиг).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`validation/input-validated-at-edge`), не префикс.

2. **Скоп.** `**/*request*.ts`, `**/*dto*.ts`, контроллеры, `common/validation/**`, `main.ts` (ValidationPipe), конфиг-классы/`validate`, `git diff` на `.ts`.

3. **Прогон.**
   - **WHERE:** входной DTO — класс с декораторами в сигнатуре контроллера, глобальный `ValidationPipe({ whitelist, forbidNonWhitelisted, transform })` с `exceptionFactory` → `InputValidationError`? (`validation/input-validated-at-edge`). Nested — `@ValidateNested` + `@Type` (без `@Type` останется plain)? (`validation/nested-validated-recursively`). Ручная `if ...: throw` в Handler → `validation/input-validated-at-edge`. Декораторы на агрегате → `validation/domain-invariants-in-aggregate`. Конфиг — `ConfigModule.forRoot({ validate })`? (`validation/config-validated-at-startup`/`CFG-1`).
   - **STD:** стандартные декораторы (`@IsEmail`/`@IsUUID`/`@Length`/`@Min`); required ровно одним декоратором; деньги — строка+decimal/`bigint`, не `number` (`R-VLD-STD-1..5`). `@IsDefined` поверх `@IsNotEmpty` → `validation/no-false-or-composite-constraints`; email-regex через `@Matches` → `validation/standard-constraints-preferred`; «всё-в-одном» кастомный валидатор → `validation/no-false-or-composite-constraints`.
   - **CC:** custom — пара `@ValidatorConstraint` + `registerDecorator` в `common/validation/`, имя по домену, `true` на null? Фейлит на null → `validation/custom-constraint-null-safe`; в файле DTO → `validation/custom-constraint-is-reusable`; ad-hoc `@Validate(...)`-лямбда вместо переиспользуемой пары → `validation/custom-constraint-is-reusable`.
   - **XF:** cross-field — class-level custom validator с говорящим именем (`R-VLD-XF-1/2`); в Handler перед dispatch → `validation/cross-field-rules-on-object`.
   - **GRP:** разные сценарии — отдельные классы; один класс с режимами → `validation/scenario-groups-are-narrow`; DTO на 3+ сценария через groups → `validation/scenario-groups-are-narrow`.
   - **OAS (code-first):** контракт = типизированный DTO-класс в сигнатуре (`@Body() req: CreateOrderRequest`), не `any`/интерфейс без декораторов (`validation/controller-implements-generated-contract` — интерфейсы стираются, пайп молча пропустит); дубли правил (декоратор + ручной чек) → `validation/single-source-of-truth`; после маппинга в команду повторной валидации нет (`validation/no-revalidation-after-edge`).
   - **CFG:** `validate` на старте fail-fast, required без default, nested валидируется; `process.env.X` для required → `validation/config-validated-at-startup` (`nest-bootstrap/profile-from-typed-config`); конфиг-класс без `validate` → `validation/config-validated-at-startup`.
   - **MSG:** сообщения на русском, человекочитаемые, плейсхолдеры; английский/тех-термины → `R-VLD-MSG-X1/X2`; копипаст message по полям → `validation/no-duplicated-messages`.

4. **Cross-check:** 400-маппинг/`exceptionFactory` → `ucp-node-error-handling-review` (`error-handling/domain-and-validation-mapping`); доменные инварианты → `ucp-node-ddd-tactical-review`/`pattern`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — ручная input-валидация в Handler (`validation/input-validated-at-edge`), inbound как `any`/интерфейс без декораторов (`validation/controller-implements-generated-contract`), nested без `@ValidateNested`+`@Type` (`validation/nested-validated-recursively`), деньги в `number`, `process.env` для required-конфига (`validation/config-validated-at-startup`).
   - **Предупреждение** — декораторы на агрегате (`validation/domain-invariants-in-aggregate`), дубли правил (`validation/single-source-of-truth`), констрейнт inline в DTO (`validation/custom-constraint-is-reusable`), констрейнт фейлит на null (`validation/custom-constraint-null-safe`), email-regex вместо `@IsEmail` (`validation/standard-constraints-preferred`), нет глобального ValidationPipe.
   - **Замечание** — английский message (`validation/message-in-user-language`), неговорящее имя cross-field-валидатора (`validation/cross-field-rules-on-object`), один класс на 3+ сценария (`validation/scenario-groups-are-narrow`), копипаст message (`validation/no-duplicated-messages`).

## Что не входит

- Маппинг ошибки в 400/problem+json — `ucp-node-error-handling-review`.
- Доменные инварианты — `ucp-node-ddd-tactical-review` / `ucp-node-pattern-review`.

$ARGUMENTS
