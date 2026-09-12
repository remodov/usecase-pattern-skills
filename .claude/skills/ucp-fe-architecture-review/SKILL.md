---
name: ucp-fe-architecture-review
lang: any
track: frontend
description: Ревью архитектуры фронта из шаблона frontend-templates по openspec-требованиям области architecture — слои FSD и направление импорта, MVVM внутри слайса, ссылочное состояние в адресе, размещение use client.
when_to_use: Изменения в src/_pages, src/features, src/entities, src/widgets, app/** или файлах роутов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(bun*)
---

# Ревью архитектуры фронта

## Откуда берутся правила

**`openspec/specs/architecture/spec.md`** проекта — источник правды. В каждой
находке цитируй requirement ID. Сводная таблица инвариантов — `AGENTS.md`
(собирается `bun run spec:sync`, руками не правится).

**Читай поле «Гейт» каждого требования.** Оно говорит, ловит нарушение машина
или человек. Требование с гейтом «нет» не поймает никто, кроме тебя — смотри
такие внимательнее прочих. Поле «Не ловит» прямо называет, что проскакивает
мимо гейта: это готовый список того, что нужно проверить глазами.

**Проверь, что гейты включены.** Требование обещает механизм — убедись, что он
есть в проекте: `bun run lint:arch` (steiger) и зоны `import/no-restricted-paths` в `eslint.config.mjs`. Обещанный, но не включённый гейт — **отдельная
находка**, и она важнее единичного нарушения.

Если `openspec/specs` в проекте нет — скажи прямо: требований не объявлено,
ревьюить не против чего. Предложи завести по образцу `next-ssr`, и дальше
выдавай находки как мнение, а не как нарушения.

## Что смотреть

- **Слои и направление импорта** (`architecture/fsd-layer-direction`): `shared → entities → features → widgets → _pages → app`, только вниз. Общий код двух фич опускается слоем ниже, а не импортируется вбок. Требование само предупреждает: кросс-фичевый импорт **из теста** не ловит ничто — проверь тесты руками.
- **Чужой слайс — через `index.ts`** (`architecture/slice-public-api-only`), сущности не знают о фичах (`architecture/entities-know-nothing-about-features`).
- **MVVM внутри слайса** (`architecture/mvvm-model-view-split`): ветвление дискриминированным объединением в `model/`-хуке, `ui/` — чистый рендер. Гейта нет.
- **Роут — тонкий реэкспорт слайса** (`architecture/thin-route-reexport`), слой страниц называется `_pages` (`architecture/pages-layer-underscore`), слоя `app` внутри `src/` нет.
- **Слайс страницы — композиция и доступ** (`architecture/page-slice-guard`), состав слайса задан скелетом (`architecture/slice-skeletons-by-screen-type`), файлов `utils.ts` не бывает (`architecture/no-utils-files`).
- **Ссылочное состояние живёт в адресе** (`architecture/linkable-state-in-url`), чтение адреса обёрнуто в Suspense (`architecture/suspense-around-searchparams`).
- **`'use client'`** — файлам с хуками и обработчиками, чистому View нет (`architecture/use-client-placement`).
- **Данные тянутся клиентскими хуками** (`architecture/client-side-data-fetching`): кука сессии в серверный запрос не едет.

## Формат вывода

Находка: `<requirement-id>` — что не так, файл и строка, почему это ломается,
как надо. Сгруппируй: критично (ломает прод или контракт) / важно / замечание.
В конце — список требований с гейтом «нет», которые ты проверил глазами.

$ARGUMENTS
