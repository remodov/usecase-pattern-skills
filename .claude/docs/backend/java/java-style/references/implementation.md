# Java — реализация

Свод правил для Java-кода. Каждое правило имеет код вида `JS-<section>.<num>` —
скилл `java-style-review` цитирует эти коды в findings.

Базовый принцип (`java-style/deviation-requires-justification`): **допускается любое нарушение, если оно улучшает
читаемость**. Цель руководства — улучшить читаемость, понимание и общее
качество кода, а не превратить ревью в формальную проверку.

Источник: внутренний Java Style guide (Yandex Wiki).

---

## 1. Общие рекомендации

- **`java-style/deviation-requires-justification`** — любое нарушение допустимо, если оно улучшает читаемость. Это
  не индульгенция «писать как хочется»: от ревьюера ожидается явное
  объяснение, чем именно нарушение лучше.

---

## 2. Именование

### `java-style/package-and-type-naming` Имена пакетов

Имена пакетов — в нижнем регистре, без подчёркиваний и других специальных
символов.

```java
package com.example.orderservice;       // PREFER
package com.example.order_service;      // AVOID
package com.example.OrderService;       // AVOID
```

### `java-style/package-and-type-naming` Множественное число в пакетах запрещено

Следуем соглашению стандартного API: `java.util`, не `java.utils`.

```java
package com.example.util;               // PREFER
package com.example.utils;              // AVOID
```

### `java-style/package-and-type-naming` Имена классов — существительные

```java
class Car {}                            // PREFER
class Running {}                        // AVOID — глагольная форма
```

### `java-style/package-and-type-naming` Имена интерфейсов — существительные или прилагательные на `-able`

Не начинать имя с `I` (это привет шарпистам).

```java
interface Runnable {}                   // PREFER
interface Comparable {}                 // PREFER
interface IEnumerable {}                // AVOID
```

### `java-style/abbreviation-casing` Аббревиатуры в именах

В именах классов, переменных и интерфейсов **не должно быть нескольких
заглавных букв подряд**. Правила:

- Рекомендуется отказываться от аббревиатур.
- Аббревиатура из **2 букв** входит в имя в верхнем регистре.
- Аббревиатура из **3+ букв** входит только с первой буквой в верхнем регистре
  (цифры не учитываются).

```java
class IOStream {}                       // PREFER (2 буквы — обе CAPS)
class IoStream {}                       // AVOID

class XmlParser {}                      // PREFER (3 буквы — Capitalize)
class XMLParser {}                      // AVOID

class Pk2dfCertificate {}               // PREFER
class C2CTariff {}                      // PREFER (2 буквы C2C → CAPS, цифра не считается)
class C2сTariff {}                      // AVOID (микс регистров)
```

### `java-style/member-naming` Имена методов — глаголы или описание действия

```java
public String getName() {}              // PREFER
public String name() {}                 // AVOID

public void expand() {}                 // PREFER
public boolean expanding() {}           // AVOID
```

### `java-style/test-method-naming` Имена тестов

Имена тестов должны отражать суть тест-кейса и точно описывать, что
тестируется. Допустимо два подхода:

```java
// PREFER — длинное говорящее имя
@Test
public void shouldReturnNullIfResponseEmptyArray() {}

// PREFER — короткое имя + @DisplayName, если иначе слишком длинно
@Test
@DisplayName("should return null if response is empty array")
public void someOtherShorterName() {}

// AVOID — snake_case
public void should_Return_Null_If_Response_Empty_Array() {}

// AVOID — имя слишком длинное и без @DisplayName
public void shouldReturnNullIfResponseEmptyArrayOrExternalSystemIsDownAndStuff() {}
```

### `java-style/member-naming` Имена переменных — camelCase, начинаются с lowercase

```java
int currentValue;                       // PREFER
int PreviousValue;                      // AVOID
```

### `java-style/member-naming` Имена констант — `UPPER_SNAKE_CASE`, обязательно `static final`

```java
public static final int BUFFER_SIZE = 1024;   // PREFER
public final int ARRAY_SIZE = 10;             // AVOID — не static
```

