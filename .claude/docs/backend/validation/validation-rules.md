# Validation — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил валидации входных данных: код + интент, по разделам — **общий контракт**.
> **Реализация по языкам** — `java/validation-style-guide.md` (Jakarta Validation + OpenAPI-first),
> `python/validation-style-guide.md` (Pydantic v2, code-first). Коды `R-VLD-*` общие; меняется реализация.
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

Суть: **валидация контракта входа — на границе (edge)**, до Handler; **доменные инварианты — в агрегате**, не во фреймворк-валидаторе; конфиг валидируется fail-fast на старте. Источник правды по input-валидации — один (схема/модель), без дублирования.

## 1. Где валидируем
**MUST:**
- **R-VLD-WHERE-1.** Входной HTTP-DTO валидируется на границе декларативно (Java: `@Valid` + Jakarta; Python: Pydantic-модель FastAPI-эндпоинта). Невалидное → 400 с единым форматом violations (cross-ref `R-ERR-MAP-2`), до Handler.
- **R-VLD-WHERE-2.** Конфиг валидируется fail-fast на старте (Java: `@ConfigurationProperties` + `@Validated`; Python: `pydantic-settings BaseSettings`). Невалидный конфиг → падение на старте, не «поднялся с битыми флагами».
- **R-VLD-WHERE-3.** Доменные инварианты агрегата — **не** через фреймворк-валидатор; агрегат гарантирует целостность в конструкторе/методах, бросая domain-ошибку → edge мапит в 409/400 с конкретным `code` (cross-ref `R-AGG-*`, `R-ERR-MAP-1`).
- **R-VLD-WHERE-4.** Nested-DTO валидируется рекурсивно (Java: `@Valid` на поле; Python: вложенные Pydantic-модели — автоматически).

**MUST NOT:**
- **R-VLD-WHERE-X1.** Ручная `if (x < 0) throw ...` входная валидация в Handler — теряется единый формат violations. Правило про DTO → на границе; про инвариант → метод агрегата.
- **R-VLD-WHERE-X2.** Повторная валидация UseCase-команды после уже провалидированного DTO — двойная работа.
- **R-VLD-WHERE-X3.** Конфиг без валидации (см. `R-VLD-WHERE-2`).
- **R-VLD-WHERE-X4.** Доменный инвариант фреймворк-аннотацией на поле агрегата — поля иммутабельны после конструирования; инвариант — в конструкторе.

## 2. Стандартные constraints
**MUST:**
- **R-VLD-STD-1.** Null/empty проверки (Java `@NotNull`/`@NotBlank`; Python: тип `str` vs `str | None`, `min_length=1`).
- **R-VLD-STD-2.** Размеры (`@Size`; Python `min_length`/`max_length`/`Field(ge=,le=)`).
- **R-VLD-STD-3.** Формат — стандартными средствами (`@Email`; Python `EmailStr`), не самописный regex для известных форматов.
- **R-VLD-STD-4.** Время — корректные типы и границы (`@Past`/`@Future`; Python `datetime` + validator).
- **R-VLD-STD-5.** Тип-зависимая валидация на правильном типе (число — числовым constraint, не строковым).

**MUST NOT:**
- **R-VLD-STD-X1.** Null-проверка там, где тип уже не допускает null (Java `@NotNull int`; Python `@field_validator` «не None» на non-Optional поле) — ложная гарантия.
- **R-VLD-STD-X2.** Самописный regex для формата со стандартным средством (`@Pattern` email вместо `@Email`/`EmailStr`).
- **R-VLD-STD-X3.** Composite-«всё-в-одном» constraint поверх стандартных — лучше отдельные, читаемые.

## 3. Custom constraints
**MUST:**
- **R-VLD-CC-1.** Кастомный constraint — переиспользуемая единица (Java: annotation + ConstraintValidator; Python: `Annotated[T, AfterValidator(fn)]` или reusable `field_validator`/типы).
- **R-VLD-CC-2.** Размещается в общем модуле валидаторов, не inline в DTO.
- **R-VLD-CC-3.** Имя по доменному термину без префиксов `Valid`/`Check`/`Is` (`RussianPhone`, `VatNumber`).
- **R-VLD-CC-4.** Null обрабатывается отдельной null-проверкой; custom-валидатор на не-null значении (комбинируется с required).
- **R-VLD-CC-5.** Валидатор — stateless, чистая функция от значения; зависимости (справочник) — только осознанно.

