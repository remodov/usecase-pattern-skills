# Validation — Node Style Guide (class-validator / class-transformer / NestJS)

Реализация язык-нейтрального контракта `../validation-rules.md` (`R-VLD-*`) на NestJS.
Коды — общие с Java и Python; здесь — идиомы class-validator + class-transformer.

> **Парадигма.** NestJS **code-first** (как Python): DTO-класс с декораторами — **источник правды** валидации
> входа, OpenAPI генерируется из него (`@nestjs/swagger`). «Не править generated руками» (`R-VLD-OAS-X1`)
> неактуально; актуально «DTO-класс = контракт, без дублей» (`R-VLD-OAS-X4`). Точка входа — **глобальный
> `ValidationPipe`** в `main.ts`, один на приложение.

---

## 1. Где валидируем — `R-VLD-WHERE-*`

`R-VLD-WHERE-1` — входной DTO — класс с class-validator-декораторами в сигнатуре контроллера; валидирует
глобальный `ValidationPipe` до Handler; невалидное → 400 problem+json через `exceptionFactory`
(cross-ref `R-ERR-MAP-2`, `backend/error-handling/node`):

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

`R-VLD-WHERE-2` — конфиг валидируется на старте: `ConfigModule.forRoot({ validate })` — fail-fast (см. §7, `NESTBOOT-4`).
`R-VLD-WHERE-3` — доменные инварианты — в агрегате (`Order.create(...)` бросает `DomainError`), не в class-validator (cross-ref `R-AGG-*`).
`R-VLD-WHERE-4` — nested — `@ValidateNested` + `@Type(...)`; без `@Type` объект останется plain и не провалидируется.

`R-VLD-WHERE-X1` ❌ ручная `if (req.amount < 0) throw ...` в Handler — правило DTO → декоратор (`@Min(0)`), инвариант → агрегат.
`R-VLD-WHERE-X2` ❌ повторная валидация UseCase-команды (она — plain-объект из уже чистого DTO). `R-VLD-WHERE-X3` ❌ конфиг без валидации (§7).
`R-VLD-WHERE-X4` ❌ class-validator-декораторы на доменном агрегате — домен без фреймворка; инвариант в конструкторе.

---

## 2. Стандартные constraints — `R-VLD-STD-*`

`R-VLD-STD-1` — required по умолчанию (нет `@IsOptional`); пустая строка — `@IsNotEmpty`; optional — `@IsOptional()` + `field?: T`.
`R-VLD-STD-2` — размеры — `@Length(min, max)` / `@ArrayMinSize`, числа — `@Min`/`@Max`.
`R-VLD-STD-3` — формат — стандартные декораторы (`@IsEmail`, `@IsUUID`, `@IsUrl`, `@IsISO8601`), не самописный `@Matches`.
`R-VLD-STD-4` — время — `@IsISO8601()` (string-DTO) или `@Type(() => Date)` + `@MinDate`/`@MaxDate`.
`R-VLD-STD-5` — валидация на правильном типе: число — `@IsInt`/`@Min` на `number` (`transform: true` приводит query-строки); деньги — строка + decimal-библиотека или `bigint` в миноре, не `number`.

`R-VLD-STD-X1` ❌ дублирование required-проверки (`@IsDefined` поверх `@IsNotEmpty`) — TS-типы стираются в runtime, поэтому один required-декоратор нужен, но ровно один.
`R-VLD-STD-X2` ❌ `@Matches(emailRegex)` вместо `@IsEmail`. `R-VLD-STD-X3` ❌ «всё-в-одном» кастомный валидатор вместо комбинации стандартных.

---

## 3. Custom constraints — `R-VLD-CC-*`

`R-VLD-CC-1` — переиспользуемый constraint — пара `@ValidatorConstraint`-класс + декоратор-обёртка через `registerDecorator`:

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

`R-VLD-CC-2` — в общем модуле `common/validation/`, не inline в DTO. `R-VLD-CC-3` — имя по домену
(`RussianPhone`, `VatNumber`), без `Valid`/`Check`/`Is`. `R-VLD-CC-4` — на null/undefined возвращает `true`;
required — комбинацией с `@IsNotEmpty`. `R-VLD-CC-5` — stateless чистая функция; зависимость (справочник) —
только осознанно (`useContainer(app, ...)` для DI в констрейнт).

