---
name: ucp-fe-screen-design
lang: any
track: frontend
description: Спроектировать новый экран или раздел фронта по OpenAPI-контракту в проекте из шаблона frontend-templates — карта экрана до кода, слайсы FSD, MVVM внутри слайса, прохождение гейтов проекта.
when_to_use: Триггеры — «сделай экран по спеке», «новый раздел», «выведи список из API». Проект собран из шаблона next-ssr или vite-spa.
allowed-tools: Read Glob Grep Write Edit Bash(bun*) Bash(npm*) Bash(git diff*)
---

# Экран по контракту — проектирование

Ты строишь экран в проекте, приехавшем из `<репозиторий шаблонов фронтенда>`. Правила
этого проекта живут в нём самом, не в методологии.

## Откуда берутся правила

1. **`openspec/specs/**/spec.md`** — требования проекта. Адресуются `ID` вида
   `architecture/fsd-layer-direction`. Поле **Гейт** говорит, ловит нарушение
   машина или ревью; поле **Не ловит** — что проскочит.
2. **`AGENTS.md`** — сводная таблица инвариантов, собранная `bun run spec:sync`.
   Быстрый обзор: что вообще обязано быть верно.
3. **`.claude/skills/ui-from-openapi/`** (или `ui-from-figma` в статике) — если
   шаблон принёс свой процедурный скилл, **веди по нему**: он знает гейты этого
   шаблона, справочники со скелетами и рецепты. Твоя задача тогда — не
   пересказывать его, а следить за порядком и за тем, что ничего не пропущено.

Если `openspec/specs` в проекте нет — скажи об этом прямо, предложи завести по
образцу `next-ssr` и дальше работай по коду, помечая решения как мнение.

## Порядок

1. **Прочитай контракт.** Экран строится от `operationId` и схем, а не от
   макета: значения, которых нет в контракте, не выдумываются
   (`api/operationid-required`, `content/no-invented-values`).

2. **Карта экрана — до кода.** `design/screens/<screen>.map.md`: что за экран,
   какие операции, какие поля, какие состояния. Проверяется `bun run map:check`
   (`design-system/screen-map-required`). Черновой прогон — `--draft`.

3. **Реши раскладку по слоям.** `shared → entities → features → widgets →
   _pages → app`, импорт только вниз, чужой слайс — через `index.ts`
   (`architecture/fsd-layer-direction`, `architecture/slice-public-api-only`).
   Файл роута — тонкий реэкспорт слайса (`architecture/thin-route-reexport`).

4. **Раздели model и ui внутри слайса.** Ветвление и запросы — в хуке `model/`
   дискриминированным объединением; `ui/` — чистый рендер
   (`architecture/mvvm-model-view-split`). `'use client'` ставится файлам
   с хуками и обработчиками, чистому View — нет
   (`architecture/use-client-placement`).

5. **Данные — только сгенерированными хуками** (`api/network-via-generated-hooks`).
   Пагинация серверная, размер страницы объявлен один раз
   (`api/server-side-pagination`, `api/page-size-single-source`). Ссылочное
   состояние живёт в адресе, чтение адреса обёрнуто в Suspense
   (`architecture/linkable-state-in-url`, `architecture/suspense-around-searchparams`).

6. **Тексты — через `t()`** по схеме ключей словаря; кириллица в разметке
   запрещена линтером (`content/texts-only-via-t`, `content/dictionary-key-schema`).

7. **Права.** Кнопку, закрытую скоупом, мало выключить — 403 обрабатывается
   всегда (`auth/permissions-via-usecan`, `auth/always-handle-403`).
   Подробнее — `ucp-fe-auth-design`.

8. **Прогони гейты проекта** и не сдавай красным (`tooling/gate-discipline`):
   `bun run lint`, `lint:arch`, `typecheck`, `map:check`, `test`, `build`,
   `analyze:seo` (у страницы обязана быть `metadata` с описанием 50–160
   символов — `tooling/page-metadata-and-seo-registry`).

## Дальше

Форма — `ucp-fe-form-design`, тесты — `ucp-fe-test-design`, ревью —
`ucp-fe-architecture-review` и `ucp-fe-api-review`.

$ARGUMENTS