**MUST NOT:**
- **R-VLD-CC-X1.** Custom-валидатор падает на null, ломая композицию с required-проверкой.
- **R-VLD-CC-X2.** Constraint inline в файле DTO — не переиспользуется, не находится grep-ом.
- **R-VLD-CC-X3.** Логика constraint в ad-hoc методе DTO (`@AssertTrue`/`@model_validator` с невыносимой логикой) — не переиспользуется.

## 4. Validation groups / сценарии
**MUST:**
- **R-VLD-GRP-1.** Разные required-поля одного DTO в разных сценариях — только когда DTO реально один (Java: validation groups; Python: отдельные модели или `model_validator(mode=...)` по контексту).
- **R-VLD-GRP-2.** Маркер группы — пустой, документированный.

**MUST NOT:**
- **R-VLD-GRP-X1.** Группы для «строгая/мягкая» — это два разных DTO (`CreateOrderRequest` vs `DraftOrderRequest`).
- **R-VLD-GRP-X2.** Цепочки 3+ групп на один класс — запах «класс делает слишком много», разбить.

## 5. Cross-field validation
**MUST:**
- **R-VLD-XF-1.** Правило с 2+ полями одного объекта — на уровне объекта (Java: class-level annotation; Python: `@model_validator(mode="after")`).
- **R-VLD-XF-2.** Имя описывает правило, не объект (`DateRange`, `PasswordsMatch`).

**MUST NOT:**
- **R-VLD-XF-X1.** Одноразовый ad-hoc метод вместо переиспользуемого правила, если правило встречается в нескольких DTO.
- **R-VLD-XF-X2.** Cross-field валидация в Handler перед dispatch — это валидация контракта, место — на DTO.

## 6. Контракт-схема как источник правды (OpenAPI)
**MUST:**
- **R-VLD-OAS-1.** Единый источник правды по input-валидации — **схема контракта**, без дублирования код↔YAML. Направление зависит от языка: Java — **OpenAPI-first** (YAML → generated DTO с `useBeanValidation`); Python/FastAPI — **code-first** (Pydantic-модели → OpenAPI генерируется из них). В обоих случаях правило живёт в одном месте.
- **R-VLD-OAS-4.** Контроллер реализует сгенерированный контракт-интерфейс (Java: `implements <Tag>Api`); в FastAPI — типизированные Pydantic-модели в сигнатуре эндпоинта (контракт = модель).
- **R-VLD-OAS-6.** После маппинга в UseCase-команду повторная валидация не делается — команда «уже чистая»; доменные инварианты — отдельный концерн на агрегате.

**MUST NOT:**
- **R-VLD-OAS-X1.** Править сгенерированные артефакты руками (Java: аннотации в `build/generated/...DTO.java`) — затрётся.
- **R-VLD-OAS-X4.** Дублирование правил в двух местах (YAML + код, или Pydantic + ручной чек) — источник правды один.
- **R-VLD-OAS-X5.** Handcrafted inbound-DTO в обход контракта (Java: вне OpenAPI-генерации, `BS-20`); в Python inbound-DTO = Pydantic-модель, не голый dict.

## 7. Конфигурация
**MUST:**
- **R-VLD-CFG-1.** Каждый класс конфига валидируется (Java `@Validated`; Python `BaseSettings` валидирует по типам автоматически) — fail-fast на старте.
- **R-VLD-CFG-2.** Required-поля без default; типобезопасно.
- **R-VLD-CFG-4.** Nested-конфиг валидируется рекурсивно.

**MUST NOT:**
- **R-VLD-CFG-X1.** Конфиг-класс без валидации.
- **R-VLD-CFG-X2.** Нетипизированное чтение required-конфига (Java `@Value`; Python `os.environ[...]` напрямую) — без валидации; использовать typed settings.

## 8. Сообщения и i18n
**MUST:**
- **R-VLD-MSG-1.** `message` — на языке пользователя (русский), для UI.
- **R-VLD-MSG-2.** Интерполяция значений через плейсхолдеры.
- **R-VLD-MSG-3.** i18n — через message-bundle/каталог по ключу.

**MUST NOT:**
- **R-VLD-MSG-X1.** Английский в пользовательском `message`.
- **R-VLD-MSG-X2.** Технические термины в сообщении («Field amount must be positive» → «Сумма должна быть положительной»).
- **R-VLD-MSG-X3.** Дублирование одного и того же message на каждом поле.
