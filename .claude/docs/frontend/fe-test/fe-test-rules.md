# Тестирование фронта (Vitest + Testing Library)

> **Что это.** Concern `fe-test` трека `frontend` (стек React+TS). Single-stack → плоская форма: коды + интент +
> примеры внутри. Коды: `FE-TEST-<N>` — обязательно, `FE-TEST-X<N>` — антипаттерн. Карта трека — `frontend/_index.md`.
>
> **Статус: STUB (каркас).** Направление ниже задано, наполняет **FE-лид** по `_meta/authoring-contract.md` §8.
> После наполнения — создать пару `ucp-fe-test-{design,review}` (track: frontend) и
> прогнать `ucp-meta-review`. Зарегистрировать `FE-TEST-*` в `_meta/rule-code-registry.md`.

**Интент (что покрывает):** тест юзер-центричный (что видит/делает пользователь, не имплементация); запросы — через MSW (мок на уровне сети), не мок хуков; нет тестов на детали реализации; a11y-роли как селекторы.

## 1. Юзер-центричные тесты (Testing Library)
**MUST:**
- **FE-TEST-10.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-TEST-X1.** [TODO: FE-лид] …

## 2. Мок API через MSW
**MUST:**
- **FE-TEST-20.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-TEST-X2.** [TODO: FE-лид] …

## 3. Что НЕ тестировать (детали реализации)
**MUST:**
- **FE-TEST-30.** [TODO: FE-лид] …
**MUST NOT:**
- **FE-TEST-X3.** [TODO: FE-лид] …
