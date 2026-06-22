# Node Style — индекс правил (Node/TypeScript)

> **Что это.** Сжатый индекс правил Node/TypeScript-стиля: код + формулировка, по разделам. Рабочий вход
> скиллов — review цитирует код в findings. Языко-специфичный concern (аналог Java `java-style` / `JS-*`,
> Python `python-style` / `PY-*`) — **только Node**, префикс `NODE-*`. Код-примеры включены (отдельного
> style-guide нет). Стек: TypeScript strict, ESLint (typescript-eslint) + Prettier, ESM/NodeNext.
> Коды: `NODE-<N>` — обязательно (MUST), `NODE-X<N>` — антипаттерн (запрещено). То, что ловят
> tsc/eslint/prettier механически, в findings не дублируем — фокус на семантике.

Базовый принцип (`NODE-1`): **любое нарушение допустимо, если улучшает читаемость** — ревьюер обязан явно
объяснить, чем нарушение лучше. Цель — читаемость и качество, не формальная проверка.

## 1. Инструменты — обязательны в CI
**MUST:**
- **NODE-2.** `tsconfig.json`: `"strict": true` + `"noUncheckedIndexedAccess": true`; `module`/`moduleResolution` — `NodeNext` (ESM). Ослабление — только точечно с обоснованием.
- **NODE-3.** ESLint с `typescript-eslint` (type-checked пресет `strictTypeChecked`) + Prettier; единый конфиг на сервис (`eslint.config.mjs`), не разрозненные override'ы.
- **NODE-4.** `tsc --noEmit` + `eslint .` + `prettier --check .` на каждом CI-прогоне; fail при нарушении. `// eslint-disable` / `@ts-expect-error` — только с кодом правила и justify.
- **NODE-5.** ESLint/Prettier покрывают механику (нейминг, импорты, формат); семантику разделов 4–7 — `ucp-node-style-review`.

**MUST NOT:**
- **NODE-X1.** `@ts-ignore` — глушит без проверки; только `@ts-expect-error` с описанием (упадёт сам, когда ошибка исчезнет).
- **NODE-X2.** Отключение правил «потому что мешают» без обсуждения — расхождение conventions между сервисами.

## 2. Именование
**MUST:**
- **NODE-6.** Файлы и директории — `kebab-case`; Nest-суффиксы через точку: `create-order.handler.ts`, `.module.ts`, `.controller.ts`, `.service.ts`, `.spec.ts`.
- **NODE-7.** Классы, интерфейсы, типы, decorators-фабрики — `PascalCase`; интерфейсы без префикса `I`.
- **NODE-8.** Функции, методы, переменные, свойства — `camelCase`; функции/методы — глагол/действие (`createOrder`, не `order`).
- **NODE-9.** Константы уровня модуля и DI-токены — `UPPER_SNAKE_CASE`; локальные `const` — обычный `camelCase`.
- **NODE-10.** Имена тестов — говорящие: `it('rejects order when balance is insufficient')`, не `it('test1')` (cross-ref `NODETEST-16`).

## 3. Импорты и модули
**MUST:**
- **NODE-11.** Только named exports; `export default` для сервисов/классов/функций запрещён — ломает rename-рефакторинг и автоимпорт (исключение — конфиг-файлы, где формат требует default).
- **NODE-12.** Порядок импортов: node builtins (с префиксом `node:`) → third-party → path-aliases → relative; сортирует ESLint (`import/order` / `simple-import-sort`), руками не поддерживать.
- **NODE-13.** Path-aliases (`@app/*` через `paths` в tsconfig) вместо глубоких relative (`../../../core/...`).
- **NODE-14.** `import type { X }` для type-only импортов (`verbatimModuleSyntax`); без неиспользуемых импортов.

**MUST NOT:**
- **NODE-X3.** Барель-файлы (`index.ts`, реэкспортирующий весь пакет) ради «короткого импорта» — циклические зависимости и медленный tsc.
- **NODE-X4.** `require(...)` / `module.exports` (CommonJS) в новом коде — только ESM `import`/`export`.

## 4. Выражения и типизация
**MUST:**
- **NODE-15.** Граничные/неизвестные данные — `unknown` + narrowing (type guard, схема-валидатор), не `any`.
- **NODE-16.** Возвращаемый тип публичных функций/методов аннотирован явно — фиксирует контракт, ловит случайное расширение типа.
- **NODE-17.** Guard clause (ранний `throw`/`return`) вместо вложенных `if/else`.
- **NODE-18.** Деньги — `bigint` (минорные единицы) или Decimal-библиотека, не `number`; время — UTC (cross-ref `PG-T-011/030`).
- **NODE-19.** Сложность булева выражения — не более 3 операторов `&&`/`||`; сложнее — именованный предикат.

**MUST NOT:**
- **NODE-X5.** `any` (явный или через `as any`) — отравляет типизацию всего downstream-кода; `unknown` + narrowing.
- **NODE-X6.** Non-null assertion (`x!`) — скрывает реальный nullability; narrowing / `??` / guard, либо честный `| undefined` в типе.
- **NODE-X7.** Каскад `as`-кастов для «подгонки» типов — чинить модель типов, не глушить компилятор.

## 5. Async
**MUST:**
- **NODE-20.** `async/await`, не raw `.then()/.catch()`-цепочки; параллелизм — `Promise.all`/`allSettled` по месту.
- **NODE-21.** Каждый Promise — awaited, returned или явно обработан; `no-floating-promises` и `no-misused-promises` включены как error.

**MUST NOT:**
- **NODE-X8.** `async`-функция без `await` внутри и `await` не-промисов — шум, скрывающий реальные точки ожидания.
- **NODE-X9.** Fire-and-forget (`void doStuff()`) без catch-канала — unhandled rejection валит процесс.

## 6. Иммутабельность
**MUST:**
- **NODE-22.** Поля, не меняющиеся после конструктора — `readonly`; DI-зависимости — `private readonly` в параметрах конструктора.
- **NODE-23.** `as const` для литеральных констант/конфиг-объектов; `readonly T[]` в публичных сигнатурах, где мутация не нужна.
- **NODE-24.** Новые объекты через spread/`structuredClone`, не мутация входных аргументов.

## 7. Запреты
**MUST NOT:**
- **NODE-X10.** `var` — только `const` (по умолчанию) и `let` (когда реально переприсваивается).
- **NODE-X11.** `==`/`!=` — только `===`/`!==`; допустимое исключение — `== null` для одновременной проверки null/undefined при включённом eslint-правиле.
- **NODE-X12.** `enum` для простых closed-наборов — string literal union (`type Status = 'new' | 'paid'`) + `as const`-объект, если нужна итерация; `enum` — только осознанно, где требует интеграция (Swagger).
- **NODE-X13.** `namespace` — реликт pre-ESM; модуль = файл.
- **NODE-X14.** Комментарии в коде — ни `//`, ни `/* */`, ни JSDoc; неочевидный WHY выражается именем, структурой или спекой (как `JS-7.*` / `PY-7.*`).
