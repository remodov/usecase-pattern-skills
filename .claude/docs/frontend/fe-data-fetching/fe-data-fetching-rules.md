# Запросы к API (React + TS)

> **Что это.** Concern `fe-data-fetching` трека `frontend` (стек React+TS). Single-stack → плоская форма: коды + интент +
> примеры внутри. Коды: `FE-DATA-<N>` — обязательно, `FE-DATA-X<N>` — антипаттерн. Карта трека — `frontend/_index.md`.
>
> **Статус: STUB (каркас).** Направление ниже задано, наполняет **FE-лид** по `_meta/authoring-contract.md` §8.
> После наполнения — создать пару `ucp-fe-data-fetching-{design,review}` (track: frontend) и
> прогнать `ucp-meta-review`. Зарегистрировать `FE-DATA-*` в `_meta/rule-code-registry.md`.

**Интент (что покрывает):** запросы через react-query/SWR (кеш/инвалидация/retry), не `fetch` в компоненте; явные loading/error/empty состояния; отмена устаревших; типизированные ответы; problem+json разбирается.

## 1. Слой запросов (хуки, не компонент)
**MUST:**
- **FE-DATA-10.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-DATA-X1.** [TODO: FE-лид] …

## 2. Кеш и инвалидация
**MUST:**
- **FE-DATA-20.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-DATA-X2.** [TODO: FE-лид] …

## 3. Loading/error/empty + отмена
**MUST:**
- **FE-DATA-30.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-DATA-X3.** [TODO: FE-лид] …

## 4. Типы ответов и ошибки
**MUST:**
- **FE-DATA-40.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-DATA-X4.** [TODO: FE-лид] …
