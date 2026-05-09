# Java Style Guide

Свод правил для Java-кода. Каждое правило имеет код вида `JS-<section>.<num>` —
скилл `java-style-review` цитирует эти коды в findings.

Базовый принцип (`JS-1.1`): **допускается любое нарушение, если оно улучшает
читаемость**. Цель руководства — улучшить читаемость, понимание и общее
качество кода, а не превратить ревью в формальную проверку.

Источник: внутренний Java Style guide (Yandex Wiki).

---

## 1. Общие рекомендации

- **`JS-1.1`** — любое нарушение допустимо, если оно улучшает читаемость. Это
  не индульгенция «писать как хочется»: от ревьюера ожидается явное
  объяснение, чем именно нарушение лучше.

---

## 2. Именование

### `JS-2.1` Имена пакетов

Имена пакетов — в нижнем регистре, без подчёркиваний и других специальных
символов.

```java
package com.example.orderservice;       // PREFER
package com.example.order_service;      // AVOID
package com.example.OrderService;       // AVOID
```

### `JS-2.2` Множественное число в пакетах запрещено

Следуем соглашению стандартного API: `java.util`, не `java.utils`.

```java
package com.example.util;               // PREFER
package com.example.utils;              // AVOID
```

### `JS-2.3` Имена классов — существительные

```java
class Car {}                            // PREFER
class Running {}                        // AVOID — глагольная форма
```

### `JS-2.4` Имена интерфейсов — существительные или прилагательные на `-able`

Не начинать имя с `I` (это привет шарпистам).

```java
interface Runnable {}                   // PREFER
interface Comparable {}                 // PREFER
interface IEnumerable {}                // AVOID
```

### `JS-2.5` Аббревиатуры в именах

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

### `JS-2.6` Имена методов — глаголы или описание действия

```java
public String getName() {}              // PREFER
public String name() {}                 // AVOID

public void expand() {}                 // PREFER
public boolean expanding() {}           // AVOID
```

### `JS-2.6.1` Имена тестов

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

### `JS-2.7` Имена переменных — camelCase, начинаются с lowercase

```java
int currentValue;                       // PREFER
int PreviousValue;                      // AVOID
```

### `JS-2.8` Имена констант — `UPPER_SNAKE_CASE`, обязательно `static final`

```java
public static final int BUFFER_SIZE = 1024;   // PREFER
public final int ARRAY_SIZE = 10;             // AVOID — не static
```

---

## 3. Импорты

### `JS-3.1` Не использовать wildcard-импорты

```java
import some.java.package.ParticularClass;     // PREFER
import some.java.package.*;                   // AVOID
```

Исключение — `java.util.*` допустим.

### `JS-3.2` Не оставлять неиспользуемых импортов

---

## 4. Выражения

### `JS-4.1` Сложность булева выражения — не более 3 операторов `&&`/`||`

```java
boolean good = (!a && b) | (a || !b) ^ a;     // PREFER (3 op)
boolean bad  = (a && b) && c && (c || b);     // AVOID (4 op)
```

Слишком много условий → код трудно читать, отлаживать и поддерживать.

### `JS-4.2` Избегать C-стиля объявления массивов

```java
int[] nums;                             // PREFER
String strs[];                          // AVOID
```

### `JS-4.3` Порядок модификаторов

```
public → protected → private → static → final → transient → volatile → synchronized
```

### `JS-4.4` Не указывать неявные модификаторы

- В методах интерфейса не пишем `public` или `abstract` (они подразумеваются).
- Во вложенных enum и interface не пишем `static`.

### `JS-4.5` Method reference вместо лямбды, где имеет смысл

```java
filter(someStrings::contains);          // PREFER
filter(s -> someStrings.contains(s));   // AVOID
```

### `JS-4.6` Большие лямбды выносить в методы

Если в лямбде логика «больше одного выражения», вынеси её в named method и
передавай method reference.

### `JS-4.7` Guard expression вместо вложенных условий

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

### `JS-5.1` Длина строки — не более 120 символов

Включая отступы.

### `JS-5.2` Перенос длинных выражений

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

### `JS-5.3` Не использовать горизонтальное выравнивание переменных

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

### `JS-6.1` Конструктор строим через Lombok — всегда, без исключений по типу класса

Правило универсальное: **любой класс с `private final`-полями, которые инициализируются конструктором** — `@RequiredArgsConstructor`. Не только Spring-бины. Применяется к:

- `@Component` / `@Service` / `@Repository` / `@RestController` / `@Configuration` с DI.
- Доменным `*Service` / `*Handler` / `*Mapper` / `*Validator` (могут быть Spring-бинами или просто POJO).
- Адаптерам, helper-классам, integration-клиентам.
- Custom exception-классам с payload-полями (см. также `JS-6.3` про `@Getter`).
- Любому value-object'у, который **не record** (для record используется свой ctor — см. `JS-6.4`).

