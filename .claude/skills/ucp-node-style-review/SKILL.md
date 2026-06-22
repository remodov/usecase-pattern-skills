---
name: ucp-node-style-review
lang: node
description: Ревью TypeScript-исходников по UCP Node Style Guide (коды NODE-*) — нейминг, ESM-импорты, async/await, типизация strict без any, иммутабельность, eslint+prettier+tsc. Узкий скилл: только стиль.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .ts в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Node-стиля (eslint / prettier / tsc strict)

Ты ревьюишь TypeScript-исходники на соответствие `backend/node/node-style/node-style-rules.md` (`NODE-*`). Скилл намеренно
узкий — только **стиль** (нейминг, импорты, выражения, типизация, async, иммутабельность, комментарии). Архитектура,
DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/node/node-style/node-style-rules.md`** — правила `NODE-*` (код-примеры включены).
- `shared/review-finding-format.md` (`RFF-*`). Связанные коды для cross-ref: `R-ERR-*` (обработка ошибок), `R-HEX-2` (порты), `NODETEST-16` (имена тестов), `PG-T-011/030` (деньги/время).

## Инструкции

1. **Прочти** `node-style-rules.md`. Цитируй конкретные коды (`NODE-15`, `NODE-X5`), не префикс. Гайд обязателен, кроме явного `NODE-1` (нарушение улучшает читаемость) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.ts`. По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**
   - **Инструменты (`NODE-2..5`):** `tsconfig` `"strict": true` + `"noUncheckedIndexedAccess"`, `NodeNext` (`NODE-2`); eslint `strictTypeChecked` + prettier, единый конфиг (`NODE-3`); `tsc --noEmit`+`eslint`+`prettier --check` в CI (`NODE-4`). `@ts-ignore` → `NODE-X1` (только `@ts-expect-error` с описанием). Отключение правил без обсуждения → `NODE-X2`.
   - **Именование (`NODE-6..10`):** файлы `kebab-case` с Nest-суффиксами через точку (`NODE-6`); классы/типы `PascalCase`, интерфейсы без `I` (`NODE-7`); функции/переменные `camelCase`, функции-глаголы (`NODE-8`); константы модуля/DI-токены `UPPER_SNAKE_CASE` (`NODE-9`); имена тестов говорящие (`NODE-10`, cross-ref `NODETEST-16`).
   - **Импорты (`NODE-11..14`):** только named exports (`export default` → `NODE-11`); порядок builtins(`node:`)→third-party→aliases→relative через ESLint (`NODE-12`); path-aliases вместо глубоких relative (`NODE-13`); `import type` для type-only (`NODE-14`). Барель-`index.ts` → `NODE-X3`. `require`/`module.exports` в новом коде → `NODE-X4`.
   - **Выражения и типизация (`NODE-15..19`):** граничные данные `unknown` + narrowing (`NODE-15`); возвращаемый тип публичных функций явный (`NODE-16`); guard clause (`NODE-17`); деньги `bigint`/Decimal не `number`, время UTC (`NODE-18`); булева сложность ≤3 (`NODE-19`). `any`/`as any` → `NODE-X5`. Non-null assertion `x!` → `NODE-X6`. Каскад `as`-кастов → `NODE-X7`.
   - **Async (`NODE-20..21`):** `async/await`, не `.then()`-цепочки, параллелизм `Promise.all` (`NODE-20`); каждый Promise awaited/returned/обработан, `no-floating-promises` как error (`NODE-21`). `async` без `await`/`await` не-промисов → `NODE-X8`. Fire-and-forget `void doStuff()` без catch-канала → `NODE-X9`.
   - **Иммутабельность (`NODE-22..24`):** `readonly`-поля, DI — `private readonly` в конструкторе (`NODE-22`); `as const`/`readonly T[]` (`NODE-23`); spread/`structuredClone` вместо мутации аргументов (`NODE-24`).
   - **Запреты:** `var` → `NODE-X10`; `==`/`!=` → `NODE-X11`; `enum` для простых наборов вместо string literal union → `NODE-X12`; `namespace` → `NODE-X13`; комментарии в коде (`//`, `/* */`, JSDoc) → `NODE-X14`.

4. **Не дублируй eslint/tsc/prettier.** Если в проекте есть strict-конфиг и eslint — упомяни в начале отчёта, что механика (нейминг, импорты, формат) ловится ими, и сосредоточься на семантике, требующей человеческого судьи: `any`-escape (`NODE-X5`), non-null assertions (`NODE-X6`), fire-and-forget (`NODE-X9`), комментарии (`NODE-X14`), читаемость guard clause/предикатов.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `any`/`as any` (`NODE-X5`), `@ts-ignore` (`NODE-X1`), fire-and-forget без catch-канала (`NODE-X9`), деньги `number` (`NODE-18`), комментарии в коде (`NODE-X14`).
   - **Предупреждение** — non-null assertion (`NODE-X6`), каскад `as` (`NODE-X7`), `export default` (`NODE-11`), `require`/CommonJS (`NODE-X4`), `==` (`NODE-X11`), `var` (`NODE-X10`), `enum` вместо union (`NODE-X12`), отключение правил без justify (`NODE-X2`).
   - **Замечание** — барель-файлы (`NODE-X3`), глубокие relative-импорты (`NODE-13`), нет явного возвращаемого типа (`NODE-16`), неговорящее имя теста (`NODE-10`), булева сложность >3 (`NODE-19`).

## Что не входит

- Архитектура/слои — `ucp-node-pattern-review`. DDD-инварианты — `ucp-node-ddd-tactical-review`. Валидация входа — `ucp-node-validation-review`.
- Обработка ошибок (иерархия/filters) — `ucp-node-error-handling-review`. Persistence — `ucp-node-typeorm-review`.

$ARGUMENTS
