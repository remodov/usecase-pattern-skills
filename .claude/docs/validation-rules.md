# Validation — индекс правил

> **Что это.** Сжатый индекс правил `validation-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `validation-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Где валидируем
**MUST:**
- **R-VLD-WHERE-1.** **Входной HTTP DTO** на контроллере → Jakarta Validation через `@Valid` на параметре. Это первая линия защиты, до того как невалидные данные дойдут до handler-а. Spring сам бросит `MethodArgumentNotValidException` → `@RestControllerAdvice` маппит в `400 Bad Request` с `code=VALIDATION_ERROR` и `violations` (см. `R-ERR-5`).
- **R-VLD-WHERE-2.** **`@ConfigurationProperties`** обязательно `@Validated` на классе. Невалидный конфиг → `BeanCreationException` на старте, не «сервис поднялся, но половина флагов некорректна».
- **R-VLD-WHERE-3.** **Доменные инварианты** Aggregate — НЕ через Jakarta. Aggregate сам гарантирует целостность через методы: Бросает domain-specific exception, который `@RestControllerAdvice` маппит в `409 Conflict` или `400 Bad Request` с конкретным `code` (например `ORDER_EMPTY`, `ORDER_ALREADY_CONFIRMED`). См. также `R-ENT-*`/`R-AGG-*` в DDD style guide.
- **R-VLD-WHERE-4.** При наличии **nested DTO** (`CreateOrderRequest` содержит `List<OrderItemRequest>`) — на nested-поле обязательно `@Valid`:
**MUST NOT:**
- **R-VLD-WHERE-X1.** **Manual `if (cmd.amount() < 0) throw ...` в Handler** для входной валидации. Теряется единый формат `violations` в ProblemDetails. Если правило про входной DTO — `@Valid` на контроллере; если про доменный инвариант — метод агрегата.
- **R-VLD-WHERE-X2.** Дублирование Jakarta-валидации на UseCase command (record). Контроллер уже провалидировал входной DTO; перенос в `<X>UseCase` record → `@Validated` на handler-е = двойная работа без пользы.
- **R-VLD-WHERE-X3.** **`@ConfigurationProperties` без `@Validated`.** Сервис стартует с невалидным конфигом, падает на первом запросе с непонятной ошибкой.
- **R-VLD-WHERE-X4.** **Доменный инвариант через Jakarta-аннотацию на Aggregate-поле** (`@Min(1)` на поле `quantity` в `OrderItem`). Aggregate-поля иммутабельны после конструирования; инвариант проверяется в конструкторе/методе бросанием domain exception.

## 2. Стандартные constraints
**MUST:**
- **R-VLD-STD-1.** Базовые null/empty проверки:
- **R-VLD-STD-2.** Размеры:
- **R-VLD-STD-3.** Формат:
- **R-VLD-STD-4.** Время:
- **R-VLD-STD-5.** Тип-зависимая валидация:
**MUST NOT:**
- **R-VLD-STD-X1.** `@NotNull` на примитивах (`@NotNull int amount`). Примитив не может быть null. Аннотация molчaливо ничего не проверяет, создаёт ложную гарантию.
- **R-VLD-STD-X2.** Кастомный regex в `@Pattern` для форматов, у которых уже есть стандартная аннотация: `@Pattern("^[^@]+@[^@]+$")` вместо `@Email`. Хуже валидирует и тяжелее читается.
- **R-VLD-STD-X3.** Composite-аннотации проекта (`@NotBlankAndAtMost50`) поверх стандартных. Лучше две отдельные на поле — компилятор их легко прочитает.