`R-VLD-CC-X1` ❌ констрейнт падает/фейлит на null — ломает композицию с required. `R-VLD-CC-X2` ❌ констрейнт-класс
в файле DTO. `R-VLD-CC-X3` ❌ невыносимая логика в ad-hoc `@Validate(...)`-лямбде вместо переиспользуемой пары.

---

## 4. Сценарии (groups) — `R-VLD-GRP-*`

`R-VLD-GRP-1` — class-validator поддерживает `groups` (`@IsNotEmpty({ groups: ['create'] })` +
`new ValidationPipe({ groups: [...] })` на конкретном эндпоинте) — допустимо, только когда DTO реально один;
идиома по умолчанию — **отдельные классы** (`CreateOrderRequest` vs `UpdateOrderRequest`), как в Python.
`R-VLD-GRP-2` — имя группы — документированная константа, не магическая строка по месту.
`R-VLD-GRP-X1` ❌ один класс с режимами «строгий/мягкий» — два разных класса. `R-VLD-GRP-X2` ❌ DTO,
обслуживающий 3+ сценария через группы, — разбить.

---

## 5. Cross-field — `R-VLD-XF-*`

`R-VLD-XF-1` — правило с 2+ полями — **class-level** custom validator (декоратор на классе):

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

`R-VLD-XF-2` — имя описывает правило (`DateRange`, `PasswordsMatch`), не объект.
`R-VLD-XF-X1` ❌ одноразовый ad-hoc чек, если правило встречается в нескольких DTO — выносить в `common/validation/`.
`R-VLD-XF-X2` ❌ cross-field-проверка в Handler перед dispatch — место на DTO.

---

## 6. Контракт-схема — `R-VLD-OAS-*`

`R-VLD-OAS-1` — **code-first**: DTO-класс — источник; OpenAPI генерирует `@nestjs/swagger` (CLI-plugin снимает
constraints с декораторов в схему); правило живёт в одном месте — в DTO. `R-VLD-OAS-4` — контракт =
типизированный DTO-класс в сигнатуре контроллера (`@Body() req: CreateOrderRequest`), не `@Body() body: any`.
`R-VLD-OAS-6` — после маппинга в UseCase-команду повторной валидации нет; домен-инварианты — на агрегате.

`R-VLD-OAS-X4` ❌ дублирование: декоратор **и** ручной чек того же правила. `R-VLD-OAS-X5` ❌ inbound-DTO как
`any`/интерфейс без декораторов (интерфейсы стираются — `ValidationPipe` молча пропустит всё).

---

## 7. Конфигурация — `R-VLD-CFG-*`

`R-VLD-CFG-1` — `ConfigModule.forRoot({ validate })` — fail-fast на старте (`NESTBOOT-4`):

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

`R-VLD-CFG-X1` ❌ конфиг-класс без `validate`. `R-VLD-CFG-X2` ❌ `process.env.X` напрямую для required-конфига —
без валидации и типов (`NESTBOOT-X1`); только инжектируемый типизированный конфиг.

---

## 8. Сообщения и i18n — `R-VLD-MSG-*`

`R-VLD-MSG-1` — `message` в декораторе — на русском, для UI (`@Min(0, { message: 'Сумма должна быть положительной' })`).
`R-VLD-MSG-2` — интерполяция через плейсхолдеры class-validator (`$constraint1`, `$property`, `$value`).
`R-VLD-MSG-3` — i18n — каталог по ключу (например, `nestjs-i18n` + `i18nValidationMessage`), не копипаст текста.

`R-VLD-MSG-X1` ❌ дефолтные английские сообщения class-validator в пользовательском ответе.
`R-VLD-MSG-X2` ❌ технические термины («property amount has failed...») вместо человекочитаемого.
`R-VLD-MSG-X3` ❌ дублирование одного message на каждом поле — выносить в константу/каталог.

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
