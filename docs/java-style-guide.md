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
