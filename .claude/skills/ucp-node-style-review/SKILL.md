---
name: ucp-node-style-review
lang: node
description: Ревью TypeScript-исходников по требованиям `node-style/*` — нейминг, ESM-импорты, async/await, типизация strict без any, иммутабельность, eslint+prettier+tsc. Узкий скилл: только стиль.
when_to_use: Ревью PR, перед коммитом, онбординг модуля; изменённые .ts в git diff.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Node-стиля (eslint / prettier / tsc strict)

Ты ревьюишь TypeScript-исходники на соответствие `backend/node/node-style/spec.md` (`NODE-*`). Скилл намеренно
узкий — только **стиль** (нейминг, импорты, выражения, типизация, async, иммутабельность, комментарии). Архитектура,
DDD-инварианты, Use Case Pattern, валидация — другие скиллы.

## Зависимости

- **`.claude/docs/backend/node/node-style/spec.md`** — правила `NODE-*` (код-примеры включены).
- `shared/review-format/spec.md` (`review-format/*`). Связанные коды для cross-ref: `R-ERR-*` (обработка ошибок), `hexagonal/core-free-of-framework` (порты), `node-test-strategy/test-name-states-scenario` (имена тестов), `PG-T-011/030` (деньги/время).

## Инструкции

1. **Прочти** `node-style/spec.md`. Цитируй конкретные коды (`node-style/unknown-not-any`, `node-style/unknown-not-any`), не префикс. Гайд обязателен, кроме явного `node-style/deviation-requires-justification` (нарушение улучшает читаемость) — тогда автор обосновывает в PR.

2. **Скоп.** Если пользователь назвал файлы — бери их. Иначе `git diff` (working tree/staged/last commit) на `.ts`. По умолчанию — изменённые строки; нарушения в окружении — как **Замечание**.

3. **Прогон.**
   - **Инструменты (`NODE-2..5`):** `tsconfig` `"strict": true` + `"noUncheckedIndexedAccess"`, `NodeNext` (`node-style/strict-compiler-settings`); eslint `strictTypeChecked` + prettier, единый конфиг (`node-style/lint-and-format-enforced`); `tsc --noEmit`+`eslint`+`prettier --check` в CI (`node-style/lint-and-format-enforced`). `@ts-ignore` → `node-style/suppressions-are-justified` (только `@ts-expect-error` с описанием). Отключение правил без обсуждения → `node-style/suppressions-are-justified`.
   - **Именование (`NODE-6..10`):** файлы `kebab-case` с Nest-суффиксами через точку (`node-style/naming-conventions`); классы/типы `PascalCase`, интерфейсы без `I` (`node-style/naming-conventions`); функции/переменные `camelCase`, функции-глаголы (`node-style/naming-conventions`); константы модуля/DI-токены `UPPER_SNAKE_CASE` (`node-style/naming-conventions`); имена тестов говорящие (`node-style/test-naming`, cross-ref `node-test-strategy/test-name-states-scenario`).
   - **Импорты (`NODE-11..14`):** только named exports (`export default` → `node-style/named-exports-only`); порядок builtins(`node:`)→third-party→aliases→relative через ESLint (`node-style/imports-are-ordered-and-explicit`); path-aliases вместо глубоких relative (`node-style/imports-are-ordered-and-explicit`); `import type` для type-only (`node-style/imports-are-ordered-and-explicit`). Барель-`index.ts` → `node-style/imports-are-ordered-and-explicit`. `require`/`module.exports` в новом коде → `node-style/imports-are-ordered-and-explicit`.
   - **Выражения и типизация (`NODE-15..19`):** граничные данные `unknown` + narrowing (`node-style/unknown-not-any`); возвращаемый тип публичных функций явный (`node-style/explicit-return-types`); guard clause (`node-style/simple-control-flow`); деньги `bigint`/Decimal не `number`, время UTC (`node-style/precise-money-and-time`); булева сложность ≤3 (`node-style/simple-control-flow`). `any`/`as any` → `node-style/unknown-not-any`. Non-null assertion `x!` → `node-style/unknown-not-any`. Каскад `as`-кастов → `node-style/unknown-not-any`.
   - **Async (`NODE-20..21`):** `async/await`, не `.then()`-цепочки, параллелизм `Promise.all` (`node-style/async-await-not-chains`); каждый Promise awaited/returned/обработан, `no-floating-promises` как error (`node-style/no-floating-promises`). `async` без `await`/`await` не-промисов → `node-style/async-await-not-chains`. Fire-and-forget `void doStuff()` без catch-канала → `node-style/no-floating-promises`.
   - **Иммутабельность (`NODE-22..24`):** `readonly`-поля, DI — `private readonly` в конструкторе (`node-style/immutability-in-types`); `as const`/`readonly T[]` (`node-style/immutability-in-types`); spread/`structuredClone` вместо мутации аргументов (`node-style/immutability-in-types`).
   - **Запреты:** `var` → `node-style/no-legacy-constructs`; `==`/`!=` → `node-style/no-legacy-constructs`; `enum` для простых наборов вместо string literal union → `node-style/no-legacy-constructs`; `namespace` → `node-style/no-legacy-constructs`; комментарии в коде (`//`, `/* */`, JSDoc) → `node-style/no-comments-in-code`.

4. **Не дублируй eslint/tsc/prettier.** Если в проекте есть strict-конфиг и eslint — упомяни в начале отчёта, что механика (нейминг, импорты, формат) ловится ими, и сосредоточься на семантике, требующей человеческого судьи: `any`-escape (`node-style/unknown-not-any`), non-null assertions (`node-style/unknown-not-any`), fire-and-forget (`node-style/no-floating-promises`), комментарии (`node-style/no-comments-in-code`), читаемость guard clause/предикатов.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `any`/`as any` (`node-style/unknown-not-any`), `@ts-ignore` (`node-style/suppressions-are-justified`), fire-and-forget без catch-канала (`node-style/no-floating-promises`), деньги `number` (`node-style/precise-money-and-time`), комментарии в коде (`node-style/no-comments-in-code`).
   - **Предупреждение** — non-null assertion (`node-style/unknown-not-any`), каскад `as` (`node-style/unknown-not-any`), `export default` (`node-style/named-exports-only`), `require`/CommonJS (`node-style/imports-are-ordered-and-explicit`), `==` (`node-style/no-legacy-constructs`), `var` (`node-style/no-legacy-constructs`), `enum` вместо union (`node-style/no-legacy-constructs`), отключение правил без justify (`node-style/suppressions-are-justified`).
   - **Замечание** — барель-файлы (`node-style/imports-are-ordered-and-explicit`), глубокие relative-импорты (`node-style/imports-are-ordered-and-explicit`), нет явного возвращаемого типа (`node-style/explicit-return-types`), неговорящее имя теста (`node-style/test-naming`), булева сложность >3 (`node-style/simple-control-flow`).

## Что не входит

- Архитектура/слои — `ucp-node-pattern-review`. DDD-инварианты — `ucp-node-ddd-tactical-review`. Валидация входа — `ucp-node-validation-review`.
- Обработка ошибок (иерархия/filters) — `ucp-node-error-handling-review`. Persistence — `ucp-node-typeorm-review`.

$ARGUMENTS
