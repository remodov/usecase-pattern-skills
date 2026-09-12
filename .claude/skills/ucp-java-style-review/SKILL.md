---
name: ucp-java-style-review
description: Ревью Java-исходников по требованиям `java-style/*` — нейминг, импорты, выражения, форматирование. Узкий скилл: только стиль, без архитектуры и DDD.
when_to_use: Ревью PR, перед коммитом, онбординг модуля под командный стиль; изменённые .java в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*)
---

# Ревью Java-стиля

Ты ревьюишь Java-исходники на соответствие требованиям `java-style/*`. Этот скилл намеренно узкий — проверяет только **стиль** (нейминг, импорты, выражения, форматирование). Архитектура, инварианты DDD, соответствие Use Case Pattern и API-контракты — задача других скиллов.

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/java/java-style/spec.md` в корне проекта (полный текст с PREFER/AVOID-примерами — `backend/java/java-style/references/implementation.md`, открывай точечно по разделу). У каждого правила есть код (`java-style/package-and-type-naming`, `java-style/guard-clauses-preferred`, …) — цитируй коды в замечаниях. Гайд обязателен, кроме случаев, когда явно применимо `java-style/deviation-requires-justification` («любое нарушение допустимо, если оно улучшает читаемость»); в этом случае автор должен обосновать отклонение в описании PR.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - Используй `git diff` (working tree, staged, last commit), чтобы найти изменённые `.java`-файлы.
   - По умолчанию — только изменённые строки. О нарушениях в окружающем контексте сообщай как **Замечание** (чтобы автор знал, но не блокировался).

3. **Прогон по каждому разделу гайда:**

   - **§2 Именование (`java-style/package-and-type-naming`–`java-style/member-naming`):**
     - Имена пакетов lowercase, без `_` и спецсимволов (`java-style/package-and-type-naming`).
     - Имена пакетов в единственном числе (`java-style/package-and-type-naming`).
     - Имена классов — существительные (`java-style/package-and-type-naming`).
     - Имена интерфейсов — существительные / прилагательные на `-able`, не начинаются с `I` (`java-style/package-and-type-naming`).
     - Аббревиатуры: 2 буквы — все CAPS, 3+ — только первая (`java-style/abbreviation-casing`).
     - Имена методов — глаголы / описание действия; getters начинаются с `get` (`java-style/member-naming`).
     - Имена тестов: длинные говорящие либо короткие + `@DisplayName`; не `snake_case` (`java-style/test-method-naming`).
     - Переменные — `camelCase` с lowercase first (`java-style/member-naming`).
     - Константы — `UPPER_SNAKE_CASE` + обязательно `static final` (`java-style/member-naming`).

   - **§3 Импорты:**
     - Без wildcard, кроме `java.util.*` (`java-style/imports-are-explicit`).
     - Без неиспользуемых (`java-style/imports-are-explicit`).

   - **§4 Выражения:**
     - Булева сложность ≤ 3 операторов `&&`/`||` (`java-style/expressions-stay-simple`).
     - Java-стиль объявления массивов: `int[] x`, не `int x[]` (`java-style/expressions-stay-simple`).
     - Порядок модификаторов: `public/protected/private` → `static` → `final` → `transient` → `volatile` → `synchronized` (`java-style/expressions-stay-simple`).
     - Без неявных модификаторов: в interface-методах нет `public`/`abstract`, во вложенных enum/interface нет `static` (`java-style/expressions-stay-simple`).
     - Method reference вместо лямбды, если возможно (`java-style/lambdas-stay-short`).
     - Большие лямбды — в named methods (`java-style/lambdas-stay-short`).
     - Guard expressions вместо вложенных условий (`java-style/guard-clauses-preferred`).

   - **§5 Отступы:**
     - Длина строки ≤ 120 символов (`java-style/formatting-rules`).
     - Корректный перенос длинных выражений (`java-style/formatting-rules`).
     - Нет горизонтального выравнивания переменных (`java-style/formatting-rules`).

4. **Не дублируй то, что ловит checkstyle.** Если в проекте есть `checkstyle.xml` — упомяни в начале отчёта, что часть правил автоматически проверяется им, и сосредоточься на правилах, которые требуют человеческого судьи (`java-style/abbreviation-casing` аббревиатуры, `java-style/test-method-naming` имена тестов, `java-style/lambdas-stay-short` большие лямбды, `java-style/guard-clauses-preferred` guard expressions, `java-style/formatting-rules` перенос).

5. **Формат finding, локализация, серьёзность, резюме, запрет правок** — см. `.claude/docs/shared/review-format/spec.md` (правила `review-format/*`). Перед каждым finding обязательна Read-проверка строки (`review-format/*`), поле `Строка` в формате обязательно (`review-format/finding-carries-line-and-rule`).

6. **Доменные ориентиры для серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — имя класса как глагол, аббревиатура наперекосяк, гигантская лямбда без декомпозиции, булева сложность ≥ 5, длина строки ≥ 200.
   - **Предупреждение** — неявные модификаторы, множественное число в имени пакета, неиспользуемые импорты, отсутствие method reference, горизонтальное выравнивание.
   - **Замечание** — можно сделать чуть выразительнее, длина строки 121–140 символов и т. п.

$ARGUMENTS
