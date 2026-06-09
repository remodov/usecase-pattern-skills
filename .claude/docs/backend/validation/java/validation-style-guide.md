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

Связка с REST API style guide: контроллеры implements generated `<Tag>Api`, DTO генерируются `openapi-generator`. Принцип в команде — **OpenAPI-first для валидации**: все правила входных DTO формулируются в OpenAPI YAML, codegen превращает их в Jakarta-аннотации автоматически. Java-код только подключает `@Valid` на параметре контроллера и (при необходимости) добавляет custom constraints, которых нет в OpenAPI.

Workflow для нового эндпоинта:
```
ucp-api-design → src/main/resources/openapi/<service>.openapi.yaml
                  ↓ ./gradlew openApiGenerate
              build/generated/.../*Request.java   ← с Jakarta-аннотациями
                  ↓ controller implements <Tag>Api + @Valid
              automatic 400 + violations при невалидных данных
```

### 6.1 Обязательно

- **R-VLD-OAS-1.** **OpenAPI-first.** Все validation-правила для входных DTO живут в OpenAPI YAML, не в Java-коде. Если правило выражается через standard OpenAPI keywords — пиши в YAML, не дописывай аннотации в коде. В Java добавляются **только** custom constraints, которых OpenAPI не покрывает (см. `R-VLD-OAS-5`).

- **R-VLD-OAS-2.** Опция `useBeanValidation = true` в `openapi-generator` config. Без неё generated DTO без аннотаций, `@Valid` на контроллере ничего не делает.
  ```kotlin
  // <module>/build.gradle.kts
  openApiGenerate {
      generatorName.set("spring")          // или spring-restclient для outbound
      configOptions.set(mapOf(
          "useSpringBoot3" to "true",
          "useJakartaEe" to "true",
          "useBeanValidation" to "true"     // ← обязательно
      ))
  }
  ```