---

## 3. Импорты

### `java-style/imports-are-explicit` Не использовать wildcard-импорты

```java
import some.java.package.ParticularClass;     // PREFER
import some.java.package.*;                   // AVOID
```

Исключение — `java.util.*` допустим.

### `java-style/imports-are-explicit` Не оставлять неиспользуемых импортов

---

## 4. Выражения

### `java-style/expressions-stay-simple` Сложность булева выражения — не более 3 операторов `&&`/`||`

```java
boolean good = (!a && b) | (a || !b) ^ a;     // PREFER (3 op)
boolean bad  = (a && b) && c && (c || b);     // AVOID (4 op)
```

Слишком много условий → код трудно читать, отлаживать и поддерживать.

### `java-style/expressions-stay-simple` Избегать C-стиля объявления массивов

```java
int[] nums;                             // PREFER
String strs[];                          // AVOID
```

### `java-style/expressions-stay-simple` Порядок модификаторов

```
public → protected → private → static → final → transient → volatile → synchronized
```

### `java-style/expressions-stay-simple` Не указывать неявные модификаторы

- В методах интерфейса не пишем `public` или `abstract` (они подразумеваются).
- Во вложенных enum и interface не пишем `static`.

### `java-style/lambdas-stay-short` Method reference вместо лямбды, где имеет смысл

```java
filter(someStrings::contains);          // PREFER
filter(s -> someStrings.contains(s));   // AVOID
```

### `java-style/lambdas-stay-short` Большие лямбды выносить в методы

Если в лямбде логика «больше одного выражения», вынеси её в named method и
передавай method reference.

### `java-style/guard-clauses-preferred` Guard expression вместо вложенных условий

```java
public void someMethod() {              // PREFER
    if (!condition) {
        throw e;
    }
    doSomething();
}

public void someMethod() {              // AVOID
    if (condition) {
        doSomething();
    } else {
        throw e;
    }
}
```

---

## 5. Отступы и форматирование

### `java-style/formatting-rules` Длина строки — не более 120 символов

Включая отступы.

### `java-style/formatting-rules` Перенос длинных выражений

Если выражение не умещается в 120 символов, разбиваем по правилам:

- **После запятой** (для аргументов / списков):

  ```java
  List<String> colors = Arrays.asList("red", "green", "blue");
  ```

- **Перед оператором**:

  ```java
  int sum = a
      + b;
  boolean isValid = (count > 0)
      && (value != null);
  ```

- **Сопоставление новой строки** с началом выражения:

  ```java
  long totalCount = firstValue
                    + secondValue
                    + thirdValue
                    + fourthValue;

  String message = String.format(
      "User: %s, Age: %d, Score: %f",
      userName, userAge, userScore
  );
  ```

### `java-style/formatting-rules` Не использовать горизонтальное выравнивание переменных

```java
public class Entity {
    public String name;                 // PREFER
    public int age;
}

public class Entity {
    public String name;                 // AVOID — выравнивание тратит время в diff
    public int    age;
}
```

---

## 6. Lombok

Lombok применяется во всех модулях по умолчанию — он убирает шум boilerplate-конструкторов и логгеров, не меняя видимой семантики. Правила ниже — обязательные.

### `java-style/boilerplate-is-generated` Конструктор строим через Lombok — всегда, без исключений по типу класса

Правило универсальное: **любой класс с `private final`-полями, которые инициализируются конструктором** — `@RequiredArgsConstructor`. Не только Spring-бины. Применяется к:

- `@Component` / `@Service` / `@Repository` / `@RestController` / `@Configuration` с DI.
- Доменным `*Service` / `*Handler` / `*Mapper` / `*Validator` (могут быть Spring-бинами или просто POJO).
- Адаптерам, helper-классам, integration-клиентам.
- Custom exception-классам с payload-полями (см. также `java-style/boilerplate-is-generated` про `@Getter`).
- Любому value-object'у, который **не record** (для record используется свой ctor — см. `java-style/no-generation-on-records`).

