# Java Style Guide — индекс правил

> **Что это.** Сжатый индекс правил `java-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами кода, PREFER/AVOID-сниппетами и обоснованием — `java-style-guide.md`**; открывай её точечно
> по нужному разделу, когда индекса не хватает.
> Коды: `JS-<раздел>.<N>` — рекомендация, `JS-<раздел>.X<N>` — антипаттерн (запрещено), `JS-CS-*` — enforcement через Checkstyle.

Базовый принцип (`JS-1.1`): **любое нарушение допустимо, если оно улучшает читаемость** — от ревьюера ожидается явное объяснение, чем нарушение лучше. Цель — читаемость и качество, не формальная проверка.

## 1. Общие рекомендации
**MUST:**
- **JS-1.1.** Любое нарушение допустимо, если улучшает читаемость; ревьюер обязан явно объяснить, чем именно нарушение лучше. Не индульгенция «писать как хочется».

## 2. Именование
**MUST:**
- **JS-2.1.** Имена пакетов — нижний регистр, без подчёркиваний и спецсимволов.
- **JS-2.2.** Множественное число в пакетах запрещено — следуем стандартному API (`java.util`, не `java.utils`).
- **JS-2.3.** Имена классов — существительные (не глагольные формы).
- **JS-2.4.** Имена интерфейсов — существительные или прилагательные на `-able`; не начинать с `I`.
- **JS-2.5.** Аббревиатуры: избегать; 2-буквенная — в UPPER (`IOStream`), 3+-буквенная — только первая заглавная (`XmlParser`); подряд нескольких заглавных нет.
- **JS-2.6.** Имена методов — глаголы / описание действия (`getName`, не `name`).
- **JS-2.6.1.** Имена тестов отражают суть кейса: длинное говорящее camelCase-имя либо короткое + `@DisplayName`; не snake_case, не сверхдлинное без `@DisplayName`.
- **JS-2.7.** Имена переменных — camelCase, с lowercase.
- **JS-2.8.** Имена констант — `UPPER_SNAKE_CASE`, обязательно `static final`.

## 3. Импорты
**MUST:**
- **JS-3.1.** Без wildcard-импортов; исключение — `java.util.*`.
- **JS-3.2.** Не оставлять неиспользуемых импортов.

## 4. Выражения
**MUST:**
- **JS-4.1.** Сложность булева выражения — не более 3 операторов `&&`/`||`.
- **JS-4.2.** Без C-стиля объявления массивов (`int[] nums`, не `String strs[]`).
- **JS-4.3.** Порядок модификаторов: `public → protected → private → static → final → transient → volatile → synchronized`.
- **JS-4.4.** Не указывать неявные модификаторы (`public`/`abstract` в методах интерфейса, `static` во вложенных enum/interface).
- **JS-4.5.** Method reference вместо лямбды, где имеет смысл.
- **JS-4.6.** Большие лямбды (логика > одного выражения) выносить в named method + method reference.
- **JS-4.7.** Guard expression (ранний `throw`/`return`) вместо вложенных `if/else`.

## 5. Отступы и форматирование
**MUST:**
- **JS-5.1.** Длина строки — не более 120 символов (с отступами).
- **JS-5.2.** Перенос длинных выражений: после запятой, перед оператором, с выравниванием новой строки по началу выражения.
- **JS-5.3.** Без горизонтального выравнивания переменных — тратит время в diff.

## 6. Lombok
**MUST:**
- **JS-6.1.** Любой класс с `private final`-полями, инициализируемыми конструктором — `@RequiredArgsConstructor` (не только Spring-бины). Явный ctor — только при валидации аргументов, нестандартном `super(...)`, factory-методе или no-arg ctor для frameworks. Перекрывает `R-HND-5`.
- **JS-6.2.** `@Slf4j` вместо ручного `LoggerFactory.getLogger(...)`.
- **JS-6.3.** `@Getter` на custom exceptions и не-record value-object'ах с payload-полями.
- **JS-6.4.** Lombok **не** на records — record уже даёт ctor/accessors/equals/hashCode/toString.
- **JS-6.6.** Build-настройка Lombok одинакова во всех модулях; `compileOnly` + `annotationProcessor`, не `implementation`; версия в `libs.versions.toml`.
- **JS-6.7.** `@Builder` — точечно (сложные DTO 5+ полей, опциональные значения), не на каждом POJO; запрещён на entity / aggregate root (построение через named-конструкторы).

**MUST NOT:**
- **JS-6.5.** `@Data` в production-коде — ломает иммутабельность (mutable setters) и equals/hashCode по всем полям. Нужен legacy-POJO — `@Getter @Setter` явно; иммутабельный DTO — record.
- **JS-6.X1.** Явный all-args конструктор там, где подошёл `@RequiredArgsConstructor` — boilerplate без причины.
- **JS-6.X2.** `@AllArgsConstructor` на DI-классах — генерит ctor для всех полей, включая non-final, ломает вызовы при добавлении поля. Для DI — `@RequiredArgsConstructor`.

## 7. Комментарии
**MUST:**
- **JS-7.1.** Комментариев в коде нет вообще — ни `//`, ни `/* … */`, ни Javadoc, ни в production, ни в test. Абсолютное правило, не «по умолчанию».
- **JS-7.2.** Неочевидный WHY выражается именем, структурой или спекой (`docs/spec/`) — не комментарием.
- **JS-7.3.** Не цитировать коды правил из спеки/гайдов в коде (`BR-C5`, `AUTH-15`, `R-LAY-3`, `TS-9`, `BS-17`) — дублирует source-of-truth, хрупко, шум. Коды — в commit messages / PR / гайд. То же для `remarks:` в Liquibase.
- **JS-7.4.** Не писать комментарии «что тут было», «removed because», «added for», «TODO до …» — источник изменений — `git blame`.
- **JS-7.5.** Javadoc не используем нигде, включая публичный API OSS-библиотек — гниёт быстрее кода, сам код = документация, сложный контракт → спека.

