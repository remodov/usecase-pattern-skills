---
name: ucp-validation-review
description: Ревью валидации входных данных Java/Spring (Jakarta Validation, коды R-VLD-*) — @Valid на контроллерах и nested-полях, @Validated на @ConfigurationProperties, custom constraints, validation groups, cross-field, OpenAPI useBeanValidation.
when_to_use: Ревью контроллеров, DTO, custom validators, configuration-классов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации

Ты ревьюишь валидацию входных данных в Java/Spring-сервисе на соответствие требованиям `validation/*`. Главные точки контроля: `@Valid` на контроллерах и nested-полях, `@Validated` на configuration, manual-валидация в Handler vs Jakarta, custom constraints размещение, OpenAPI integration.

## Зависимости

- **`.claude/docs/backend/validation/spec.md`** — индекс всех правил (полный текст с примерами — `references/<lang>/implementation.md`). Каждое нарушение цитируется кодом из подгрупп: `R-VLD-WHERE-*` (где валидируем), `R-VLD-STD-*` (стандартные constraints), `R-VLD-CC-*` (custom constraints), `R-VLD-GRP-*` (groups), `R-VLD-XF-*` (cross-field), `R-VLD-OAS-*` (OpenAPI generator), `R-VLD-CFG-*` (config), `R-VLD-MSG-*` (сообщения).
- Парные документы: `backend/rest-api/spec.md` (`rest-api/validation-errors-list-violations`/`rest-api/validation-errors-list-violations` — формат violations), `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` — Idempotency-Key валидация), `backend/ddd-tactical/spec.md` (`R-ENT-*`/`R-AGG-*` — отличие domain invariants от validation).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/validation/spec.md` (общий контракт) **и Java-реализацию** `.claude/docs/backend/validation/references/java/implementation.md` (Jakarta/OpenAPI-first — для проверки Java-кода). Цитируй конкретные коды правил (`validation/input-validated-at-edge`, `validation/generated-artifacts-immutable`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые контроллеры (`*-in-adapter/`), DTO (`*Request`, `*Response`), `*ConfigurationProperties`/`*Settings`, кастомные validators (`common/validation/`, `core/validation/`), OpenAPI YAML (`*.openapi.yaml`).

3. **Прогон по подгруппам кодов:**
   - **`R-VLD-WHERE-5`** — на реплике чужих данных (справочник из шины, наливка через API) проверок формы нет: копия сохраняется как пришла, проверяются идентификатор и метка версии. Обязательность полей владельца, навешенная на приёме, — `validation/replica-is-stored-as-received`: запись уходит в разбор, справочник молча неполный.
   - **`R-VLD-WHERE-*`** — `@Valid` на @RequestBody/@RequestParam/@PathVariable; `@Validated` на `@ConfigurationProperties`-классах; нет manual-валидации в Handler (`if (cmd.x < 0) throw`); нет дублирования валидации на UseCase command; `@Valid` на nested-DTO полях.
   - **`R-VLD-STD-*`** — `@NotBlank` для строк, `@NotEmpty` для коллекций, `@DecimalMin`/`@DecimalMax` для BigDecimal, `@Email` вместо regex, `@Pattern` только для редких форматов, `@Past`/`@Future` для дат.
   - **`R-VLD-CC-*`** — custom constraints в `core/validation/` (доменные) или `common/validation/` (общие); annotation + ConstraintValidator пара; `isValid(null) → true`; имена без префиксов `Valid`/`Check`.
   - **`R-VLD-GRP-*`** — groups только для одного класса с разными required-полями (Create/Update); не для «строгая/мягкая»; не цепочки 3+ groups.
   - **`R-VLD-XF-*`** — cross-field правила как class-level annotation; не `@AssertTrue`-методы; не валидация в Handler.
   - **`R-VLD-OAS-*`** — `useBeanValidation: "true"` в openapi-generator конфиге; constraints в OpenAPI YAML (pattern, minLength, required); custom-constraints не дописываются в generated DTO.
   - **`R-VLD-CFG-*`** — `@Validated` на каждом `@ConfigurationProperties`; `@NotNull`/`@NotBlank` на required-полях; `@Valid` на nested settings; не `@Value` для required-конфига.
   - **`R-VLD-MSG-*`** — `message` на русском; интерполяция через `{}`-плейсхолдеры; пользовательский язык, не технический.

4. **Ищи паттерны-нарушения:**
   - Контроллер с `@RequestBody X req` без `@Valid` — `validation/input-validated-at-edge`.
   - Handler с ручной проверкой формы входа (`if (cmd.amount() < 0) throw ...`) вместо контракта на границе — `validation/input-validated-at-edge`.
   - `@ConfigurationProperties` без `@Validated` на классе — `validation/config-validated-at-startup` / `validation/config-validated-at-startup`.
   - DTO с `List<X> items` или `OtherDto nested` без `@Valid` на поле, при этом родительский `@Valid` — `validation/nested-validated-recursively` (silent skip).
   - Aggregate-поле с `@Min(1) int quantity` — `validation/domain-invariants-in-aggregate` (это инвариант, не валидация).
   - `@NotNull int x` или `@NotNull long y` — `validation/no-false-or-composite-constraints` (примитив не nullable).
   - `@Pattern("^[^@]+@[^@]+$")` для email — `validation/standard-constraints-preferred` (используй `@Email`).
   - `@Min` на `BigDecimal`-поле — `validation/no-false-or-composite-constraints` производный (используй `@DecimalMin`).
   - Custom validator возвращает `false` при null — `validation/custom-constraint-null-safe`.
   - Custom-аннотация в одном файле с DTO — `validation/custom-constraint-is-reusable`.
   - `@AssertTrue boolean isValid()` метод в DTO для cross-field — `validation/cross-field-rules-on-object`.
   - Cross-field валидация в Handler перед dispatch — `validation/cross-field-rules-on-object`.
   - Manual-цепочка `@Validated({A.class, B.class, C.class})` — `validation/scenario-groups-are-narrow`.
   - Validation groups для «strict/loose» — `validation/scenario-groups-are-narrow` (нужны разные DTO).
   - В `build.gradle.kts`/`pom.xml` openapi-generator с `useBeanValidation = false` или без указания — `validation/generation-carries-constraints`.
   - Modified-date generated DTO с `@NotNull` руками — `validation/generated-artifacts-immutable`.
   - `class <X>Request` в `*-in-adapter/jsonbean/` или подобном handcrafted-пакете без `@Generated` — `validation/controller-implements-generated-contract`.
   - В Java-коде `@Pattern("^\\+7\\d{10}$")` на поле, при этом то же `pattern` уже в OpenAPI YAML — `validation/single-source-of-truth` (дублирование).
   - Контроллер с `@RestController` + `@RequestMapping` ручной без `implements <Tag>Api` — `validation/controller-implements-generated-contract` (нарушение).
   - `@Value("${prop.required}")` — `validation/config-validated-at-startup`.
   - English в `message`-параметре аннотации — `validation/message-in-user-language`.

5. **При ревью OpenAPI YAML (`*.openapi.yaml`):**
   - Required-поля в `required:` массиве.
   - Constraints явно указаны: `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `format: email`/`uuid`/`date-time`.
   - Nested schemas (`$ref`) валидируются автоматически generated `@Valid`.
   - Если в коде нужна стрикт-валидация, которой нет в YAML — это либо отсутствие правила в YAML (добавить), либо custom-wrapper в коде.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`validation/input-validated-at-edge`, `validation/generation-carries-constraints`).

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично:**
     - `@RequestBody` без `@Valid` — silent passing невалидных данных в Handler.
     - `@ConfigurationProperties` без `@Validated` — невалидный конфиг в проде.
     - `@Valid` забыт на nested-DTO — silent skip nested-валидации.
     - `useBeanValidation = false` в openapi-generator.
     - Manual if-цепочка вместо Jakarta — теряется единый `violations` формат.
   - **Предупреждение:**
     - `@NotNull` на примитиве — мёртвый код.
     - Кастомный regex вместо `@Email`.
     - `@AssertTrue isXValid()` в DTO для cross-field.
     - Custom-constraint в одном файле с DTO.
     - Composite-аннотации `@NotBlankAndAtMost50`.
   - **Замечание:**
     - Английский в `message`.
     - Дублирование default-message в каждом поле.
     - Validation groups использованы там, где можно ограничиться одним DTO.

## Что не входит

- Доменные инварианты в Aggregate — `ucp-ddd-tactical-review`.
- REST API-контракт (URL, JSON, ProblemDetails формат) — `ucp-api-review`.
- UseCase-логика (бизнес-валидация) — `ucp-pattern-review`.
- Spring Security / RBAC — `ucp-auth-review`.
- jOOQ-репозиторий (валидация на persistence-уровне) — `ucp-jooq-review`.
- Resilience-обвязка — `ucp-resilience-review`.
- PostgreSQL CHECK-constraints — `ucp-pg-schema-review`.
- Java-стиль (нейминг, импорты) — `ucp-java-style-review`.

$ARGUMENTS