```java
// Spring-бин
@Component
@RequiredArgsConstructor
public class CreateOrderCommandHandler implements UseCaseHandler<CreateOrderCommand, OrderDto> {
    private final OrderRepository orders;
    private final DateTimeService dateTimeService;
    private final UuidGenerator uuidGenerator;
}

// Не Spring-бин — те же правила
@RequiredArgsConstructor
public class OrderTotalCalculator {
    private final TaxService tax;
    private final DiscountPolicy discounts;

    public Money calculate(List<OrderItem> items) { /* ... */ }
}

// Custom exception с payload
@Getter
@RequiredArgsConstructor
public class InvalidStateTransitionException extends RuntimeException {
    private final ProductStatus from;
    private final ProductStatus to;
}
```

Явный `public Foo(Bar bar) { this.bar = bar; }` **не пишем**. Это перекрывает `usecase-pattern/handler-is-stateless` из `backend/usecase-pattern/references/java/implementation.md`.

**Когда явный конструктор всё-таки оправдан** (исключения, не основное правило):

1. Нужна **валидация аргументов в конструкторе** (`Objects.requireNonNull`, `if (x < 0) throw ...`). Lombok не даёт хука.
2. Нужен `super(...)`-вызов с не-стандартными аргументами (например, наследование от чужого класса, у которого нет no-arg ctor).
3. Нужен **factory-метод** на VO или объекте переноса (`Money.of(...)`) — это уже не «конструктор», а named ctor; у агрегатов путь другой — фабрика `<X>Factory.create(...)` и `@Builder` как проводка (см. `java-style/builder-used-sparingly` про `@Builder` — то же мышление).
4. Класс должен иметь **no-arg constructor для frameworks** (JPA entity, Jackson DTO без records). В этом случае часто используется `@NoArgsConstructor(access = AccessLevel.PROTECTED)` + `@Getter` + `@Setter` — но это кейс legacy-биндинга, см. `java-style/no-generation-on-records`.

Во всех остальных случаях — `@RequiredArgsConstructor`.

### `JS-6.X1` ❌ Явный all-args конструктор там, где подошёл `@RequiredArgsConstructor`

```java
// AVOID — boilerplate без причины
public class CreateOrderCommandHandler {
    private final OrderRepository orders;
    private final DateTimeService dateTimeService;

    public CreateOrderCommandHandler(OrderRepository orders, DateTimeService dateTimeService) {
        this.orders = orders;
        this.dateTimeService = dateTimeService;
    }
}
```

Превращаем в `@RequiredArgsConstructor`. Если есть валидация в ctor — оставляем явный конструктор (без комментариев, `java-style/no-comments-in-code`).

### `JS-6.X2` ❌ `@AllArgsConstructor` на DI-классах

`@AllArgsConstructor` генерит ctor для **всех** полей, включая non-final. Это значит — позже добавили `private boolean cached = false`, и ctor требует его передавать, ломаются все вызовы. Для DI правильный — `@RequiredArgsConstructor` (только final). `@AllArgsConstructor` — для DTO и тестовых fixtures.

### `java-style/boilerplate-is-generated` `@Slf4j` вместо ручного логгера

```java
@Slf4j
@Component
public class FooService { /* log.info(...) */ }
```

Не пишем `private static final Logger log = LoggerFactory.getLogger(FooService.class);` — это шум.

### `java-style/boilerplate-is-generated` `@Getter` на custom exceptions и value-objects, которые не records

Когда исключение несёт payload-поля (`productId`, `from`, `to`), accessor-методы — через `@Getter`, не руками. Если accessor нужен в record-стиле (без `get`-префикса) — оставляем явный, но не дублируем `@Getter`.

```java
@Getter
public class InvalidStateTransitionException extends RuntimeException {
    private final ProductStatus from;
    private final ProductStatus to;
    public InvalidStateTransitionException(ProductStatus from, ProductStatus to) {
        super("Invalid transition: " + from + " -> " + to);
        this.from = from;
        this.to = to;
    }
}
```

### `java-style/no-generation-on-records` На records — только `@Builder`

