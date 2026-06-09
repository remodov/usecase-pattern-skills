# Frontend-трек — карта и «что куда добавлять»

Каркас специализации **`track: frontend`** (стек: **React + TypeScript**). Backend-паттерны (UseCase/aggregate/
CQRS) сюда **не тянем** — у фронта свой набор concern'ов (см. `_meta/authoring-contract.md` §10). Кросс-трековое
(spec/arch/meta) приходит из `track: any` — не дублировать.

> **Статус: КАРКАС.** Раскладка, гейты и шаблон вертикали готовы и работают. **Содержимое concern'ов наполняет
> FE-лид** — текущие `*-rules.md` это скелеты с принципами-заглушками и `[TODO]`. Эталон формы — `fe-component/`
> (наполнен полнее) + пара скиллов `ucp-fe-component-{design,review}`.

## Раскладка (стек один → плоско, без `<lang>/`)

Frontend — single-stack (React+TS), поэтому concern'ы — **плоская single-file форма** (rules-index с
код-примерами внутри, без отдельного style-guide; §2 / §11 контракта это разрешает):

```
docs/frontend/
├── _index.md                         # этот файл
└── <concern>/<concern>-rules.md      # коды FE-* + интент + примеры на React/TS
.claude/skills/
└── ucp-fe-<concern>-{design,review}/ # пара скиллов, frontmatter track: frontend
```

## Карта concern'ов (что куда)

| Concern | Префикс | Про что | Статус |
|---|---|---|---|
| `fe-component` | `FE-CMP-*` | компоненты: презентационные vs контейнеры, типизация props, композиция, мемоизация | эталон (наполнен) |
| `fe-state` | `FE-ST-*` | состояние: local vs server-state, выбор стора, не держать server-data в глобальном сторе | [TODO] |
| `fe-data-fetching` | `FE-DATA-*` | запросы к API: react-query/SWR, кеш, loading/error, отмена; не `fetch` в компоненте | [TODO] |
| `fe-forms` | `FE-FORM-*` | формы: react-hook-form, схемная валидация (zod), submit/ошибки | [TODO] |
| `fe-routing` | `FE-RT-*` | роутинг, code-splitting, guard'ы по auth | [TODO] |
| `fe-styling` | `FE-STY-*` | дизайн-система, токены, CSS-подход, отказ от inline-магии | [TODO] |
| `fe-a11y` | `FE-A11Y-*` | семантика, ARIA, фокус, контраст, клавиатура (web.dev) | [TODO] |
| `fe-test` | `FE-TEST-*` | Vitest + Testing Library (юзер-центрично), MSW для API-моков | [TODO] |
| `fe-style` | `FE-STYLE-*` | eslint/prettier/tsconfig strict (langspecific-аналог `python-style`) | [TODO] |

(E2E — **отдельный трек** `track: e2e` (Playwright), не под frontend: он дёргает контракты и backend, и фронта.)

## Как FE-лид добавляет concern (по `authoring-contract.md` §8)

1. Зарезервировать префикс `FE-<X>-*` в `_meta/rule-code-registry.md` (уже намечены в карте выше).
2. Наполнить `docs/frontend/<concern>/<concern>-rules.md`: разделы `## N.`, `**MUST:**`/`**MUST NOT:**`,
   буллеты `- **FE-<X>-<N>.** формулировка` (`-X<N>` — антипаттерн). Код-примеры на React/TS — внутри.
3. Создать пару `ucp-fe-<concern>-{design,review}` с frontmatter `track: frontend`, `lang: any` (стек один) —
   по образцу `ucp-fe-component-*`. SKILL.md — текст по-русски, идентификаторы латиницей.
4. **Прогнать гейты:** скилл `ucp-meta-review` + `python3 .claude/docs/_meta/check-shared-neutral.py`
   (для single-stack frontend D мягок — биндинг и есть реализация; но meta-review проверит форму/пары/нейминг).
5. CODEOWNERS: `docs/frontend/**` + `ucp-fe-*` → FE-лид.

## Установка фронт-среза

```
UCP_TRACK=frontend ./install.sh ~/my-frontend     # только fe-* + кросс-трековое (spec/arch/meta)
UCP_TRACK=backend,frontend UCP_LANG=python ./install.sh ~/monorepo   # моно-репо: и бэк, и фронт
```
