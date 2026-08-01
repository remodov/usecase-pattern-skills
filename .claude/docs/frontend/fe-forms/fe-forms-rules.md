# Формы и валидация (React + TS, Formik + yup)

> **Что это.** Concern `fe-forms` трека `frontend` (стек React+TS, **Formik + yup**). Single-stack → плоская
> форма: коды + интент + примеры внутри (отдельного style-guide нет). Коды: `FE-FORM-<N>` — обязательно,
> `FE-FORM-X<N>` — антипаттерн. Карта трека — `frontend/_index.md`.
>
> **Реализация под проект:** состояние формы — Formik (`useFormik` / `<Formik>`); валидация — декларативная
> yup-схема в `validationSchema`; поля контролируемые (compound-form: `<CompoundForm>` + `useCompoundForm`,
> `FormInput`/`FormSelect`/`FormCheckboxes` из `@design-system/components`). Связанные: `fe-state` (локальное
> состояние формы — в Formik, не в сторе; cross-ref `FE-ST-1`), `fe-data-fetching` (submit дёргает thunk/fetcher),
> `fe-component` (поле не держит бизнес-логику/запросы), `fe-a11y` (label и ошибки доступны).

## 1. Состояние формы — в Formik
**MUST:**
- **FE-FORM-1.** Состояние формы (`values`/`errors`/`touched`/`isSubmitting`) держи в Formik (`useFormik`/`<Formik>`), а не россыпью `useState` на каждое поле.
- **FE-FORM-2.** Поля контролируемые и завязаны на Formik: `value` берётся из `values`, изменение — через `handleChange`/`setFieldValue`, потеря фокуса — через `handleBlur`.
- **FE-FORM-3.** Локальный (неотправленный) ввод формы держи в Formik, **не** в Redux-сторе (cross-ref `FE-ST-1`); в стор кладётся только результат сабмита / доменные сущности.
- **FE-FORM-13.** Форма редактирования инициализируется из доменной сущности и переинициализируется при её подгрузке — `enableReinitialize: true` с `initialValues` из стора; не копируй данные в форму вручную через `useEffect`+`setValues`.
- **FE-FORM-14.** Один компонент формы параметризуется **режимом** (`PageMode`: `CREATE`/`EDIT`/`INFO`), который задаёт `initialValues`, readonly-вид и ветку submit — а не три почти одинаковые копии формы на каждый режим.

**MUST NOT:**
- **FE-FORM-X1.** Ручной `useState` на каждое поле вместо Formik — дубль логики `values`/`touched`/валидации и рассинхрон.
- **FE-FORM-X2.** Неконтролируемые инпуты с прямым чтением DOM (`ref.value`, `getElementById`) вместо `values` Formik.

## 2. Схемная валидация (yup)
**MUST:**
- **FE-FORM-4.** Правила валидации — декларативная yup-схема в `validationSchema`; это единый источник правил поля, а не проверки, размазанные по обработчикам.
- **FE-FORM-5.** Тексты ошибок и доменные ограничения (`required`/формат/`min`-`max`/зависимости полей) выражены в схеме и переиспользуемы — не хардкод по месту в JSX.

- **FE-FORM-15.** Тайминг валидации выбран осознанно и единообразно (в проекте — валидация на submit: `validateOnChange/validateOnBlur/validateOnMount: false`), а не «по умолчанию на каждый keystroke» — это решение, а не случайность; ошибки появляются по `submit`/`touched`, не дёргают пользователя на каждый ввод.

**MUST NOT:**
- **FE-FORM-X3.** Ad-hoc проверки вразнобой в `onChange`/`onBlur`/`onSubmit` вместо yup-схемы — правила расходятся и не покрывают все пути ввода.
- **FE-FORM-X7.** Копирование подгруженной сущности в форму через `useEffect`+`setValues` вместо `enableReinitialize` (`FE-FORM-13`) — гонки и рассинхрон формы с данными.

## 3. Submit, ошибки и блокировка
**MUST:**
- **FE-FORM-6.** `onSubmit` — `async`; сама отправка идёт через thunk/fetcher доменного слоя (cross-ref `FE-DATA-*`), а не `fetch` прямо в обработчике.
- **FE-FORM-16.** Пост-действие после submit опирается на **возвращаемое значение** thunk'а (cross-ref `FE-DATA-15`): успех определяется по результату (например, навигация на роут созданной/изменённой сущности через `generatePath(getRoutePath(ROUTES.X), { id })`), а не предполагается вслепую и не зашивается до завершения запроса.
- **FE-FORM-7.** Во время отправки поля и submit-кнопка `disabled` по `isSubmitting` — защита от двойного сабмита.
- **FE-FORM-8.** Серверные ошибки сабмита показываются пользователю: маппятся на поле (`setFieldError`) или на форму (`setStatus`/состояние ошибки), не глушатся.
- **FE-FORM-9.** Ошибки (валидации и серверные) выводятся у поля/формы с учётом `touched` (после взаимодействия), а не молча отбрасываются.

**MUST NOT:**
- **FE-FORM-X4.** Пустой `catch` / проглоченная ошибка сабмита (silent failure) — пользователь не узнаёт о провале операции.
- **FE-FORM-X5.** Сабмит без блокировки на время отправки → двойная отправка (двойное списание / дублирующая операция).

## 4. Поля и компоновка (compound-form, доменные значения)
**MUST:**
- **FE-FORM-10.** Compound-form: поля берут `values`/`errors`/`touched` из контекста формы (`<CompoundForm>` + `useCompoundForm`, `FormInput`/`FormSelect`/`FormCheckboxes`), без ручного прокидывания formik-пропсов.
- **FE-FORM-11.** Доменные значения полей (опции селектов, справочники) приходят сверху/из стора, не хардкодятся внутри поля (cross-ref `FE-CMP-*`).
- **FE-FORM-12.** У каждого поля — `label` и доступная привязка сообщения об ошибке (cross-ref `fe-a11y`).

**MUST NOT:**
- **FE-FORM-X6.** Prop-drilling formik-пропсов через 3+ уровня вместо контекста compound-form.

## 5. Чеклист подключения (React + Formik + yup)
1. Состояние формы — в Formik (`values`/`errors`/`touched`/`isSubmitting`); поля контролируемые; ввод не в сторе (`FE-ST-1`).
2. Валидация — yup-схема `validationSchema`; тексты и доменные ограничения в схеме, без ad-hoc проверок в обработчиках.
3. `onSubmit` async через thunk/fetcher (`FE-DATA-*`); поля/кнопка `disabled` по `isSubmitting`; пост-действие — по возвращаемому значению thunk'а.
4. Ошибки валидации и серверные показываются у поля/формы (с `touched`), не глушатся пустым `catch`.
5. Compound-form: поля из контекста, доменные значения сверху, `label` + доступная ошибка (`fe-a11y`).
6. Одна форма параметризуется режимом (`PageMode`); edit-форма — `enableReinitialize` из стора, а не `useEffect`+`setValues`.