Records уже дают immutable ctor / accessors / `equals` / `hashCode` / `toString`. `@Value`, `@Data`, `@AllArgsConstructor`, `@Getter` / `@Setter`, `@EqualsAndHashCode` / `@ToString` поверх record — мусор, и Lombok их на записях отвергает при компиляции. `@Builder` на record'е с многими необязательными полями — норма: в эталоне так размечены 23 из 24 фильтров портов, команды с параметрами по умолчанию, DTO внешних протоколов; `@Builder(toBuilder = true)` — когда нужна копия с одним изменённым полем.

### `java-style/no-generation-on-records` `@Data` — не на домене и не на объектах переноса

Единственное законное место `@Data` / `@Setter` — класс, которому фреймворк требует изменяемый bean: классы свойств планировщика и Kafka, конверт ответа внешнего протокола (в эталоне — 1 `@Data` и 18 `@Setter`, все в `config/` и адаптерах, в `core/` — ноль).

`@Data` генерирует mutable setters + equals/hashCode по всем полям — это две диверсии в одном: оно ломает неизменяемость и делает entity сравнимыми по `id` равных в коллекциях, что приводит к багам в `Set`-ах и JPA-кешах. Нужен POJO с геттерами/сеттерами для legacy-биндинга — пишем `@Getter @Setter` явно. Для иммутабельных DTO — record (см. `java-style/no-generation-on-records`).

### `java-style/generation-setup-is-uniform` Build-настройка одинакова во всех модулях

```kotlin
compileOnly("org.projectlombok:lombok:1.18.34")
annotationProcessor("org.projectlombok:lombok:1.18.34")
testCompileOnly("org.projectlombok:lombok:1.18.34")
testAnnotationProcessor("org.projectlombok:lombok:1.18.34")
```

Версия фиксируется в `gradle/libs.versions.toml` (если используется). `lombok` НЕ в `implementation` — это compile-time-only зависимость, не должна попасть в runtime classpath.

### `java-style/builder-used-sparingly` `@Builder` — на объектах переноса, на агрегате — проводка фабрики

`@Builder` уместен на объектах переноса с многими полями и опциональными значениями: фильтры портов, команды с параметрами по умолчанию, исходящие запросы во внешний API, настройки. Не вешаем его на каждый POJO «на всякий случай» — это раздувает API класса.

На entity / aggregate root `@Builder` стоит (в эталоне — на всех 19 агрегатах и 12 сущностях), но это не API, а проводка: публичного конструктора у агрегата нет (Lombok генерирует package-private all-args), а `builder()` зовут ровно два места — `<X>Factory.create(...)` при создании и `<X>DomainRecordMapper.toDomain(...)` при восстановлении из БД. Любой другой вызов — обход проверок создания, его ловит `AggregateBuildersUsedOnlyByFactoriesTest` (правило — в `ddd-tactical/references/java/implementation.md`, §7).

---

## 7. Комментарии

### `java-style/no-comments-in-code` Комментариев в коде нет — вообще

В production и test source **комментариев нет**: ни `//`, ни `/* … */`, ни Javadoc — ни в доменных классах, ни в хендлерах, ни в конфигах. Имя класса / метода / переменной + типы + структура отвечают на «что делает». Это абсолютное правило, не «по умолчанию»: комментарий — не «последняя линия», а нарушение.

### `java-style/no-comments-in-code` Неочевидный WHY выражается именем, структурой или спекой — не комментарием

Если «почему так» неочевидно — **переименуй**, **выдели метод с говорящим именем** или **зафиксируй в спеке** (`docs/spec/`). Комментарий не вариант ни при каких условиях.

Недопустимо (любой комментарий):

```java
// проверяем владельца
if (!owner.equals(requester)) { ... }

// 404, не 403 — не подтверждаем существование чужого продукта
throw new OwnProductRequiredException(productId);
```

В первом случае имя переменной уже всё говорит; во втором знание «404, не 403» несут имя `OwnProductRequiredException` (маппинг в `@ExceptionHandler`) и правило в §Команды спеки.

### `java-style/no-rule-codes-or-history-in-code` Не цитируем коды правил из спеки и стайл-гайдов в коде

**Запрещено** в production / test source:

```java
// BR-C5: Publish — только из DRAFT|HIDDEN.       // ❌
// AUTH-15: фасад над audit log.                   // ❌
// R-LAY-3: маппинг через MapStruct.               // ❌
// TS-9..TS-11: fluent preparer.                   // ❌
// BS-17/18: jOOQ-only, generated POJO.            // ❌
```

Причины:

- Дублирует source-of-truth: правило живёт в гайде/спеке, а не в комментарии.
- Хрупко: при следующей ревизии гайда нумерация уезжает, комментарии в коде молча становятся ложью.
- Шум для читателя: соответствие правилу должно выражаться **именами и структурой** (запись `record` + `UseCaseCommand` уже = `R-UC-1..3`; `@RequiredArgsConstructor` уже = `java-style/boilerplate-is-generated`; `@Mapper(componentModel="spring")` уже = `usecase-pattern/explicit-mapper-between-layers`).

Куда уходят коды правил: commit messages, PR description, сам гайд / спека. Не в исходники.

То же касается `remarks:` в Liquibase changelog: человеческое описание — да, код правила — нет.

### `java-style/no-rule-codes-or-history-in-code` Не пишем комментарии «что тут было», «убрано для X», «TODO до spring 4»

`git blame` и история коммитов — авторитетный источник изменений. Комментарии типа `// removed because YYY` или `// added for the Z flow` гниют быстро и засоряют diff.

### `java-style/no-comments-in-code` Javadoc не используем — нигде, включая публичный API библиотек

Командное правило **без исключений**: внутренний код, public API сервиса, OSS-библиотеки (`ddd-building-blocks`, `hexagonal-architecture`, `usecase-pattern`) — везде. Causes:

- **Javadoc гниёт быстрее кода**. Сигнатура переименована — Javadoc остался про старое имя. Поведение изменилось — описание не тронули. Через год документация хуже, чем её отсутствие, потому что вводит в заблуждение.
- **Сам код — документация**. Хорошее имя метода + типы аргументов + типы возврата + читаемая реализация дают consumer-у больше, чем 4-строчный Javadoc «Returns the user by id».
- **Consumer OSS-библиотеки читает источники на GitHub**. Код в `ddd-building-blocks` короткий и явный — `AggregateRoot.java` ≈ 80 строк, понятен за минуту. Альтернатива «открыть Javadoc на сайте» хуже: не виден контекст, не пройти к ссылающимся местам, не запустить тесты.
- **Если нужен сложный контракт — это спека** (`docs/spec/`), не Javadoc. Спецификация версионируется отдельно от кода и обсуждается в PR-ревью; Javadoc — инициатива одного автора, не проходит через коллектив.
- **Читать через IDE (`Cmd-Click` на метод)** даёт лучший результат, чем `hover` на Javadoc — ты видишь реализацию.

Что делать вместо Javadoc:
- Имя метода / класса / поля несёт смысл (см. правила `JS-2.*`).
- Не-очевидные **инварианты** (срок жизни bean, threadsafety, порядок вызовов) — выражаются именами/аннотациями (`@Scope`, `@ThreadSafe` и т.п.) или фиксируются в спеке/`docs`; **комментарием — нет** (`java-style/no-comments-in-code`).
- Доменный контракт операции — спека в `docs/spec/`.

### `JS-7.X1` ❌ Любой комментарий — `//`, `/* … */`, Javadoc

Любой комментарий в коде — нарушение `java-style/no-comments-in-code`. `/** … */` с `@param`/`@return`/`@throws`/`@see` — частный случай (Javadoc, `java-style/no-comments-in-code`). Нужен контракт/нюанс — в спеку, не в код.

### `JS-7.X2` ❌ Конфигурация `javadoc`-task в `build.gradle` / `pom.xml` для production-сервиса

Не запускаем `./gradlew javadoc`, не публикуем `*-javadoc.jar` в Maven Central / Nexus. Один источник правды — исходники + спека.

---

## 8. Современные фичи Java