```java
// Spring-бин
@Component
@RequiredArgsConstructor
public class CreateOrderUseCaseHandler implements UseCaseHandler<CreateOrderUseCase, OrderDto> {
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

Явный `public Foo(Bar bar) { this.bar = bar; }` **не пишем**. Это перекрывает `R-HND-5` из `usecase-pattern-style-guide.md`.

**Когда явный конструктор всё-таки оправдан** (исключения, не основное правило):

1. Нужна **валидация аргументов в конструкторе** (`Objects.requireNonNull`, `if (x < 0) throw ...`). Lombok не даёт хука.
2. Нужен `super(...)`-вызов с не-стандартными аргументами (например, наследование от чужого класса, у которого нет no-arg ctor).
3. Нужен **factory-метод** (`Order.draft(...)`, `Order.fromPersistence(...)`) — это уже не «конструктор», это бизнес-named ctor; для агрегатов это норма (см. `JS-6.7` про `@Builder` — то же мышление).
4. Класс должен иметь **no-arg constructor для frameworks** (JPA entity, Jackson DTO без records). В этом случае часто используется `@NoArgsConstructor(access = AccessLevel.PROTECTED)` + `@Getter` + `@Setter` — но это кейс legacy-биндинга, см. `JS-6.5`.

Во всех остальных случаях — `@RequiredArgsConstructor`.

### `JS-6.X1` ❌ Явный all-args конструктор там, где подошёл `@RequiredArgsConstructor`

```java
// AVOID — boilerplate без причины
public class CreateOrderUseCaseHandler {
    private final OrderRepository orders;
    private final DateTimeService dateTimeService;

    public CreateOrderUseCaseHandler(OrderRepository orders, DateTimeService dateTimeService) {
        this.orders = orders;
        this.dateTimeService = dateTimeService;
    }
}
```

Превращаем в `@RequiredArgsConstructor`. Если есть валидация в ctor — оставляем явный, но с комментарием **зачем** (`JS-7.2`).

### `JS-6.X2` ❌ `@AllArgsConstructor` на DI-классах

`@AllArgsConstructor` генерит ctor для **всех** полей, включая non-final. Это значит — позже добавили `private boolean cached = false`, и ctor требует его передавать, ломаются все вызовы. Для DI правильный — `@RequiredArgsConstructor` (только final). `@AllArgsConstructor` — для DTO и тестовых fixtures.

### `JS-6.2` `@Slf4j` вместо ручного логгера

```java
@Slf4j
@Component
public class FooService { /* log.info(...) */ }
```

Не пишем `private static final Logger log = LoggerFactory.getLogger(FooService.class);` — это шум.

### `JS-6.3` `@Getter` на custom exceptions и value-objects, которые не records

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

### `JS-6.4` Lombok **не** на records

Records уже дают immutable ctor / accessors / `equals` / `hashCode` / `toString`. `@Value`, `@Data`, `@AllArgsConstructor` поверх record — мусор и компилятор ругается.

### `JS-6.5` `@Data` запрещён в производственном коде

`@Data` генерирует mutable setters + equals/hashCode по всем полям — это две диверсии в одном: оно ломает неизменяемость и делает entity сравнимыми по `id` равных в коллекциях, что приводит к багам в `Set`-ах и JPA-кешах. Нужен POJO с геттерами/сеттерами для legacy-биндинга — пишем `@Getter @Setter` явно. Для иммутабельных DTO — record (см. `JS-6.4`).

### `JS-6.6` Build-настройка одинакова во всех модулях

```kotlin
compileOnly("org.projectlombok:lombok:1.18.34")
annotationProcessor("org.projectlombok:lombok:1.18.34")
testCompileOnly("org.projectlombok:lombok:1.18.34")
testAnnotationProcessor("org.projectlombok:lombok:1.18.34")
```

Версия фиксируется в `gradle/libs.versions.toml` (если используется). `lombok` НЕ в `implementation` — это compile-time-only зависимость, не должна попасть в runtime classpath.

### `JS-6.7` `@Builder` — точечно, не везде

`@Builder` уместен на сложных DTO с 5+ полями и опциональными значениями (например, исходящие запросы во внешний API, настройки). Не вешаем его на каждый POJO «на всякий случай» — это раздувает API класса.

`@Builder` запрещён на entity / aggregate root: построение агрегата идёт через named-конструкторы (`Order.draft(...)`, `Order.fromPersistence(...)`), Lombok-builder делает это бесконтрольно и обходит инварианты.

---

## 7. Комментарии

### `JS-7.1` По умолчанию — не пишем комментарии

Хорошее имя класса / метода / переменной + структура кода уже отвечают на «что делает». Комментарий — последняя линия, когда имя/структура не справляются.

### `JS-7.2` Комментарий уместен только когда WHY неочевиден

Допустимо:

```java
// 404, не 403 — не подтверждаем существование чужого продукта
throw new OwnProductRequiredException(productId);
```

Недопустимо:

```java
// проверяем владельца
if (!owner.equals(requester)) { ... }    // имя владельца уже всё сказало
```

### `JS-7.3` Не цитируем коды правил из спеки и стайл-гайдов в коде

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
- Шум для читателя: соответствие правилу должно выражаться **именами и структурой** (запись `record` + `UseCaseCommand` уже = `R-UC-1..3`; `@RequiredArgsConstructor` уже = `JS-6.1`; `@Mapper(componentModel="spring")` уже = `R-LAY-3`).

Куда уходят коды правил: commit messages, PR description, сам гайд / спека. Не в исходники.

То же касается `remarks:` в Liquibase changelog: человеческое описание — да, код правила — нет.

### `JS-7.4` Не пишем комментарии «что тут было», «убрано для X», «TODO до spring 4»

`git blame` и история коммитов — авторитетный источник изменений. Комментарии типа `// removed because YYY` или `// added for the Z flow` гниют быстро и засоряют diff.

