---
name: ucp-node-validation-design
lang: node
description: Спроектировать валидацию входа в NestJS-сервисе, class-validator (требования validation/*) — DTO-классы с декораторами на границе, глобальный ValidationPipe, custom через ValidatorConstraint, cross-field class-level декоратор, валидируемый конфиг.
when_to_use: Триггеры — «валидация запроса в NestJS», «DTO с декораторами для X», «настрой ValidationPipe». При новом эндпоинте/DTO/конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# Проектирование валидации (Node / class-validator / NestJS)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/spec.md` (`R-VLD-*`)
и его **Node-реализации** `backend/validation/references/node/implementation.md` (class-validator + class-transformer, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/spec.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/references/node/implementation.md` — NestJS-реализация (ValidationPipe/декораторы/ValidatorConstraint/конфиг).
   - `.claude/docs/backend/error-handling/spec.md` — как ошибка валидации станет 400 (`error-handling/domain-and-validation-mapping`, `exceptionFactory` → `InputValidationError`).

2. **Определи объект.** Входной HTTP-DTO эндпоинта / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (TypeScript strict; без комментариев; коды правил НЕ цитируй в коде):
   - Глобальный `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true })` в `main.ts` с `exceptionFactory` → `InputValidationError` (`validation/input-validated-at-edge`).
   - Входные DTO — классы с декораторами в сигнатуре контроллера; required по умолчанию, optional — `@IsOptional()` + `field?: T`; стандартные декораторы (`@IsEmail`/`@IsUUID`/`@Length`/`@Min`); nested — `@ValidateNested` + `@Type(...)`; деньги — строка + decimal-библиотека или `bigint`, не `number` (`R-VLD-STD-*`, `R-VLD-WHERE-1/4`).
   - Custom — пара `@ValidatorConstraint`-класс + декоратор через `registerDecorator` в `common/validation/`, имя по домену, `true` на null/undefined (`R-VLD-CC-*`).
   - Cross-field — class-level custom validator с говорящим именем (`DateRange`, `PasswordsMatch`) (`R-VLD-XF-1/2`).
   - Разные сценарии — отдельные классы (`CreateOrderRequest` vs `UpdateOrderRequest`), groups — только когда DTO реально один (`R-VLD-GRP-*`).
   - Конфиг — `ConfigModule.forRoot({ validate })` с class-validator-классом или zod-схемой, required без default, nested валидируется (`R-VLD-CFG-*`, `nest-bootstrap/config-validated-at-startup`).
   - Сообщения валидаторов — на русском, человекочитаемые, плейсхолдеры class-validator (`R-VLD-MSG-*`).

4. **Самопроверка** — чеклист из `node/implementation.md`.

5. **Финальный шаг:** предложи «запусти `ucp-node-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручная `if (req.x < 0) throw ...` в Handler (`validation/input-validated-at-edge`); повторная валидация UseCase-команды (`validation/no-revalidation-after-edge`).
- class-validator-декораторы на доменном агрегате (`validation/domain-invariants-in-aggregate`); инвариант — в конструкторе агрегата.
- nested без `@ValidateNested` + `@Type` — объект останется plain и не провалидируется (`validation/nested-validated-recursively`).
- `@Matches(emailRegex)` вместо `@IsEmail` (`validation/standard-constraints-preferred`); констрейнт, фейлящий на null (`validation/custom-constraint-null-safe`).
- Констрейнт-класс в файле DTO (`validation/custom-constraint-is-reusable`); inbound-DTO как `any`/интерфейс без декораторов (`validation/controller-implements-generated-contract`); деньги в `number`.
- `process.env.X` для required-конфига вместо валидируемого (`validation/config-validated-at-startup`, `nest-bootstrap/profile-from-typed-config`); дубли правил (`validation/single-source-of-truth`).
- Дефолтные английские сообщения / технические термины в пользовательском сообщении (`R-VLD-MSG-X1/X2`).

После работы скилла — обязательно `ucp-node-validation-review`.

$ARGUMENTS