Раздел применяется, **если проект собирается на Java 21+** (проверить
`sourceCompatibility = JavaVersion.VERSION_21` в `build.gradle` или
`<source>21</source>` в `pom.xml`). На Java 17 применимы только правила
про records и sealed без record patterns. На Java 11 и ниже раздел
не применим.

### `java-style/exhaustive-switch-on-sealed` Switch expression на sealed-иерархии вместо if-else цепочек

Если значение принадлежит sealed-иерархии и нужно вернуть результат
на основе варианта — `switch` expression, не цепочка `instanceof`-проверок.
Компилятор гарантирует exhaustiveness и поймает забытый вариант
при добавлении нового подтипа.

```java
// PREFER
return switch (parking) {
    case ParkingResolution.None ignored -> null;
    case ParkingResolution.Reused(UUID id) -> id;
    case ParkingResolution.Created(UUID id) -> id;
};

// AVOID — exhaustiveness не гарантируется компилятором
if (parking instanceof ParkingResolution.None) return null;
if (parking instanceof ParkingResolution.Reused r) return r.id();
if (parking instanceof ParkingResolution.Created c) return c.id();
throw new IllegalStateException("Unhandled: " + parking);
```

### `java-style/exhaustive-switch-on-sealed` Record patterns в `case` — для деконструкции

Если вариант sealed-иерархии — record, его поля разбираем прямо
в `case`, без `.field()` геттера в правой части.

```java
// PREFER
case ParkingResolution.Created(UUID id) -> id;

// AVOID — двойная работа: распознали тип и тут же тянем геттер
case ParkingResolution.Created c -> c.id();
```

Когда поле в варианте есть, но не нужно — `ignored` как имя binding-а:

```java
case ParkingResolution.None ignored -> null;
```

### `java-style/exhaustive-switch-on-sealed` Record patterns в `instanceof` — для деконструкции

В `if (x instanceof Type)` — также через record pattern, не через
binding + геттер.

```java
// PREFER
if (parking instanceof ParkingResolution.Created(UUID parkingSessionId)) {
    parkingSessionService.cancelParking(parkingSessionId);
}

// AVOID
if (parking instanceof ParkingResolution.Created created) {
    parkingSessionService.cancelParking(created.id());
}
```

### `java-style/exhaustive-switch-on-sealed` Exhaustive switch без `default` для sealed-иерархий

Если switch покрывает все варианты sealed-иерархии — **не** добавляем
`default`. Компилятор обязан проверить exhaustiveness, и `default` молча
проглотит новый вариант, который ты забудешь обработать после расширения
иерархии.

```java
// PREFER — компилятор сломает сборку, если добавить новый ParkingResolution
return switch (parking) {
    case ParkingResolution.None ignored -> null;
    case ParkingResolution.Reused(UUID id) -> id;
    case ParkingResolution.Created(UUID id) -> id;
};

// AVOID — default превращает compile-time error в runtime
return switch (parking) {
    case ParkingResolution.None ignored -> null;
    case ParkingResolution.Reused(UUID id) -> id;
    case ParkingResolution.Created(UUID id) -> id;
    default -> throw new IllegalStateException("Unhandled: " + parking);
};
```

`default` оправдан только для open-иерархий (switch по `String`, `int`,
enum, который может быть расширен в будущем).

### `java-style/exhaustive-switch-on-sealed` Sealed interfaces — для closed-набора альтернатив

Если у концепта **закрытый** набор вариантов, известный во время
компиляции (`None / Reused / Created`, `Success / Failure`,
`Free / Premium / Trial`) — `sealed interface` + record-варианты.
Это включает exhaustiveness check в switch (`java-style/exhaustive-switch-on-sealed`, `java-style/exhaustive-switch-on-sealed`)
и делает добавление варианта compile-time-событием.

```java
// PREFER
public sealed interface ParkingResolution {
    record None() implements ParkingResolution {}
    record Reused(UUID id) implements ParkingResolution {}
    record Created(UUID id) implements ParkingResolution {}

    static ParkingResolution none() { return new None(); }
}
```

Sealed **не** для open-расширяемых иерархий (доменные базовые классы,
которые расширяет чужой код в других модулях / сервисах) — там обычный
`interface`.