### `JS-7.5` Javadoc не используем — нигде, включая публичный API библиотек

Командное правило **без исключений**: внутренний код, public API сервиса, OSS-библиотеки (`ddd-building-blocks`, `hexagonal-architecture`, `usecase-pattern`) — везде. Causes:

- **Javadoc гниёт быстрее кода**. Сигнатура переименована — Javadoc остался про старое имя. Поведение изменилось — описание не тронули. Через год документация хуже, чем её отсутствие, потому что вводит в заблуждение.
- **Сам код — документация**. Хорошее имя метода + типы аргументов + типы возврата + читаемая реализация дают consumer-у больше, чем 4-строчный Javadoc «Returns the user by id».
- **Consumer OSS-библиотеки читает источники на GitHub**. Код в `ddd-building-blocks` короткий и явный — `AggregateRoot.java` ≈ 80 строк, понятен за минуту. Альтернатива «открыть Javadoc на сайте» хуже: не виден контекст, не пройти к ссылающимся местам, не запустить тесты.
- **Если нужен сложный контракт — это спека** (`docs/spec/`), не Javadoc. Спецификация версионируется отдельно от кода и обсуждается в PR-ревью; Javadoc — инициатива одного автора, не проходит через коллектив.
- **Читать через IDE (`Cmd-Click` на метод)** даёт лучший результат, чем `hover` на Javadoc — ты видишь реализацию.

Что делать вместо Javadoc:
- Имя метода / класса / поля несёт смысл (см. правила `JS-2.*`).
- Не-очевидные **инварианты** (срок жизни bean, threadsafety, порядок вызовов) — пишутся **обычным комментарием** при объявлении, по правилам `JS-7.2` (комментарий уместен когда WHY неочевиден). Это не Javadoc — это `//`-комментарий или короткий `/* ... */` без `@param`/`@return`.
- Доменный контракт операции — спека в `docs/spec/<usecase>/`.

### `JS-7.X1` ❌ Любой `/** ... */` блок с тегами `@param`, `@return`, `@throws`, `@see`

Это явный признак Javadoc-а — нарушение `JS-7.5`. Если нужно описать редкий нюанс — обычный комментарий по `JS-7.2`, без формального формата.

### `JS-7.X2` ❌ Конфигурация `javadoc`-task в `build.gradle` / `pom.xml` для production-сервиса

Не запускаем `./gradlew javadoc`, не публикуем `*-javadoc.jar` в Maven Central / Nexus. Один источник правды — исходники + спека.

---

## 8. Современные фичи Java

Раздел применяется, **если проект собирается на Java 21+** (проверить
`sourceCompatibility = JavaVersion.VERSION_21` в `build.gradle` или
`<source>21</source>` в `pom.xml`). На Java 17 применимы только правила
про records и sealed без record patterns. На Java 11 и ниже раздел
не применим.

### `JS-8.1` Switch expression на sealed-иерархии вместо if-else цепочек

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

### `JS-8.2` Record patterns в `case` — для деконструкции

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

### `JS-8.3` Record patterns в `instanceof` — для деконструкции

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

### `JS-8.4` Exhaustive switch без `default` для sealed-иерархий

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

### `JS-8.5` Sealed interfaces — для closed-набора альтернатив

Если у концепта **закрытый** набор вариантов, известный во время
компиляции (`None / Reused / Created`, `Success / Failure`,
`Free / Premium / Trial`) — `sealed interface` + record-варианты.
Это включает exhaustiveness check в switch (`JS-8.1`, `JS-8.4`)
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

### `JS-8.6` `String.formatted()` вместо `String.format()`

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

### `JS-8.7` Records для in-class data carriers

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

