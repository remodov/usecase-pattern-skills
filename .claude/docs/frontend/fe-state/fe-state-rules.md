# Управление состоянием (React + TS)

> **Что это.** Concern `fe-state` трека `frontend` (стек React+TS). Single-stack → плоская форма: коды + интент +
> примеры внутри. Коды: `FE-ST-<N>` — обязательно, `FE-ST-X<N>` — антипаттерн. Карта трека — `frontend/_index.md`.
>
> **Статус: STUB (каркас).** Направление ниже задано, наполняет **FE-лид** по `_meta/authoring-contract.md` §8.
> После наполнения — создать пару `ucp-fe-state-{design,review}` (track: frontend) и
> прогнать `ucp-meta-review`. Зарегистрировать `FE-ST-*` в `_meta/rule-code-registry.md`.

**Интент (что покрывает):** local UI-state vs server-state разделены; server-data НЕ в глобальном сторе (это кеш — см. fe-data-fetching); стор минимален; нет дублирования источника правды.

## 1. Разделение local/server-state
**MUST:**
- **FE-ST-10.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-ST-X1.** [TODO: FE-лид] …

## 2. Выбор и границы стора
**MUST:**
- **FE-ST-20.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-ST-X2.** [TODO: FE-лид] …

## 3. Производные данные (селекторы, не дубли)
**MUST:**
- **FE-ST-30.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-ST-X3.** [TODO: FE-лид] …