## 3. Custom constraints
**MUST:**
- **R-VLD-CC-1.** Custom constraint оформляется как пара: annotation interface + ConstraintValidator implementation.
- **R-VLD-CC-2.** Расположение кастомных constraints:
- **R-VLD-CC-3.** Имена: `@<DomainTerm>` без префиксов `Valid`/`Check`/`Is`. `@RussianPhone`, `@VatNumber` — да; `@ValidPhone`, `@CheckVat` — нет.
- **R-VLD-CC-4.** `isValid(null, ...)` возвращает `true` — null обрабатывается отдельной `@NotNull`. Custom-constraint обязан комбинироваться с null-аннотацией.
- **R-VLD-CC-5.** ConstraintValidator — **stateless**, без @Autowired-полей с runtime-state. Если нужны зависимости (DI на справочник) — использовать `HibernatePropertyNodeBuilderCustomizable` или явно `initialize(annotation)` с обращением к `Validator`-context. Но в большинстве случаев validator — pure function от value.
**MUST NOT:**
- **R-VLD-CC-X1.** `isValid(null, ...)` возвращает `false`. Нарушает композицию с `@NotNull`/`@NotBlank` — если ставишь обе, первая бесполезна.
- **R-VLD-CC-X2.** Custom constraint в одном файле с DTO (как inner-аннотация). Не переиспользуется, не находится grep-ом.
- **R-VLD-CC-X3.** Constraint-логика inline в `@AssertTrue`-методе на DTO. Не переиспользуется.

## 4. Validation groups
**MUST:**
- **R-VLD-GRP-1.** Validation groups применяй **только** когда тот же класс DTO нужен в разных сценариях с разными required-полями. Типичный кейс — `OrderRequest` для Create и Update:
- **R-VLD-GRP-2.** Group-interface — пустой interface с doc-comment «применяется в <контексте>». Не extends `Default`, не имеет методов.
**MUST NOT:**
- **R-VLD-GRP-X1.** Группы для разделения «строгая / мягкая валидация». Это два разных DTO в духе `CreateOrderRequest` vs `DraftOrderRequest`, а не один с группами.
- **R-VLD-GRP-X2.** Цепочки групп `@Validated({OnCreate.class, OnConfirm.class, OnPay.class})`. Если правил для одного класса больше двух режимов — это запах «класс делает слишком много», разбивай.

## 5. Cross-field validation
**MUST:**
- **R-VLD-XF-1.** Cross-field constraint (правило, в котором участвуют 2+ поля одного объекта) — class-level annotation:
- **R-VLD-XF-2.** Имя cross-field-constraint описывает правило, не объект: `@DateRange`, `@PasswordsMatch`, `@AmountWithinLimit` — да; `@OrderRequestValid` — нет (что валидируется?).
**MUST NOT:**
- **R-VLD-XF-X1.** `@AssertTrue`-метод в DTO (`@AssertTrue boolean isDateRangeValid()`). Не переиспользуется в другие DTO с тем же правилом, теряется при рефакторинге.
- **R-VLD-XF-X2.** Cross-field валидация в Handler перед `dispatcher.dispatch(...)`. Это валидация контракта, а не бизнес-правило — должна быть на DTO-уровне.

