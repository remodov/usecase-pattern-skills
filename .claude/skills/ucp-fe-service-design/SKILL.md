---
name: ucp-fe-service-design
lang: any
track: frontend
description: Подключить внешний сервис к фронту из шаблона frontend-templates — контракт npm-пакетом из приватного реестра, секция orval, генерация хуков/zod/моков, сверка дрейфа контракта.
when_to_use: Триггеры — «подключи сервис», «обнови контракт», «в спеке новый тег», «сверь карту с контрактом». До постройки экранов.
allowed-tools: Read Glob Grep Write Edit Bash(bun*) Bash(npm*) Bash(git diff*)
---

# Подключение сервиса — проектирование

## Откуда берутся правила

`openspec/specs/api/spec.md` проекта; сводка — `AGENTS.md`. Рецепт подключения —
`docs/api.md` проекта и справочник `ui-from-openapi/references/contract-lifecycle.md`,
если шаблон его принёс.

## Порядок

1. **Контракт приезжает npm-пакетом из приватного реестра**
   (`api/contract-as-npm-package`). Локального `openapi.yaml` в проекте не
   бывает: копия расходится с сервисом молча, и заметить это нечем. Демо —
   единственное исключение, и оно уезжает по `bun run demo:remove`.

2. **У каждой операции есть `operationId`** (`api/operationid-required`): из
   него берётся имя хука. Нет — правится контракт на стороне сервиса, а не
   обходится на фронте.

3. **Секция сервиса в `orval.config.ts` собирается по образцу**
   (`api/orval-section-shape`). Образца в шаблоне может не остаться: после
   `demo:remove` конфиг обнуляется до `defineConfig({})` — рецепт брать
   из `docs/api.md`.

4. **Генерация — командой, руками ничего не правится**
   (`api/generated-code-immutable`): `bun run generate:api` даёт хуки, zod-схемы
   и фабрики моков. Каталог сгенерированного не хранится в git и
   перезаписывается на `predev` / `prebuild` / `pretest`.

5. **Проверь режимы вокруг контракта до первого экрана**
   (`api/contract-modes-before-gate-1`): генерация, `env:check`, тесты
   с MSW-стендом. Экран, построенный до рабочего контракта, переделывается целиком.

6. **Вошедшего отдаёт эндпоинт действующего лица**
   (`api/me-endpoint-convention`) — оттуда же приезжают скоупы прав.

7. **Окружение — только через `env` из `@shared/config`**
   (`environment/env-via-shared-config`), наборы ключей стендов одинаковы
   (`environment/env-identical-key-sets`), проверяется `bun run env:check`.

8. **Обновление контракта — это сверка дрейфа.** Подняли версию пакета —
   прогони генерацию, `typecheck`, `map:check` и посмотри, какие карты экранов
   разошлись с контрактом.

## Дальше

Экран — `ucp-fe-screen-design`. Ревью — `ucp-fe-api-review`,
`ucp-fe-tooling-review` (окружение и гейты).

$ARGUMENTS