- **R-VLD-OAS-3.** OpenAPI YAML формулирует constraints на уровне схемы. Соответствие keyword → Java type → Jakarta annotation:

  | OpenAPI keyword | Java type | Jakarta annotation |
  |---|---|---|
  | `required: [field]` | object property | `@NotNull` (для object/Long), без `@NotBlank` для строк |
  | `minLength: 1` | `String` | `@Size(min=1)` (фактически not-empty) |
  | `maxLength: N` | `String` | `@Size(max=N)` |
  | `minLength: 1, maxLength: N` | `String` | `@Size(min=1, max=N)` |
  | `pattern: '^...$'` | `String` | `@Pattern(regexp = "^...$")` |
  | `format: email` | `String` | `@Email` |
  | `format: uuid` | `UUID` | (тип, не аннотация) |
  | `format: date` | `LocalDate` | (тип) |
  | `format: date-time` | `OffsetDateTime` | (тип) |
  | `minimum: N` | `int`/`long` | `@Min(N)` |
  | `minimum: 0.01` | `BigDecimal` | `@DecimalMin("0.01")` |
  | `maximum: N` | `int`/`long` | `@Max(N)` |
  | `exclusiveMinimum: true` + `minimum: 0` | numbers | `@DecimalMin(value = "0", inclusive = false)` |
  | `minItems: N` | `List`/`Set` | `@Size(min=N)` |
  | `maxItems: N` | `List`/`Set` | `@Size(max=N)` |
  | `uniqueItems: true` | array | **не генерируется** — нужен custom validator или `Set<X>` тип |
  | `enum: [A, B]` | java enum | (тип, не аннотация) |
  | `$ref: '#/.../X'` | nested object | `@Valid` (рекурсивная валидация) |

  Пример входного DTO в YAML:
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
      totalAmount:
        type: number
        format: double
        minimum: 0.01
      items:
        type: array
        minItems: 1
        maxItems: 100
        items:
          $ref: '#/components/schemas/OrderItemRequest'
  ```
  Generated `CreateOrderRequest.java` уже содержит: `@NotNull`, `@Min(1)`, `@Email`, `@Pattern("^\\+7\\d{10}$")`, `@DecimalMin("0.01")`, `@NotEmpty`, `@Size(min=1, max=100)`, `@Valid` на nested.

  Контроллер тривиален:
  ```java
  @PostMapping("/orders")
  public ResponseEntity<OrderJson> create(@Valid @RequestBody CreateOrderRequest req) { ... }
  ```

- **R-VLD-OAS-4.** Контроллер обязательно `implements <Tag>Api` (generated interface), не `@RestController` с handcrafted маппингом. Это гарантирует что generated `@Valid`/Jakarta-аннотации применяются (см. `R-OAS-1` REST guide).
  ```java
  @RestController
  public class OrderController implements OrdersApi {
      @Override
      public ResponseEntity<OrderJson> createOrder(CreateOrderRequest req) { ... }
      // generated OrdersApi method signature уже имеет @Valid внутри (благодаря useBeanValidation)
  }
  ```

- **R-VLD-OAS-5.** Custom constraint, который **не выражается** standard OpenAPI keywords:

  **Вариант А (рекомендуется):** custom формат уже выражается через `pattern: '^...$'` — пиши в OpenAPI напрямую. Например `@RussianPhone` = `pattern: '^\+7\d{10}$'`. Дублирование java-аннотации не нужно.

  **Вариант Б:** правило не сводится к pattern (например бизнес-проверка ИНН с контрольной суммой). Применяй на **wrapper-class** в коде проекта:
  ```java
  // адаптер в *-in-adapter
  public record CreateOrderInput(@Valid @RussianInn String inn, @Valid CreateOrderRequest body) {}

  @PostMapping
  public ResponseEntity<OrderJson> create(@Valid @RequestBody CreateOrderInput input) { ... }
  ```
  Generated `CreateOrderRequest` остаётся регенерируемым; custom-логика — на wrapper.

  **Вариант В (если генератор поддерживает):** OpenAPI extension `x-validation`:
  ```yaml
  inn:
    type: string
    x-validation: russianInn      # генератор-специфичный extension
  ```
  Поддержка зависит от templates генератора — обычно нужно кастомизировать mustache-шаблон. **Не используй без явного решения** в команде; дефолт — Вариант А или Б.

- **R-VLD-OAS-6.** **Двойной контракт generated vs UseCase.** Generated DTO (`CreateOrderRequest`) валидируется через `@Valid` на контроллере. После маппинга в UseCase command (`CreateOrderCommand` record) — **повторная валидация не делается**. Команда пришла «уже чистой» из контроллера. Domain-инварианты (`R-VLD-WHERE-3`) — отдельный концерн на агрегате, не Jakarta.

### 6.2 Запрещено

- **R-VLD-OAS-X1.** Дописывать `@Valid`/`@NotNull`/`@Pattern` руками в generated DTO (`build/generated/.../CreateOrderRequest.java`) — затрётся при следующем `compileJava`/`openApiGenerate`.

- **R-VLD-OAS-X2.** `useBeanValidation = false` или отсутствие этой опции. Generated DTO без constraints; `@Valid` на контроллере silent-passes невалидные данные в Handler.

- **R-VLD-OAS-X3.** Class-level constraint (`@DateRange`) на generated DTO. Применяй на wrapper-class или формулируй cross-field правила через OpenAPI bool-логику (если возможно).

- **R-VLD-OAS-X4.** Дублирование validation-правил: то же самое в OpenAPI YAML **и** руками в коде. Источник правды один — OpenAPI YAML. Если правило только в коде — оно не отразится в OpenAPI-документации, и фронт/потребители не узнают про ограничение.

- **R-VLD-OAS-X5.** Handcrafted DTO в `jsonbean/` или подобном пакете для inbound REST API. Это нарушение `R-OAS-1`/`BS-20` — все request/response DTO генерируются из OpenAPI. Если видишь `class CreateOrderRequest` без `@Generated` — вырезать, перенести в YAML.

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
| Дублирование validation в YAML и в Java | `R-VLD-OAS-X4` | OpenAPI YAML — единственный источник |
| Handcrafted request DTO без OpenAPI | `R-VLD-OAS-X5` | сгенерировать из YAML |
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
