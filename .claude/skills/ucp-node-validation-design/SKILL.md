---
name: ucp-node-validation-design
lang: node
description: Спроектировать валидацию входа в NestJS-сервисе, class-validator (коды R-VLD-*) — DTO-классы с декораторами на границе, глобальный ValidationPipe, custom через ValidatorConstraint, cross-field class-level декоратор, валидируемый конфиг.
when_to_use: Триггеры — «валидация запроса в NestJS», «DTO с декораторами для X», «настрой ValidationPipe». При новом эндпоинте/DTO/конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# Проектирование валидации (Node / class-validator / NestJS)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/validation-rules.md` (`R-VLD-*`)
и его **Node-реализации** `backend/validation/node/validation-style-guide.md` (class-validator + class-transformer, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/validation-rules.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/node/validation-style-guide.md` — NestJS-реализация (ValidationPipe/декораторы/ValidatorConstraint/конфиг).
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — как ошибка валидации станет 400 (`R-ERR-MAP-2`, `exceptionFactory` → `InputValidationError`).

2. **Определи объект.** Входной HTTP-DTO эндпоинта / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (TypeScript strict; без комментариев; коды правил НЕ цитируй в коде):
   - Глобальный `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true })` в `main.ts` с `exceptionFactory` → `InputValidationError` (`R-VLD-WHERE-1`).
   - Входные DTO — классы с декораторами в сигнатуре контроллера; required по умолчанию, optional — `@IsOptional()` + `field?: T`; стандартные декораторы (`@IsEmail`/`@IsUUID`/`@Length`/`@Min`); nested — `@ValidateNested` + `@Type(...)`; деньги — строка + decimal-библиотека или `bigint`, не `number` (`R-VLD-STD-*`, `R-VLD-WHERE-1/4`).
   - Custom — пара `@ValidatorConstraint`-класс + декоратор через `registerDecorator` в `common/validation/`, имя по домену, `true` на null/undefined (`R-VLD-CC-*`).
   - Cross-field — class-level custom validator с говорящим именем (`DateRange`, `PasswordsMatch`) (`R-VLD-XF-1/2`).
   - Разные сценарии — отдельные классы (`CreateOrderRequest` vs `UpdateOrderRequest`), groups — только когда DTO реально один (`R-VLD-GRP-*`).
   - Конфиг — `ConfigModule.forRoot({ validate })` с class-validator-классом или zod-схемой, required без default, nested валидируется (`R-VLD-CFG-*`, `NESTBOOT-4`).
   - Сообщения валидаторов — на русском, человекочитаемые, плейсхолдеры class-validator (`R-VLD-MSG-*`).

4. **Самопроверка** — чеклист из `node/validation-style-guide.md`.

5. **Финальный шаг:** предложи «запусти `ucp-node-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручная `if (req.x < 0) throw ...` в Handler (`R-VLD-WHERE-X1`); повторная валидация UseCase-команды (`R-VLD-WHERE-X2`).
- class-validator-декораторы на доменном агрегате (`R-VLD-WHERE-X4`); инвариант — в конструкторе агрегата.
- nested без `@ValidateNested` + `@Type` — объект останется plain и не провалидируется (`R-VLD-WHERE-4`).
- `@Matches(emailRegex)` вместо `@IsEmail` (`R-VLD-STD-X2`); констрейнт, фейлящий на null (`R-VLD-CC-X1`).
- Констрейнт-класс в файле DTO (`R-VLD-CC-X2`); inbound-DTO как `any`/интерфейс без декораторов (`R-VLD-OAS-X5`); деньги в `number`.
- `process.env.X` для required-конфига вместо валидируемого (`R-VLD-CFG-X2`, `NESTBOOT-X1`); дубли правил (`R-VLD-OAS-X4`).
- Дефолтные английские сообщения / технические термины в пользовательском сообщении (`R-VLD-MSG-X1/X2`).

После работы скилла — обязательно `ucp-node-validation-review`.

$ARGUMENTS
