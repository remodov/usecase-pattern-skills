# Validation Style Guide

Свод правил валидации входных данных в Java/Spring-сервисах команды UCP: где валидируем, какие constraints используем, как пишем кастомные, как связано с REST API ProblemDetails и OpenAPI-генерацией. Каждое правило идентифицируется кодом (`R-VLD-WHERE-1`, `R-VLD-OAS-X1`) — скилл `ucp-validation-review` цитирует эти коды в findings.

Гайд опирается на [Jakarta Validation 3.0](https://jakarta.ee/specifications/bean-validation/3.0/) (jakarta.validation.\*) и Hibernate Validator как стандартную имплементацию. Не покрывает: business-инварианты в Aggregate (это DDD: `R-ENT-*`/`R-AGG-*`), security-валидацию (CSRF, JWT — это `AUTH-*`), валидацию на уровне БД (`CHECK` constraints — это `PG-T-*`/`PG-N-*`).

Связанные стандарты:
- `R-ERR-5`/`R-ERR-6` (REST API style guide) — формат `violations` в ProblemDetails при `code=VALIDATION_ERROR`.
- `R-OAS-1` (REST API style guide) — OpenAPI-first контракт.
- `R-RES-OAS-2` (Resilience style guide) — `useBeanValidation=true` опция openapi-generator для автоматической генерации constraints.
- `R-LOC-3` (REST API style guide) — `message` в violations локализуется.

---

## Содержание

1. [Где валидируем — `R-VLD-WHERE-*`](#1-где-валидируем)
2. [Стандартные constraints — `R-VLD-STD-*`](#2-стандартные-constraints)
3. [Custom constraints — `R-VLD-CC-*`](#3-custom-constraints)
4. [Validation groups — `R-VLD-GRP-*`](#4-validation-groups)
5. [Cross-field validation — `R-VLD-XF-*`](#5-cross-field-validation)
6. [OpenAPI-сгенерированные DTO — `R-VLD-OAS-*`](#6-openapi-сгенерированные-dto)
7. [Конфигурация — `R-VLD-CFG-*`](#7-конфигурация)
8. [Сообщения и i18n — `R-VLD-MSG-*`](#8-сообщения-и-i18n)
9. [Антипаттерны — сводка `R-VLD-*-X*`](#9-антипаттерны)

---

## 1. Где валидируем

В UCP-сервисе у валидации три места — каждое со своим инструментом. Перепутать = либо дублировать работу, либо проскользнут невалидные данные.

### 1.1 Обязательно

- **R-VLD-WHERE-1.** **Входной HTTP DTO** на контроллере → Jakarta Validation через `@Valid` на параметре. Это первая линия защиты, до того как невалидные данные дойдут до handler-а.
  ```java
  @PostMapping("/orders")
  public ResponseEntity<OrderJson> create(@Valid @RequestBody CreateOrderRequest req) { ... }
  ```
  Spring сам бросит `MethodArgumentNotValidException` → `@RestControllerAdvice` маппит в `400 Bad Request` с `code=VALIDATION_ERROR` и `violations` (см. `R-ERR-5`).

- **R-VLD-WHERE-2.** **`@ConfigurationProperties`** обязательно `@Validated` на классе. Невалидный конфиг → `BeanCreationException` на старте, не «сервис поднялся, но половина флагов некорректна».
  ```java
  @ConfigurationProperties("client.sber")
  @Validated
  public record SberClientSettings(
      @NotBlank String baseUrl,
      @NotNull Duration connectTimeout,
      @Min(1) int maxConcurrent
  ) {}
  ```

- **R-VLD-WHERE-3.** **Доменные инварианты** Aggregate — НЕ через Jakarta. Aggregate сам гарантирует целостность через методы:
  ```java
  public void confirm() {
      if (status != OrderStatus.CREATED) {
          throw new OrderDomainException("Cannot confirm: status=" + status);
      }
      if (items.isEmpty()) {
          throw new OrderDomainException("Cannot confirm: empty order");
      }
      this.status = OrderStatus.CONFIRMED;
      this.confirmedAt = OffsetDateTime.now();
  }
  ```
  Бросает domain-specific exception, который `@RestControllerAdvice` маппит в `409 Conflict` или `400 Bad Request` с конкретным `code` (например `ORDER_EMPTY`, `ORDER_ALREADY_CONFIRMED`). См. также `R-ENT-*`/`R-AGG-*` в DDD style guide.

- **R-VLD-WHERE-4.** При наличии **nested DTO** (`CreateOrderRequest` содержит `List<OrderItemRequest>`) — на nested-поле обязательно `@Valid`:
  ```java
  public record CreateOrderRequest(
      @NotNull Long customerId,
      @NotEmpty @Valid List<OrderItemRequest> items     // @Valid обязателен — иначе nested не валидируется
  ) {}
  ```

### 1.2 Запрещено

- **R-VLD-WHERE-X1.** **Manual `if (cmd.amount() < 0) throw ...` в Handler** для входной валидации. Теряется единый формат `violations` в ProblemDetails. Если правило про входной DTO — `@Valid` на контроллере; если про доменный инвариант — метод агрегата.

- **R-VLD-WHERE-X2.** Дублирование Jakarta-валидации на UseCase command (record). Контроллер уже провалидировал входной DTO; перенос в `<X>UseCase` record → `@Validated` на handler-е = двойная работа без пользы.

- **R-VLD-WHERE-X3.** **`@ConfigurationProperties` без `@Validated`.** Сервис стартует с невалидным конфигом, падает на первом запросе с непонятной ошибкой.

- **R-VLD-WHERE-X4.** **Доменный инвариант через Jakarta-аннотацию на Aggregate-поле** (`@Min(1)` на поле `quantity` в `OrderItem`). Aggregate-поля иммутабельны после конструирования; инвариант проверяется в конструкторе/методе бросанием domain exception.

---

## 2. Стандартные constraints

Используем стандартный набор Jakarta. Не изобретаем замену для существующих.

### 2.1 Обязательно

- **R-VLD-STD-1.** Базовые null/empty проверки:
  - `@NotNull` — для object-полей и Boolean.
  - `@NotBlank` — для строк (одна аннотация вместо `@NotNull` + `@NotEmpty` + проверка пробелов).
  - `@NotEmpty` — для коллекций / массивов / Map.

- **R-VLD-STD-2.** Размеры:
  - `@Size(min, max)` — для строк (тогда — без `@NotBlank`, потому что `@Size(min=1)` это фактически not-empty) и коллекций.
  - `@Min` / `@Max` — для int / long / short / byte.
  - `@DecimalMin` / `@DecimalMax` — для `BigDecimal` / `BigInteger`. Не использовать `@Min` на BigDecimal (только примитивы).
  - `@Positive` / `@PositiveOrZero` / `@Negative` / `@NegativeOrZero` — короткая форма для знака.

- **R-VLD-STD-3.** Формат:
  - `@Email` — для email-адресов. Использовать regex `@Pattern("^[^@]+@[^@]+$")` запрещено — Jakarta `@Email` корректнее, обновляется при изменениях RFC.
  - `@Pattern(regexp)` — только для редких форматов (артикул `[A-Z]{3}-\d{6}`). Для частых форматов (телефон E.164, INN, BIC) — custom constraint (см. `R-VLD-CC-*`).

- **R-VLD-STD-4.** Время:
  - `@Past` / `@PastOrPresent` / `@Future` / `@FutureOrPresent` — для `LocalDate`/`Instant`/`OffsetDateTime`.

- **R-VLD-STD-5.** Тип-зависимая валидация:
  - Для **boolean-поля, которое может быть null** — тип `Boolean` (не `boolean`) + `@NotNull`.
  - Для int-поля, которое не может быть пустым — примитив `int` (не Integer); ноль — валидное значение, отдельная аннотация не нужна.

### 2.2 Запрещено

- **R-VLD-STD-X1.** `@NotNull` на примитивах (`@NotNull int amount`). Примитив не может быть null. Аннотация molчaливо ничего не проверяет, создаёт ложную гарантию.

- **R-VLD-STD-X2.** Кастомный regex в `@Pattern` для форматов, у которых уже есть стандартная аннотация: `@Pattern("^[^@]+@[^@]+$")` вместо `@Email`. Хуже валидирует и тяжелее читается.

- **R-VLD-STD-X3.** Composite-аннотации проекта (`@NotBlankAndAtMost50`) поверх стандартных. Лучше две отдельные на поле — компилятор их легко прочитает.

---

## 3. Custom constraints

Кастомные constraints — для доменных правил, которых нет в стандартной Jakarta.

### 3.1 Обязательно

- **R-VLD-CC-1.** Custom constraint оформляется как пара: annotation interface + ConstraintValidator implementation.
  ```java
  // common/validation/RussianPhone.java
  @Target({ FIELD, PARAMETER })
  @Retention(RUNTIME)
  @Constraint(validatedBy = RussianPhoneValidator.class)
  public @interface RussianPhone {
      String message() default "Номер должен быть в формате +7XXXXXXXXXX";
      Class<?>[] groups() default {};
      Class<? extends Payload>[] payload() default {};
  }

  // common/validation/RussianPhoneValidator.java
  public class RussianPhoneValidator implements ConstraintValidator<RussianPhone, String> {
      private static final Pattern PHONE = Pattern.compile("^\\+7\\d{10}$");

      @Override
      public boolean isValid(String value, ConstraintValidatorContext ctx) {
          return value == null || PHONE.matcher(value).matches();   // null — валидно (комбинируется с @NotBlank)
      }
  }
  ```

- **R-VLD-CC-2.** Расположение кастомных constraints:
  - **Доменно-специфичный** (`@VatNumber`, `@Iso8601Duration`) → `core/<bc>/validation/` (часть domain-vocabulary).
  - **Общий технический** (`@RussianPhone`, `@UrlSafeBase64`) → `common/validation/` отдельный модуль.

- **R-VLD-CC-3.** Имена: `@<DomainTerm>` без префиксов `Valid`/`Check`/`Is`. `@RussianPhone`, `@VatNumber` — да; `@ValidPhone`, `@CheckVat` — нет.

- **R-VLD-CC-4.** `isValid(null, ...)` возвращает `true` — null обрабатывается отдельной `@NotNull`. Custom-constraint обязан комбинироваться с null-аннотацией.
  ```java
  @NotBlank @RussianPhone String phone     // null/blank — @NotBlank; формат — @RussianPhone
  ```

- **R-VLD-CC-5.** ConstraintValidator — **stateless**, без @Autowired-полей с runtime-state. Если нужны зависимости (DI на справочник) — использовать `HibernatePropertyNodeBuilderCustomizable` или явно `initialize(annotation)` с обращением к `Validator`-context. Но в большинстве случаев validator — pure function от value.

### 3.2 Запрещено

- **R-VLD-CC-X1.** `isValid(null, ...)` возвращает `false`. Нарушает композицию с `@NotNull`/`@NotBlank` — если ставишь обе, первая бесполезна.

- **R-VLD-CC-X2.** Custom constraint в одном файле с DTO (как inner-аннотация). Не переиспользуется, не находится grep-ом.

- **R-VLD-CC-X3.** Constraint-логика inline в `@AssertTrue`-методе на DTO. Не переиспользуется.

---

## 4. Validation groups

Validation groups — механизм «один класс, разные правила в разных контекстах». Использовать узко.

### 4.1 Обязательно

- **R-VLD-GRP-1.** Validation groups применяй **только** когда тот же класс DTO нужен в разных сценариях с разными required-полями. Типичный кейс — `OrderRequest` для Create и Update:
  ```java
  public interface OnCreate {}
  public interface OnUpdate {}

  public record OrderRequest(
      @NotNull(groups = OnCreate.class) Long customerId,    // required only при создании
      @NotNull Money totalAmount,                            // required всегда
      @Size(max = 1000) String comment
  ) {}

  // controller
  @PostMapping
  public Order create(@Validated(OnCreate.class) @RequestBody OrderRequest req) { ... }

  @PatchMapping
  public Order update(@Validated(OnUpdate.class) @RequestBody OrderRequest req) { ... }
  ```

- **R-VLD-GRP-2.** Group-interface — пустой interface с doc-comment «применяется в <контексте>». Не extends `Default`, не имеет методов.

### 4.2 Запрещено

- **R-VLD-GRP-X1.** Группы для разделения «строгая / мягкая валидация». Это два разных DTO в духе `CreateOrderRequest` vs `DraftOrderRequest`, а не один с группами.

- **R-VLD-GRP-X2.** Цепочки групп `@Validated({OnCreate.class, OnConfirm.class, OnPay.class})`. Если правил для одного класса больше двух режимов — это запах «класс делает слишком много», разбивай.

---

## 5. Cross-field validation

### 5.1 Обязательно

- **R-VLD-XF-1.** Cross-field constraint (правило, в котором участвуют 2+ поля одного объекта) — class-level annotation:
  ```java
  @Target({ TYPE })
  @Retention(RUNTIME)
  @Constraint(validatedBy = DateRangeValidator.class)
  public @interface DateRange {
      String message() default "dateFrom должен быть не позже dateTo";
      Class<?>[] groups() default {};
      Class<? extends Payload>[] payload() default {};
  }

  public class DateRangeValidator implements ConstraintValidator<DateRange, OrderFilterRequest> {
      @Override
      public boolean isValid(OrderFilterRequest req, ConstraintValidatorContext ctx) {
          if (req.dateFrom() == null || req.dateTo() == null) return true;
          if (!req.dateFrom().isAfter(req.dateTo())) return true;
          ctx.disableDefaultConstraintViolation();
          ctx.buildConstraintViolationWithTemplate(ctx.getDefaultConstraintMessageTemplate())
             .addPropertyNode("dateFrom")
             .addConstraintViolation();
          return false;
      }
  }

  @DateRange
  public record OrderFilterRequest(
      LocalDate dateFrom, LocalDate dateTo, ...
  ) {}
  ```
  В `violations` ошибка прицепится к `field: "dateFrom"` (или конкретному полю, как настроено), не на всему объекту.

- **R-VLD-XF-2.** Имя cross-field-constraint описывает правило, не объект: `@DateRange`, `@PasswordsMatch`, `@AmountWithinLimit` — да; `@OrderRequestValid` — нет (что валидируется?).

### 5.2 Запрещено

- **R-VLD-XF-X1.** `@AssertTrue`-метод в DTO (`@AssertTrue boolean isDateRangeValid()`). Не переиспользуется в другие DTO с тем же правилом, теряется при рефакторинге.

- **R-VLD-XF-X2.** Cross-field валидация в Handler перед `dispatcher.dispatch(...)`. Это валидация контракта, а не бизнес-правило — должна быть на DTO-уровне.

---

## 6. OpenAPI-сгенерированные DTO

Связка с REST API style guide: контроллеры implements generated `<Tag>Api`, DTO генерируются openapi-generator.

### 6.1 Обязательно

- **R-VLD-OAS-1.** Опция `useBeanValidation = true` в `openapi-generator` config. Тогда constraints из OpenAPI YAML (`pattern`, `minLength`, `maxLength`, `minimum`, `maximum`, `required`, `format: email`) генерируются как Jakarta-аннотации в DTO.
  ```kotlin
  // <module>/build.gradle.kts
  openApiGenerate {
      ...
      configOptions.set(mapOf(
          "useSpringBoot3" to "true",
          "useJakartaEe" to "true",
          "useBeanValidation" to "true"
      ))
  }
  ```

- **R-VLD-OAS-2.** OpenAPI YAML формулирует constraints на уровне схемы:
  ```yaml
  CreateOrderRequest:
    type: object
    required:
      - customerId
      - items
    properties:
      customerId:
        type: integer
        format: int64
        minimum: 1
      email:
        type: string
        format: email
      phone:
        type: string
        pattern: '^\+7\d{10}$'
      items:
        type: array
        minItems: 1
        items:
          $ref: '#/components/schemas/OrderItemRequest'
  ```
  Контроллер: `@Valid @RequestBody CreateOrderRequest req` — generated DTO уже содержит `@NotNull`, `@Min(1)`, `@Email`, `@Pattern("^\\+7\\d{10}$")`, `@NotEmpty`, `@Valid` на nested.

- **R-VLD-OAS-3.** Custom constraint, который не выражается через OpenAPI schema, добавляется на **wrapper-class** или domain entity, не на generated DTO. Generated DTO — детали транспорта.

### 6.2 Запрещено

- **R-VLD-OAS-X1.** Дописывать `@Valid`/`@NotNull` руками в generated DTO — затрётся при regenerate.

- **R-VLD-OAS-X2.** `useBeanValidation = false`. Тогда generated DTO без constraints, контроллер `@Valid` ничего не валидирует — silent skip.

- **R-VLD-OAS-X3.** Class-level `@DateRange` constraint на generated DTO (regenerate-safe нарушение). Если cross-field правило критично — переноси в wrapper-class в коде проекта.

---

## 7. Конфигурация

`@ConfigurationProperties` + `@Validated` — стандартный паттерн UCP.

### 7.1 Обязательно

- **R-VLD-CFG-1.** Каждый `@ConfigurationProperties` класс имеет `@Validated` на классе. Невалидный конфиг → fail-fast на старте.

- **R-VLD-CFG-2.** Required-поля помечены `@NotNull` (для object-типов) или `@NotBlank` (для String):
  ```java
  @ConfigurationProperties("client.sber")
  @Validated
  public record SberClientSettings(
      @NotBlank String baseUrl,
      @NotNull Duration connectTimeout,
      @NotNull Duration readTimeout,
      @Min(1) @Max(100) int maxConcurrent,
      String apiKey                              // optional, без аннотации = nullable
  ) {}
  ```

- **R-VLD-CFG-3.** Spring валидирует `Duration` / `DataSize` по типу. Дополнительные `@DurationMin`/`@DurationMax` — только если нужен бизнес-предел (`@DurationMax(value = 60, unit = SECONDS)`).

- **R-VLD-CFG-4.** Если property — структура (nested), используй `@Valid` для рекурсивной валидации:
  ```java
  @Validated
  public record AppSettings(
      @Valid @NotNull DatabaseSettings database,
      @Valid @NotNull MessagingSettings messaging
  ) {}
  ```

### 7.2 Запрещено

- **R-VLD-CFG-X1.** `@ConfigurationProperties` без `@Validated` (см. `R-VLD-WHERE-X3`).

- **R-VLD-CFG-X2.** `@Value("${prop}")` для required-конфига. `@Value` не валидируется; используй `@ConfigurationProperties` (typed + validated) даже для одного поля.

---

## 8. Сообщения и i18n

### 8.1 Обязательно

- **R-VLD-MSG-1.** `message` в аннотации — на русском, для пользователя (см. `R-LOC-3`).
  ```java
  @NotBlank(message = "Имя обязательно")
  @Size(max = 100, message = "Имя не более 100 символов")
  String name
  ```

- **R-VLD-MSG-2.** Интерполяция значений — через `{}`-плейсхолдеры из спецификации:
  ```java
  @Min(value = 1, message = "Значение должно быть не меньше {value}")
  @Size(min = 1, max = 100, message = "Длина от {min} до {max}")
  ```

- **R-VLD-MSG-3.** Если нужна i18n — message-bundle через `{key}`:
  ```java
  @NotBlank(message = "{order.name.required}")
  String name
  ```
  В `messages_ru.properties`:
  ```
  order.name.required=Имя заказа обязательно
  ```

### 8.2 Запрещено

- **R-VLD-MSG-X1.** Английский в `message` для пользовательских правил. Будет в violations.message → пользователю на UI.

- **R-VLD-MSG-X2.** Технические термины в message: «Field amount must be positive» → «Сумма должна быть положительной». Сообщение читает обычный пользователь, не разработчик.

- **R-VLD-MSG-X3.** Дублирование message в каждом DTO для одного и того же constraint. Если `@RussianPhone` имеет default message — не переопределяй на каждом поле без бизнес-причины.

---

## 9. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Manual `if (cmd.x < 0) throw` в Handler для входной валидации | `R-VLD-WHERE-X1` | `@Valid` на контроллере |
| Дублирование Jakarta на UseCase command | `R-VLD-WHERE-X2` | один раз на контроллере |
| `@ConfigurationProperties` без `@Validated` | `R-VLD-WHERE-X3`, `R-VLD-CFG-X1` | `@Validated` на классе |
| Доменный инвариант через `@Min` на поле Aggregate | `R-VLD-WHERE-X4` | бросание domain exception в методе |
| `@NotNull` на примитиве | `R-VLD-STD-X1` | проверка не нужна, либо тип `Long`/`Integer` |
| Кастомный regex для email вместо `@Email` | `R-VLD-STD-X2` | `@Email` |
| Composite-аннотация `@NotBlankAndAtMost50` | `R-VLD-STD-X3` | две отдельные аннотации |
| Custom validator возвращает `false` для null | `R-VLD-CC-X1` | `isValid(null) → true` + комбинация с `@NotNull` |
| Inner-аннотация в одном файле с DTO | `R-VLD-CC-X2` | в `core/<bc>/validation/` или `common/validation/` |
| `@AssertTrue isDateRangeValid()` метод в DTO | `R-VLD-XF-X1`, `R-VLD-CC-X3` | class-level `@DateRange` |
| Cross-field валидация в Handler | `R-VLD-XF-X2` | class-level constraint на DTO |
| Validation groups «строгая/мягкая» вместо разных DTO | `R-VLD-GRP-X1` | разные DTO |
| Цепочки `@Validated({OnCreate, OnConfirm, OnPay})` | `R-VLD-GRP-X2` | разбить класс |
| Дописывание `@Valid`/`@NotNull` в generated DTO | `R-VLD-OAS-X1` | constraints в OpenAPI YAML |
| `useBeanValidation = false` | `R-VLD-OAS-X2` | `true` обязательно |
| Class-level constraint на generated DTO | `R-VLD-OAS-X3` | wrapper-class в коде проекта |
| `@Value("${prop}")` для required-конфига | `R-VLD-CFG-X2` | `@ConfigurationProperties` typed |
| Английский в `message` | `R-VLD-MSG-X1` | русский |
| Технические термины в message | `R-VLD-MSG-X2` | пользовательский язык |
| `@Valid` забыт на nested-DTO | `R-VLD-WHERE-4` | `@Valid` на nested-поле |

Финальная сводка: правил «Обязательно» — около 25, «Запрещено» — около 18.

---

## Связь с другими стандартами

- **`R-ERR-5`/`R-ERR-6`** (REST API) — формат `violations` в ProblemDetails. Spring `@RestControllerAdvice` ловит `MethodArgumentNotValidException` / `ConstraintViolationException` и формирует ответ — не пиши свой обработчик, используй стандарт.
- **`R-OAS-*`** (REST API) — OpenAPI-first. Constraints живут в YAML, генерируются в DTO.
- **`R-RES-OAS-2`** (Resilience) — для outbound-клиентов `useBeanValidation=true` тоже включён.
- **`R-ENT-*`/`R-AGG-*`** (DDD tactical) — domain invariants. Не путать с входной валидацией.
- **`AUTH-19`** (Auth Patterns) — `Idempotency-Key` валидация: формат через `@Pattern` или custom constraint.