### `java-style/prefer-modern-constructs` `String.formatted()` вместо `String.format()`

```java
// PREFER
"User(id=%s) default card not found".formatted(userId);

// AVOID
String.format("User(id=%s) default card not found", userId);
```

Читается линейно слева-направо: «строка → подставить аргументы».
`String.format(...)` ставит шаблон в начало, аргументы в конец, что
заставляет глаз бегать. Особенно заметно в длинных сообщениях
exception-ов.

### `java-style/prefer-modern-constructs` Records для in-class data carriers

Маленькие data-структуры внутри handler-а / сервиса (3–5 полей,
используются только в этом классе) — `private record`, без Lombok-обёрток,
без отдельного Value Object.

```java
// PREFER — внутри handler-а собрать связанные сущности из репозиториев
private record ChargingContext(
        ConnectorsPojo connector,
        ChargeStationsPojo chargeStation,
        LocationsPojo location
) {}

// AVOID — Lombok-класс ради тех же геттеров
@Getter
@RequiredArgsConstructor
private static class ChargingContext {
    private final ConnectorsPojo connector;
    private final ChargeStationsPojo chargeStation;
    private final LocationsPojo location;
}
```

Lombok поверх records запрещён (`java-style/no-generation-on-records`). Если структура нужна снаружи
класса как доменный VO — это уже отдельный concern: см.
`backend/ddd-tactical/references/java/implementation.md`.

---

## Настройка IDE (IntelliJ IDEA)

1. Берём `checkstyle.xml` из проекта.
2. Ставим плагин **CheckStyle-IDEA** (нужен VPN при установке во внутренней
   сети).
3. `File → Settings → Code Style → Java`.
4. Шестерёнка → Import Scheme → Checkstyle Configuration.
5. В корне проекта кладём `.editorconfig` для отступов.
6. Запускаем сканирование проекта в плагине.

---

## Краткий чек-лист обзора

| Группа | Правила |
|---|---|
| Именование | `java-style/package-and-type-naming`–`java-style/member-naming`, тесты — `java-style/test-method-naming` |
| Импорты | `java-style/imports-are-explicit`, `java-style/imports-are-explicit` |
| Выражения | `java-style/expressions-stay-simple`–`java-style/guard-clauses-preferred` |
| Отступы | `java-style/formatting-rules`–`java-style/formatting-rules` |
| Lombok | `java-style/boilerplate-is-generated`–`java-style/builder-used-sparingly`, антипаттерны `JS-6.X1`–`JS-6.X2` |
| Комментарии | `java-style/no-comments-in-code`–`java-style/no-comments-in-code`, антипаттерны `JS-7.X1`–`JS-7.X2` |
| Java 21+ фичи | `java-style/exhaustive-switch-on-sealed`–`java-style/prefer-modern-constructs` (применимо если проект на Java 21+) |
| Enforcement через Checkstyle | `java-style/style-check-is-enforced`–`java-style/style-check-is-enforced`, антипаттерны `java-style/style-check-is-enforced`–`java-style/mechanical-versus-semantic-split` |

---

## 9. Enforcement через Checkstyle

Часть правил из этого гайда (нейминг, импорты, отступы) механически проверяема — выносим её в Checkstyle, чтобы не тратить ревью на «forgot Test-suffix» или «звёздный импорт». Семантические правила (Lombok-defaults, комментарии, Java 21+ фичи) остаются для скилла `ucp-java-style-review`. Checkstyle и AI-скилл — дополняющие, не альтернативные.

`java-style/style-check-is-enforced` **Checkstyle обязателен** на всех Java-сервисах. Подключается через стандартный `checkstyle` gradle plugin с командным конфигом `config/checkstyle/checkstyle.xml`. Конфиг живёт в репо сервиса (не как submodule, не как зависимость) — иначе Checkstyle становится «чёрным ящиком», и каждое его срабатывание превращается в спор без возможности проверить.

