# Validation — реализация на Node (class-validator / class-transformer / NestJS)

Реализация язык-нейтрального контракта `../spec.md` (`R-VLD-*`) на NestJS.
Коды — общие с Java и Python; здесь — идиомы class-validator + class-transformer.

> **Парадигма.** NestJS **code-first** (как Python): DTO-класс с декораторами — **источник правды** валидации
> входа, OpenAPI генерируется из него (`@nestjs/swagger`). «Не править generated руками» (`validation/generated-artifacts-immutable`)
> неактуально; актуально «DTO-класс = контракт, без дублей» (`validation/single-source-of-truth`). Точка входа — **глобальный
> `ValidationPipe`** в `main.ts`, один на приложение.

---

## 1. Где валидируем — `R-VLD-WHERE-*`

`validation/input-validated-at-edge` — входной DTO — класс с class-validator-декораторами в сигнатуре контроллера; валидирует
глобальный `ValidationPipe` до Handler; невалидное → 400 problem+json через `exceptionFactory`
(cross-ref `error-handling/domain-and-validation-mapping`, `backend/error-handling/node`):

```ts
// main.ts — один глобальный pipe
app.useGlobalPipes(new ValidationPipe({
  whitelist: true, forbidNonWhitelisted: true,   // неизвестные поля → 400 (ловит опечатки клиента)
  transform: true,                               // plain → instance, приведение типов query/path
  exceptionFactory: (errs) => new InputValidationError(formatViolations(errs)),
}));

export class CreateOrderRequest {
  @IsUUID()
  customerId: string;

  @ValidateNested({ each: true })   // nested — рекурсивно (R-VLD-WHERE-4)
  @Type(() => OrderItemRequest)     // class-transformer обязателен для nested
  @ArrayMinSize(1)
  items: OrderItemRequest[];
}
```

`validation/config-validated-at-startup` — конфиг валидируется на старте: `ConfigModule.forRoot({ validate })` — fail-fast (см. §7, `nest-bootstrap/config-validated-at-startup`).
`validation/domain-invariants-in-aggregate` — доменные инварианты — в агрегате (`Order.create(...)` бросает `DomainError`), не в class-validator (cross-ref `R-AGG-*`).
`validation/nested-validated-recursively` — nested — `@ValidateNested` + `@Type(...)`; без `@Type` объект останется plain и не провалидируется.

`validation/input-validated-at-edge` ❌ ручная `if (req.amount < 0) throw ...` в Handler — правило DTO → декоратор (`@Min(0)`), инвариант → агрегат.
`validation/no-revalidation-after-edge` ❌ повторная валидация UseCase-команды (она — plain-объект из уже чистого DTO). `validation/config-validated-at-startup` ❌ конфиг без валидации (§7).
`validation/domain-invariants-in-aggregate` ❌ class-validator-декораторы на доменном агрегате — домен без фреймворка; инвариант в конструкторе.

---

## 2. Стандартные constraints — `R-VLD-STD-*`

`validation/standard-constraints-preferred` — required по умолчанию (нет `@IsOptional`); пустая строка — `@IsNotEmpty`; optional — `@IsOptional()` + `field?: T`.
`validation/standard-constraints-preferred` — размеры — `@Length(min, max)` / `@ArrayMinSize`, числа — `@Min`/`@Max`.
`validation/standard-constraints-preferred` — формат — стандартные декораторы (`@IsEmail`, `@IsUUID`, `@IsUrl`, `@IsISO8601`), не самописный `@Matches`.
`validation/standard-constraints-preferred` — время — `@IsISO8601()` (string-DTO) или `@Type(() => Date)` + `@MinDate`/`@MaxDate`.
`validation/standard-constraints-preferred` — валидация на правильном типе: число — `@IsInt`/`@Min` на `number` (`transform: true` приводит query-строки); деньги — строка + decimal-библиотека или `bigint` в миноре, не `number`.

