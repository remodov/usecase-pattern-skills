---
name: ucp-java-style-review
description: Review Java source files for compliance with the team's Java Style Guide (naming, imports, expressions, indentation). Use when reviewing PRs, before committing, or when onboarding a new module to the team's style.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*) Agent
---

# Java Style Review

You are reviewing Java source files for compliance with the team's Java Style Guide. This skill is intentionally narrow — it only checks **style** (naming, imports, expressions, formatting). Architecture, DDD invariants, UseCase Pattern compliance, and API contracts are covered by other skills.

## Instructions

1. **Read the style guide** from `.claude/docs/java-style-guide.md` in the project root. Every rule has a code (`JS-2.1`, `JS-4.7`, …) — cite codes in findings. Treat the guide as binding except where `JS-1.1` («любое нарушение допустимо, если оно улучшает читаемость») is explicitly applicable; in that case the contributor must justify the deviation in the PR description.

2. **Identify what to review.** If the user named files — review those. Otherwise:
   - Use `git diff` (working tree, staged, last commit) to find changed `.java` files.
   - Default scope: only changed lines. Mention untouched violations in surrounding context as Info findings (so the contributor knows about them but isn't blocked).

3. **Review against every section of the guide:**

   - **§2 Именование (`JS-2.1`–`JS-2.8`):**
     - Имена пакетов lowercase, без `_` и спецсимволов (`JS-2.1`).
     - Имена пакетов в единственном числе (`JS-2.2`).
     - Имена классов — существительные (`JS-2.3`).
     - Имена интерфейсов — существительные / прилагательные на `-able`, не начинаются с `I` (`JS-2.4`).
     - Аббревиатуры: 2 буквы — все CAPS, 3+ — только первая (`JS-2.5`).
     - Имена методов — глаголы / описание действия; getters начинаются с `get` (`JS-2.6`).
     - Имена тестов: длинные говорящие либо короткие + `@DisplayName`; не `snake_case` (`JS-2.6.1`).
     - Переменные — `camelCase` с lowercase first (`JS-2.7`).
     - Константы — `UPPER_SNAKE_CASE` + обязательно `static final` (`JS-2.8`).

   - **§3 Импорты:**
     - Без wildcard, кроме `java.util.*` (`JS-3.1`).
     - Без неиспользуемых (`JS-3.2`).

   - **§4 Выражения:**
     - Булева сложность ≤ 3 операторов `&&`/`||` (`JS-4.1`).
     - Java-стиль объявления массивов: `int[] x`, не `int x[]` (`JS-4.2`).
     - Порядок модификаторов: `public/protected/private` → `static` → `final` → `transient` → `volatile` → `synchronized` (`JS-4.3`).
     - Без неявных модификаторов: в interface-методах нет `public`/`abstract`, во вложенных enum/interface нет `static` (`JS-4.4`).
     - Method reference вместо лямбды, если возможно (`JS-4.5`).
     - Большие лямбды — в named methods (`JS-4.6`).
     - Guard expressions вместо вложенных условий (`JS-4.7`).

   - **§5 Отступы:**
     - Длина строки ≤ 120 символов (`JS-5.1`).
     - Корректный перенос длинных выражений (`JS-5.2`).
     - Нет горизонтального выравнивания переменных (`JS-5.3`).

4. **Не дублируй то, что ловит checkstyle.** Если в проекте есть `checkstyle.xml` — упомяни в начале отчёта, что часть правил автоматически проверяется им, и сосредоточься на правилах, которые требуют человеческого судьи (`JS-2.5` аббревиатуры, `JS-2.6.1` имена тестов, `JS-4.6` большие лямбды, `JS-4.7` guard expressions, `JS-5.2` перенос).

5. **Report findings** in this exact format:

   ```
   <FilePath>:<LineNumber>  [<RuleCode>]  <Severity>
     Problem: <one-line description>
     Why: <which rule, quoting briefly>
     Fix: <concrete suggestion, ideally a code snippet>
   ```

   Severities:
   - **Critical** — нарушение, ломающее читаемость/поддерживаемость в моменте: имя класса как глагол, аббревиатура наперекосяк, гигантская лямбда без декомпозиции, булева сложность ≥ 5, длина строки ≥ 200.
   - **Warning** — дисциплинарные: неявные модификаторы, плюрал в имени пакета, неиспользуемые импорты, отсутствие method reference, горизонтальное выравнивание.
   - **Info** — мелкие или предложения: можно сделать чуть выразительнее, длина строки 121–140 символов, и т. п.

6. **End with a summary**: количество findings по severity + одно-строчный вердикт — «compliant», «minor deviations», «needs rework».

7. **Do not modify code.** Этот скилл только репортит. Авто-фикс — задача отдельного `java-style-fix` (если/когда появится).

$ARGUMENTS