Lombok поверх records запрещён (`JS-6.4`). Если структура нужна снаружи
класса как доменный VO — это уже отдельный concern: см.
`ddd-tactical-style-guide.md`.

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
| Именование | `JS-2.1`–`JS-2.8`, тесты — `JS-2.6.1` |
| Импорты | `JS-3.1`, `JS-3.2` |
| Выражения | `JS-4.1`–`JS-4.7` |
| Отступы | `JS-5.1`–`JS-5.3` |
| Lombok | `JS-6.1`–`JS-6.7`, антипаттерны `JS-6.X1`–`JS-6.X2` |
| Комментарии | `JS-7.1`–`JS-7.5`, антипаттерны `JS-7.X1`–`JS-7.X2` |
| Java 21+ фичи | `JS-8.1`–`JS-8.7` (применимо если проект на Java 21+) |
| Enforcement через Checkstyle | `JS-CS-1`–`JS-CS-5`, антипаттерны `JS-CS-X1`–`JS-CS-X3` |

---

## 9. Enforcement через Checkstyle

Часть правил из этого гайда (нейминг, импорты, отступы) механически проверяема — выносим её в Checkstyle, чтобы не тратить ревью на «forgot Test-suffix» или «звёздный импорт». Семантические правила (Lombok-defaults, комментарии, Java 21+ фичи) остаются для скилла `ucp-java-style-review`. Checkstyle и AI-скилл — дополняющие, не альтернативные.

`JS-CS-1` **Checkstyle обязателен** на всех Java-сервисах. Подключается через стандартный `checkstyle` gradle plugin с командным конфигом `config/checkstyle/checkstyle.xml`. Конфиг живёт в репо сервиса (не как submodule, не как зависимость) — иначе Checkstyle становится «чёрным ящиком», и каждое его срабатывание превращается в спор без возможности проверить.

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

`JS-CS-2` **Checkstyle покрывает только механические правила**:
- именование (`JS-2.1`–`JS-2.8`) через `TypeName`/`MethodName`/`PackageName`/`ConstantName`,
- импорты (`JS-3.1`/`JS-3.2`) через `AvoidStarImport`/`UnusedImports`/`CustomImportOrder`,
- отступы (`JS-5.1`–`JS-5.3`) через `Indentation`/`LineLength`,
- whitespace через `WhitespaceAround`/`EmptyLineSeparator`.

Для имени тестов (`JS-2.6.1` — `*Test.java` в `src/test/java`) — `Regexp`-модуль с pattern `.*Test\\.java`.

Семантические правила (`JS-6.*` Lombok-defaults, `JS-7.*` комментарии, `JS-8.*` Java 21+ фичи) **в Checkstyle не выносим** — они требуют контекста и применяются скиллом `ucp-java-style-review`. Не пытайтесь натянуть их на Checkstyle через regex — false positive утопят сигнал.

`JS-CS-3` **`maxWarnings = 0` + `ignoreFailures = false`** — обязательно. Если хочется временно ослабить правило — добавь suppression в `config/checkstyle/checkstyle-suppressions.xml` с обязательным комментарием `<!-- justify: ... до: YYYY-MM-DD -->` (по аналогии с `R-SEC-SAST-4`).

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

`JS-CS-4` **Checkstyle привязан к `check`**, не к `checkSecurity` (`BS-SEC-2`). Это lint-уровень, не security — должен прогоняться на каждом локальном `./gradlew check` и в любом CI-job, где идут тесты:

```gradle
tasks.named('check') {
    dependsOn 'checkstyleMain', 'checkstyleTest'
}
```

`JS-CS-5` **Конфиг `config/checkstyle/checkstyle.xml`** базируется на Sun/Google checks, ослаблен под наши конвенции (например, `LineLength: max=120`, разрешён `_` в именах test-методов per `JS-2.6.1`). Полный шаблон — `config/checkstyle/checkstyle.xml.template`, поставляется через `ucp-bootstrap-design` при создании нового сервиса.

`JS-CS-X1` ❌ **`@SuppressWarnings("checkstyle:...")`** в коде без комментария-justify (≥ 30 символов). Можно только в крайних случаях с обоснованием — иначе подавляется глобально, на ревью не разглядишь.

`JS-CS-X2` ❌ **Удаление правил из `checkstyle.xml`** «потому что мешают». Если правило реально устарело — обсуждается командой, обновляется конфиг для всех сервисов сразу. Локальное удаление приводит к расхождению conventions между сервисами.

`JS-CS-X3` ❌ **Использование Checkstyle для семантических проверок** (regex-правила «все public-методы возвращают `Optional`», подсчёт строк в методе для cyclomatic complexity и т.п.). Это регрессия в сторону «ad-hoc регулярки в xml», которые никто не сможет читать через год. Семантика — `ucp-java-style-review` или отдельный AI-скилл.