**MUST NOT:**
- **JS-7.X1.** Любой комментарий (`//`, `/* … */`, Javadoc) — нарушение `JS-7.1`.
- **JS-7.X2.** Конфигурация `javadoc`-task в build для production-сервиса; не публикуем `*-javadoc.jar`.

## 8. Современные фичи Java (Java 21+)
> Раздел применяется, только если проект собирается на Java 21+ (`VERSION_21`). На Java 17 — лишь records и sealed без record patterns.

**MUST:**
- **JS-8.1.** Switch expression на sealed-иерархии вместо if-else / instanceof-цепочек — компилятор гарантирует exhaustiveness.
- **JS-8.2.** Record patterns в `case` — деконструкция полей прямо в паттерне, без `.field()`-геттера; ненужное поле — `ignored`.
- **JS-8.3.** Record patterns в `instanceof` — также через деконструкцию, не binding + геттер.
- **JS-8.4.** Exhaustive switch без `default` для sealed-иерархий — `default` молча проглотит новый вариант. `default` оправдан только для open-иерархий (String/int/расширяемый enum).
- **JS-8.5.** Sealed interface + record-варианты для closed-набора альтернатив; обычный interface — для open-расширяемых иерархий.
- **JS-8.6.** `String.formatted()` вместо `String.format()` — читается слева-направо.
- **JS-8.7.** `private record` для in-class data carriers (3–5 полей, только в этом классе), без Lombok-обёрток и отдельного VO.

## 9. Enforcement через Checkstyle
**MUST:**
- **JS-CS-1.** Checkstyle обязателен на всех Java-сервисах; стандартный `checkstyle` plugin + командный конфиг `config/checkstyle/checkstyle.xml` в репо сервиса (не submodule, не зависимость).
- **JS-CS-2.** Checkstyle покрывает только механические правила: нейминг (`JS-2.*`), импорты (`JS-3.*`), отступы/whitespace (`JS-5.*`), имя тестов (`JS-2.6.1`). Семантику (`JS-6.*`/`JS-7.*`/`JS-8.*`) в Checkstyle не выносим — это `ucp-java-style-review`.
- **JS-CS-3.** `maxWarnings = 0` + `ignoreFailures = false`. Ослабление — только через suppression с `<!-- justify: ... до: YYYY-MM-DD -->`.
- **JS-CS-4.** Checkstyle привязан к `check` (не к `checkSecurity`); `checkstyleMain` + `checkstyleTest` на каждом `./gradlew check` и в CI.
- **JS-CS-5.** Конфиг базируется на Sun/Google checks, ослаблен под конвенции (`LineLength max=120`, `_` в test-методах); шаблон поставляется через `ucp-bootstrap-design`.

**MUST NOT:**
- **JS-CS-X1.** `@SuppressWarnings("checkstyle:...")` без комментария-justify (≥ 30 символов).
- **JS-CS-X2.** Удаление правил из `checkstyle.xml` «потому что мешают» — расхождение conventions между сервисами; устаревшее правило обсуждается командой и обновляется для всех сразу.
- **JS-CS-X3.** Использование Checkstyle для семантических проверок (regex «все public возвращают `Optional`», cyclomatic complexity) — нечитаемые ad-hoc регулярки; семантика → AI-скилл.