```gradle
plugins {
    id 'checkstyle'
}
checkstyle {
    toolVersion = '10.20.2'
    configFile = file('config/checkstyle/checkstyle.xml')
    configProperties = [ 'baseDir': rootDir ]
    maxWarnings = 0
    ignoreFailures = false
}
tasks.withType(Checkstyle).configureEach {
    reports {
        xml.required = true
        html.required = true
        sarif.required = true     // публикуется в GitHub Code Scanning, как SpotBugs (R-SEC-FIND-3)
    }
}
```

`java-style/mechanical-versus-semantic-split` **Checkstyle покрывает только механические правила**:
- именование (`java-style/package-and-type-naming`–`java-style/member-naming`) через `TypeName`/`MethodName`/`PackageName`/`ConstantName`,
- импорты (`java-style/imports-are-explicit`/`java-style/imports-are-explicit`) через `AvoidStarImport`/`UnusedImports`/`CustomImportOrder`,
- отступы (`java-style/formatting-rules`–`java-style/formatting-rules`) через `Indentation`/`LineLength`,
- whitespace через `WhitespaceAround`/`EmptyLineSeparator`.

Для имени тестов (`java-style/test-method-naming` — `*Test.java` в `src/test/java`) — `Regexp`-модуль с pattern `.*Test\\.java`.

Семантические правила (`JS-6.*` Lombok-defaults, `JS-7.*` комментарии, `JS-8.*` Java 21+ фичи) **в Checkstyle не выносим** — они требуют контекста и применяются скиллом `ucp-java-style-review`. Не пытайтесь натянуть их на Checkstyle через regex — false positive утопят сигнал.

`java-style/style-check-is-enforced` **`maxWarnings = 0` + `ignoreFailures = false`** — обязательно. Если хочется временно ослабить правило — добавь suppression в `config/checkstyle/checkstyle-suppressions.xml` с обязательным комментарием `<!-- justify: ... до: YYYY-MM-DD -->` (по аналогии с `security/suppressions-are-files-with-deadline`).

```xml
<?xml version="1.0"?>
<!DOCTYPE suppressions PUBLIC
    "-//Checkstyle//DTD SuppressionFilter Configuration 1.2//EN"
    "https://checkstyle.org/dtds/suppressions_1_2.dtd">
<suppressions>
    <!-- justify: legacy package с auto-generated классами; рефакторинг до 2026-09-01 -->
    <suppress files=".*[/\\]generated[/\\].*" checks="."/>
</suppressions>
```

`java-style/style-check-is-enforced` **Checkstyle привязан к `check`**, не к `checkSecurity` (`spring-bootstrap/security-checks-split-by-task`). Это lint-уровень, не security — должен прогоняться на каждом локальном `./gradlew check` и в любом CI-job, где идут тесты:

```gradle
tasks.named('check') {
    dependsOn 'checkstyleMain', 'checkstyleTest'
}
```

`java-style/style-check-is-enforced` **Конфиг `config/checkstyle/checkstyle.xml`** базируется на Sun/Google checks, ослаблен под наши конвенции (например, `LineLength: max=120`, разрешён `_` в именах test-методов per `java-style/test-method-naming`). Полный шаблон — `config/checkstyle/checkstyle.xml.template`, поставляется через `ucp-bootstrap-design` при создании нового сервиса.

`java-style/style-check-is-enforced` ❌ **`@SuppressWarnings("checkstyle:...")`** в коде без комментария-justify (≥ 30 символов). Можно только в крайних случаях с обоснованием — иначе подавляется глобально, на ревью не разглядишь.

`java-style/style-check-is-enforced` ❌ **Удаление правил из `checkstyle.xml`** «потому что мешают». Если правило реально устарело — обсуждается командой, обновляется конфиг для всех сервисов сразу. Локальное удаление приводит к расхождению conventions между сервисами.

`java-style/mechanical-versus-semantic-split` ❌ **Использование Checkstyle для семантических проверок** (regex-правила «все public-методы возвращают `Optional`», подсчёт строк в методе для cyclomatic complexity и т.п.). Это регрессия в сторону «ad-hoc регулярки в xml», которые никто не сможет читать через год. Семантика — `ucp-java-style-review` или отдельный AI-скилл.
