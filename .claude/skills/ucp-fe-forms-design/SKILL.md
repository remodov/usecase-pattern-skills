---
name: ucp-fe-forms-design
lang: any
track: frontend
description: Спроектировать форму React+TS по UCP frontend-методологии (коды FE-FORM-*) — состояние в Formik, схемная валидация yup (validationSchema), async submit с блокировкой по isSubmitting, серверные ошибки на поля, compound-form поля.
when_to_use: Триггеры — «форма для X», «валидация полей», «submit/отправка формы». При проектировании формы, схемы валидации или обработки сабмита.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Forms — проектирование (React + TS, Formik + yup)

Ты проектируешь форму по `frontend/fe-forms/fe-forms-rules.md` (`FE-FORM-*`). Часть трека `frontend`
(карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-forms/fe-forms-rules.md` (`FE-FORM-*`). Связанные: `fe-state` (ввод формы — в Formik, не в сторе; `FE-ST-1`), `fe-data-fetching` (submit дёргает thunk/fetcher), `fe-component` (поле без бизнес-логики/запросов), `fe-a11y` (label/ошибки доступны). Коды — в обосновании, не в коде.

2. **Состояние и режим формы** (`FE-FORM-1/2/3/13/14`): всё (`values`/`errors`/`touched`/`isSubmitting`) — в Formik; поля контролируемые; неотправленный ввод не в Redux-сторе (`FE-ST-1`). Edit-форма — `enableReinitialize: true` с `initialValues` из стора, не `useEffect`+`setValues` (`FE-FORM-X7`). Один компонент параметризуй режимом (`PageMode`: `CREATE`/`EDIT`/`INFO`), а не три копии.

3. **Валидация** (`FE-FORM-4/5/15`): правила — декларативной yup-схемой в `validationSchema` (единый источник); тексты и доменные ограничения — в схеме, не ad-hoc (`FE-FORM-X3`). Тайминг выбери осознанно (в проекте — на submit: `validateOnChange/Blur/Mount: false`), а не дёргай пользователя на каждый keystroke.

4. **Submit** (`FE-FORM-6/16/7/8/9`): `onSubmit` async, отправка через thunk/fetcher (`FE-DATA-*`); пост-действие — по **возвращаемому значению** thunk'а (`FE-DATA-15`): навигация на роут сущности через `generatePath(getRoutePath(ROUTES.X), { id })`, а не вслепую (`FE-FORM-16`). Поля и кнопка `disabled` по `isSubmitting` (`FE-FORM-X5`); серверные ошибки — на поле (`setFieldError`)/форму (`setStatus`) с `touched`; не глуши (`FE-FORM-X4`).

5. **Поля/компоновка** (`FE-FORM-10/11/12`): compound-form (`<CompoundForm>`/`useCompoundForm`, `FormInput`/`FormSelect`/`FormCheckboxes`) — поля из контекста, без prop-drilling (`FE-FORM-X6`); доменные значения сверху/из стора; `label` + доступная ошибка (`fe-a11y`).

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-forms-review`. Запросы сабмита — `ucp-fe-data-fetching-design`, состояние вокруг формы — `ucp-fe-state-design`.

## Антипаттерны, которые НЕ генерировать

- Ручной `useState` на каждое поле вместо Formik (`FE-FORM-X1`); неконтролируемые инпуты с чтением DOM (`FE-FORM-X2`).
- Валидация вразнобой в `onChange`/`onBlur`/`onSubmit` вместо yup-схемы (`FE-FORM-X3`); `useEffect`+`setValues` вместо `enableReinitialize` (`FE-FORM-X7`).
- Пустой `catch` / проглоченная ошибка сабмита (`FE-FORM-X4`); сабмит без блокировки → двойная отправка (`FE-FORM-X5`).
- Prop-drilling formik-пропсов вместо контекста compound-form (`FE-FORM-X6`); состояние формы в Redux-сторе (`FE-ST-1`).

После работы скилла — обязательно `ucp-fe-forms-review`.

$ARGUMENTS
