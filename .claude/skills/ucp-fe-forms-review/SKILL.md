---
name: ucp-fe-forms-review
lang: any
track: frontend
description: Ревью формы React+TS по UCP frontend-методологии (коды FE-FORM-*) — состояние в Formik (не useState на поле), схемная валидация yup, async submit с блокировкой по isSubmitting, серверные ошибки на поля, compound-form.
when_to_use: Изменения в формах (useFormik/<Formik>, validationSchema, *Form*.tsx, onSubmit); ревью валидации, сабмита и обработки ошибок формы.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Forms (React + TS, Formik + yup)

Ты ревьюишь форму на соответствие `frontend/fe-forms/fe-forms-rules.md` (`FE-FORM-*`).

## Зависимости

- **`.claude/docs/frontend/fe-forms/fe-forms-rules.md`** (`FE-FORM-*`).
- Парные: `fe-state` (`FE-ST-1` — ввод не в сторе), `fe-data-fetching` (submit/thunk), `fe-component`, `fe-a11y`.

## Инструкции

1. **Прочти** `fe-forms-rules.md`. Цитируй конкретные коды (`FE-FORM-X4`), не префикс.

2. **Скоп.** Формы и поля: `useFormik`/`<Formik>`, `validationSchema`, `onSubmit`, `*Form*.tsx`, `<CompoundForm>`/`useCompoundForm`, `FormInput`/`FormSelect`/`FormCheckboxes`; `git diff` на этих файлах.

3. **Прогон.**
   - **Состояние/режим (`FE-FORM-1/2/3/13/14`):** россыпь `useState` на поля вместо Formik → `FE-FORM-X1`; неконтролируемые инпуты с чтением DOM → `FE-FORM-X2`; ввод формы в Redux-сторе → `FE-FORM-3` (`FE-ST-1`); `useEffect`+`setValues` вместо `enableReinitialize` → `FE-FORM-X7`; дубли формы на каждый режим вместо `PageMode`-параметризации → `FE-FORM-14`.
   - **Валидация (`FE-FORM-4/5/15`):** проверки вразнобой вместо yup-схемы → `FE-FORM-X3`; тексты/ограничения захардкожены в JSX → `FE-FORM-5`; хаотичный тайминг валидации (не единый осознанный) → `FE-FORM-15`.
   - **Submit (`FE-FORM-6/16/7/8/9`):** пустой `catch`/проглоченная ошибка → `FE-FORM-X4`; нет `disabled` по `isSubmitting` → `FE-FORM-X5`; `fetch` прямо в `onSubmit` → `FE-FORM-6`; пост-действие вслепую, без проверки возвращённого значения thunk'а → `FE-FORM-16`; серверная ошибка не показана → `FE-FORM-8/9`.
   - **Поля/компоновка (`FE-FORM-10/11/12`):** prop-drilling formik-пропсов вместо контекста → `FE-FORM-X6`; доменные значения захардкожены в поле → нарушение `FE-FORM-11`; поле без `label`/доступной ошибки → нарушение `FE-FORM-12` (`fe-a11y`).

4. **Cross-check:** запросы сабмита — `ucp-fe-data-fetching-review`; состояние вне формы — `ucp-fe-state-review`; рендер/props поля — `ucp-fe-component-review`; доступность — `ucp-fe-a11y-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — проглоченная ошибка сабмита (`FE-FORM-X4`), нет блокировки → двойной сабмит (`FE-FORM-X5`), серверная ошибка не показана (`FE-FORM-8`), состояние формы в сторе (`FE-FORM-3`/`FE-ST-1`).
   - **Предупреждение** — `useState` на поля вместо Formik (`FE-FORM-X1`), валидация вне yup-схемы (`FE-FORM-X3`), `fetch` в `onSubmit` (`FE-FORM-6`), поле без `label`/доступной ошибки (`FE-FORM-12`).
   - **Замечание** — неконтролируемые инпуты (`FE-FORM-X2`), prop-drilling вместо compound-form (`FE-FORM-X6`), `useEffect`+`setValues` вместо `enableReinitialize` (`FE-FORM-X7`), доменные значения в поле (`FE-FORM-11`).

## Что не входит

- Сам запрос/кеш/отмена сабмита — `ucp-fe-data-fetching-review`. Стор вне формы — `ucp-fe-state-review`. Рендер/props — `ucp-fe-component-review`. Семантика/ARIA — `ucp-fe-a11y-review`.

$ARGUMENTS