## 6. OpenAPI-сгенерированные DTO
**MUST:**
- **R-VLD-OAS-1.** **OpenAPI-first.** Все validation-правила для входных DTO живут в OpenAPI YAML, не в Java-коде. Если правило выражается через standard OpenAPI keywords — пиши в YAML, не дописывай аннотации в коде. В Java добавляются **только** custom constraints, которых OpenAPI не покрывает (см. `R-VLD-OAS-5`).
- **R-VLD-OAS-2.** Опция `useBeanValidation = true` в `openapi-generator` config. Без неё generated DTO без аннотаций, `@Valid` на контроллере ничего не делает.
- **R-VLD-OAS-3.** OpenAPI YAML формулирует constraints на уровне схемы. Соответствие keyword → Java type → Jakarta annotation:
- **R-VLD-OAS-4.** Контроллер обязательно `implements <Tag>Api` (generated interface), не `@RestController` с handcrafted маппингом. Это гарантирует что generated `@Valid`/Jakarta-аннотации применяются (см. `R-OAS-1` REST guide).
- **R-VLD-OAS-5.** Custom constraint, который **не выражается** standard OpenAPI keywords:
- **R-VLD-OAS-6.** **Двойной контракт generated vs UseCase.** Generated DTO (`CreateOrderRequest`) валидируется через `@Valid` на контроллере. После маппинга в UseCase command (`CreateOrderCommand` record) — **повторная валидация не делается**. Команда пришла «уже чистой» из контроллера. Domain-инварианты (`R-VLD-WHERE-3`) — отдельный концерн на агрегате, не Jakarta.
**MUST NOT:**
- **R-VLD-OAS-X1.** Дописывать `@Valid`/`@NotNull`/`@Pattern` руками в generated DTO (`build/generated/.../CreateOrderRequest.java`) — затрётся при следующем `compileJava`/`openApiGenerate`.
- **R-VLD-OAS-X2.** `useBeanValidation = false` или отсутствие этой опции. Generated DTO без constraints; `@Valid` на контроллере silent-passes невалидные данные в Handler.
- **R-VLD-OAS-X3.** Class-level constraint (`@DateRange`) на generated DTO. Применяй на wrapper-class или формулируй cross-field правила через OpenAPI bool-логику (если возможно).
- **R-VLD-OAS-X4.** Дублирование validation-правил: то же самое в OpenAPI YAML **и** руками в коде. Источник правды один — OpenAPI YAML. Если правило только в коде — оно не отразится в OpenAPI-документации, и фронт/потребители не узнают про ограничение.
- **R-VLD-OAS-X5.** Handcrafted DTO в `jsonbean/` или подобном пакете для inbound REST API. Это нарушение `R-OAS-1`/`BS-20` — все request/response DTO генерируются из OpenAPI. Если видишь `class CreateOrderRequest` без `@Generated` — вырезать, перенести в YAML.

## 7. Конфигурация
**MUST:**
- **R-VLD-CFG-1.** Каждый `@ConfigurationProperties` класс имеет `@Validated` на классе. Невалидный конфиг → fail-fast на старте.
- **R-VLD-CFG-2.** Required-поля помечены `@NotNull` (для object-типов) или `@NotBlank` (для String):
- **R-VLD-CFG-3.** Spring валидирует `Duration` / `DataSize` по типу. Дополнительные `@DurationMin`/`@DurationMax` — только если нужен бизнес-предел (`@DurationMax(value = 60, unit = SECONDS)`).
- **R-VLD-CFG-4.** Если property — структура (nested), используй `@Valid` для рекурсивной валидации:
**MUST NOT:**
- **R-VLD-CFG-X1.** `@ConfigurationProperties` без `@Validated` (см. `R-VLD-WHERE-X3`).
- **R-VLD-CFG-X2.** `@Value("${prop}")` для required-конфига. `@Value` не валидируется; используй `@ConfigurationProperties` (typed + validated) даже для одного поля.

## 8. Сообщения и i18n
**MUST:**
- **R-VLD-MSG-1.** `message` в аннотации — на русском, для пользователя (см. `R-LOC-3`).
- **R-VLD-MSG-2.** Интерполяция значений — через `{}`-плейсхолдеры из спецификации:
- **R-VLD-MSG-3.** Если нужна i18n — message-bundle через `{key}`: В `messages_ru.properties`:
**MUST NOT:**
- **R-VLD-MSG-X1.** Английский в `message` для пользовательских правил. Будет в violations.message → пользователю на UI.
- **R-VLD-MSG-X2.** Технические термины в message: «Field amount must be positive» → «Сумма должна быть положительной». Сообщение читает обычный пользователь, не разработчик.
- **R-VLD-MSG-X3.** Дублирование message в каждом DTO для одного и того же constraint. Если `@RussianPhone` имеет default message — не переопределяй на каждом поле без бизнес-причины.

## 9. Антипаттерны