`validation/no-false-or-composite-constraints` ❌ дублирование required-проверки (`@IsDefined` поверх `@IsNotEmpty`) — TS-типы стираются в runtime, поэтому один required-декоратор нужен, но ровно один.
`validation/standard-constraints-preferred` ❌ `@Matches(emailRegex)` вместо `@IsEmail`. `validation/no-false-or-composite-constraints` ❌ «всё-в-одном» кастомный валидатор вместо комбинации стандартных.

---

## 3. Custom constraints — `R-VLD-CC-*`

`validation/custom-constraint-is-reusable` — переиспользуемый constraint — пара `@ValidatorConstraint`-класс + декоратор-обёртка через `registerDecorator`:

```ts
// common/validation/russian-phone.ts
@ValidatorConstraint({ name: 'russianPhone' })
export class RussianPhoneConstraint implements ValidatorConstraintInterface {
  validate(value: unknown): boolean {
    if (value === null || value === undefined) return true;   // null — отдельной проверкой (R-VLD-CC-4)
    return typeof value === 'string' && RU_PHONE.test(value);
  }
  defaultMessage(): string { return 'Неверный формат телефона'; }
}

export function RussianPhone(options?: ValidationOptions) {
  return (object: object, propertyName: string) => registerDecorator(
    { target: object.constructor, propertyName, options, validator: RussianPhoneConstraint });
}
```

`validation/custom-constraint-is-reusable` — в общем модуле `common/validation/`, не inline в DTO. `validation/custom-constraint-named-by-domain` — имя по домену
(`RussianPhone`, `VatNumber`), без `Valid`/`Check`/`Is`. `validation/custom-constraint-null-safe` — на null/undefined возвращает `true`;
required — комбинацией с `@IsNotEmpty`. `validation/constraint-is-stateless` — stateless чистая функция; зависимость (справочник) —
только осознанно (`useContainer(app, ...)` для DI в констрейнт).

`validation/custom-constraint-null-safe` ❌ констрейнт падает/фейлит на null — ломает композицию с required. `validation/custom-constraint-is-reusable` ❌ констрейнт-класс
в файле DTO. `validation/custom-constraint-is-reusable` ❌ невыносимая логика в ad-hoc `@Validate(...)`-лямбде вместо переиспользуемой пары.

---

## 4. Сценарии (groups) — `R-VLD-GRP-*`

`validation/scenario-groups-are-narrow` — class-validator поддерживает `groups` (`@IsNotEmpty({ groups: ['create'] })` +
`new ValidationPipe({ groups: [...] })` на конкретном эндпоинте) — допустимо, только когда DTO реально один;
идиома по умолчанию — **отдельные классы** (`CreateOrderRequest` vs `UpdateOrderRequest`), как в Python.
`validation/scenario-marker-documented` — имя группы — документированная константа, не магическая строка по месту.
`validation/scenario-groups-are-narrow` ❌ один класс с режимами «строгий/мягкий» — два разных класса. `validation/scenario-groups-are-narrow` ❌ DTO,
обслуживающий 3+ сценария через группы, — разбить.

---

## 5. Cross-field — `R-VLD-XF-*`

`validation/cross-field-rules-on-object` — правило с 2+ полями — **class-level** custom validator (декоратор на классе):

```ts
@ValidatorConstraint({ name: 'dateRange' })
class DateRangeConstraint implements ValidatorConstraintInterface {
  validate(_: unknown, args: ValidationArguments): boolean {
    const o = args.object as { start: string; end: string };
    return o.end >= o.start;
  }
  defaultMessage(): string { return 'Дата окончания раньше даты начала'; }
}
export function DateRange(options?: ValidationOptions) {        // декоратор на класс
  return (target: Function) => registerDecorator(
    { target, propertyName: undefined as never, options, validator: DateRangeConstraint });
}

@DateRange()
export class PeriodRequest { @IsISO8601() start: string; @IsISO8601() end: string; }
```

`validation/cross-field-rules-on-object` — имя описывает правило (`DateRange`, `PasswordsMatch`), не объект.
`validation/cross-field-rules-on-object` ❌ одноразовый ad-hoc чек, если правило встречается в нескольких DTO — выносить в `common/validation/`.
`validation/cross-field-rules-on-object` ❌ cross-field-проверка в Handler перед dispatch — место на DTO.

---

## 6. Контракт-схема — `R-VLD-OAS-*`

`validation/single-source-of-truth` — **code-first**: DTO-класс — источник; OpenAPI генерирует `@nestjs/swagger` (CLI-plugin снимает
constraints с декораторов в схему); правило живёт в одном месте — в DTO. `validation/controller-implements-generated-contract` — контракт =
типизированный DTO-класс в сигнатуре контроллера (`@Body() req: CreateOrderRequest`), не `@Body() body: any`.
`validation/no-revalidation-after-edge` — после маппинга в UseCase-команду повторной валидации нет; домен-инварианты — на агрегате.

`validation/single-source-of-truth` ❌ дублирование: декоратор **и** ручной чек того же правила. `validation/controller-implements-generated-contract` ❌ inbound-DTO как
`any`/интерфейс без декораторов (интерфейсы стираются — `ValidationPipe` молча пропустит всё).

---

## 7. Конфигурация — `R-VLD-CFG-*`

`validation/config-validated-at-startup` — `ConfigModule.forRoot({ validate })` — fail-fast на старте (`nest-bootstrap/config-validated-at-startup`):

```ts
class AppConfig {
  @IsString() @IsNotEmpty()
  DATABASE_URL: string;                       // required без default (R-VLD-CFG-2)

  @ValidateNested() @Type(() => PaymentConfig)
  payment: PaymentConfig;                     // nested валидируется (R-VLD-CFG-4)
}

export function validate(env: Record<string, unknown>): AppConfig {
  const cfg = plainToInstance(AppConfig, env, { enableImplicitConversion: true });
  const errors = validateSync(cfg, { skipMissingProperties: false });
  if (errors.length) throw new Error(errors.toString());
  return cfg;
}
// альтернатива — zod-схема в validate; механизм тот же: невалидный конфиг роняет старт
```

`validation/config-validated-at-startup` ❌ конфиг-класс без `validate`. `validation/config-validated-at-startup` ❌ `process.env.X` напрямую для required-конфига —
без валидации и типов (`nest-bootstrap/profile-from-typed-config`); только инжектируемый типизированный конфиг.

---

## 8. Сообщения и i18n — `R-VLD-MSG-*`

`validation/message-in-user-language` — `message` в декораторе — на русском, для UI (`@Min(0, { message: 'Сумма должна быть положительной' })`).
`validation/message-in-user-language` — интерполяция через плейсхолдеры class-validator (`$constraint1`, `$property`, `$value`).
`validation/message-in-user-language` — i18n — каталог по ключу (например, `nestjs-i18n` + `i18nValidationMessage`), не копипаст текста.

`validation/message-in-user-language` ❌ дефолтные английские сообщения class-validator в пользовательском ответе.
`validation/message-in-user-language` ❌ технические термины («property amount has failed...») вместо человекочитаемого.
`validation/no-duplicated-messages` ❌ дублирование одного message на каждом поле — выносить в константу/каталог.

---

## Чеклист подключения (Node/NestJS)

- [ ] Глобальный `ValidationPipe({ whitelist, forbidNonWhitelisted, transform })` в `main.ts`;
      `exceptionFactory` → `InputValidationError` → 400 problem+json (через `backend/error-handling/node`)
- [ ] Входные DTO — классы с декораторами в сигнатурах; nested — `@ValidateNested` + `@Type`
- [ ] Конфиг — `ConfigModule.forRoot({ validate })`, required без default, nested валидируется
- [ ] Стандартные декораторы (`@IsEmail`/`@IsUUID`/`@Length`); деньги — не `number`
- [ ] Custom — пара `@ValidatorConstraint` + декоратор в `common/validation/`, имя по домену, true на null;
      cross-field — class-level декоратор с говорящим именем
- [ ] Нет ручной input-валидации в Handler; нет `any`-body; нет `process.env` для required
- [ ] Доменные инварианты — в агрегате (не class-validator); сообщения — на русском
