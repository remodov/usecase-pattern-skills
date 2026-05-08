---
name: ucp-validation-review
description: Ревью валидации входных данных (Jakarta Validation) — где валидируем, какие constraints применяем, custom-constraints размещение, validation groups, cross-field, @ConfigurationProperties + @Validated, OpenAPI-сгенерированные DTO с useBeanValidation. Проверяет @Valid на контроллерах и nested-полях, @Validated на configuration-properties, отсутствие manual if-цепочек в Handler, @NotNull на примитивах, кастомные constraints в правильных местах, validation groups только для одного класса с разными required-полями. Применяется при ревью контроллеров, DTO, custom validators, configuration-классов. Опирается на коды R-VLD-*.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации

Ты ревьюишь валидацию входных данных в Java/Spring-сервисе на соответствие Validation Style Guide. Главные точки контроля: `@Valid` на контроллерах и nested-полях, `@Validated` на configuration, manual-валидация в Handler vs Jakarta, custom constraints размещение, OpenAPI integration.

## Зависимости

- **`.claude/docs/validation-style-guide.md`** — единственный источник правил. Каждое нарушение цитируется кодом из подгрупп: `R-VLD-WHERE-*` (где валидируем), `R-VLD-STD-*` (стандартные constraints), `R-VLD-CC-*` (custom constraints), `R-VLD-GRP-*` (groups), `R-VLD-XF-*` (cross-field), `R-VLD-OAS-*` (OpenAPI generator), `R-VLD-CFG-*` (config), `R-VLD-MSG-*` (сообщения).
- Парные документы: `rest-api-style-guide.md` (`R-ERR-5`/`R-ERR-6` — формат violations), `auth-patterns-style-guide.md` (`AUTH-19` — Idempotency-Key валидация), `ddd-tactical-style-guide.md` (`R-ENT-*`/`R-AGG-*` — отличие domain invariants от validation).

## Инструкции

1. **Прочти style guide** из `.claude/docs/validation-style-guide.md`. Цитируй конкретные коды правил (`R-VLD-WHERE-1`, `R-VLD-OAS-X1`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые контроллеры (`*-in-adapter/`), DTO (`*Request`, `*Response`), `*ConfigurationProperties`/`*Settings`, кастомные validators (`common/validation/`, `core/<bc>/validation/`), OpenAPI YAML (`*.openapi.yaml`).

3. **Прогон по подгруппам кодов:**
   - **`R-VLD-WHERE-*`** — `@Valid` на @RequestBody/@RequestParam/@PathVariable; `@Validated` на `@ConfigurationProperties`-классах; нет manual-валидации в Handler (`if (cmd.x < 0) throw`); нет дублирования валидации на UseCase command; `@Valid` на nested-DTO полях.
   - **`R-VLD-STD-*`** — `@NotBlank` для строк, `@NotEmpty` для коллекций, `@DecimalMin`/`@DecimalMax` для BigDecimal, `@Email` вместо regex, `@Pattern` только для редких форматов, `@Past`/`@Future` для дат.
   - **`R-VLD-CC-*`** — custom constraints в `core/<bc>/validation/` (доменные) или `common/validation/` (общие); annotation + ConstraintValidator пара; `isValid(null) → true`; имена без префиксов `Valid`/`Check`.
   - **`R-VLD-GRP-*`** — groups только для одного класса с разными required-полями (Create/Update); не для «строгая/мягкая»; не цепочки 3+ groups.
   - **`R-VLD-XF-*`** — cross-field правила как class-level annotation; не `@AssertTrue`-методы; не валидация в Handler.
   - **`R-VLD-OAS-*`** — `useBeanValidation: "true"` в openapi-generator конфиге; constraints в OpenAPI YAML (pattern, minLength, required); custom-constraints не дописываются в generated DTO.
   - **`R-VLD-CFG-*`** — `@Validated` на каждом `@ConfigurationProperties`; `@NotNull`/`@NotBlank` на required-полях; `@Valid` на nested settings; не `@Value` для required-конфига.
   - **`R-VLD-MSG-*`** — `message` на русском; интерполяция через `{}`-плейсхолдеры; пользовательский язык, не технический.

4. **Ищи паттерны-нарушения:**
   - Контроллер с `@RequestBody X req` без `@Valid` — `R-VLD-WHERE-1`.
   - Handler с `if (cmd.amount() < 0) throw new ValidationException(...)` — `R-VLD-WHERE-X1`.
   - `@ConfigurationProperties` без `@Validated` на классе — `R-VLD-WHERE-X3` / `R-VLD-CFG-X1`.
   - DTO с `List<X> items` или `OtherDto nested` без `@Valid` на поле, при этом родительский `@Valid` — `R-VLD-WHERE-4` (silent skip).
   - Aggregate-поле с `@Min(1) int quantity` — `R-VLD-WHERE-X4` (это инвариант, не валидация).
   - `@NotNull int x` или `@NotNull long y` — `R-VLD-STD-X1` (примитив не nullable).
   - `@Pattern("^[^@]+@[^@]+$")` для email — `R-VLD-STD-X2` (используй `@Email`).
   - `@Min` на `BigDecimal`-поле — `R-VLD-STD-X1` производный (используй `@DecimalMin`).
   - Custom validator возвращает `false` при null — `R-VLD-CC-X1`.
   - Custom-аннотация в одном файле с DTO — `R-VLD-CC-X2`.
   - `@AssertTrue boolean isValid()` метод в DTO для cross-field — `R-VLD-XF-X1`.
   - Cross-field валидация в Handler перед dispatch — `R-VLD-XF-X2`.
   - Manual-цепочка `@Validated({A.class, B.class, C.class})` — `R-VLD-GRP-X2`.
   - Validation groups для «strict/loose» — `R-VLD-GRP-X1` (нужны разные DTO).
   - В `build.gradle.kts`/`pom.xml` openapi-generator с `useBeanValidation = false` или без указания — `R-VLD-OAS-X2`.
   - Modified-date generated DTO с `@NotNull` руками — `R-VLD-OAS-X1`.
   - `class <X>Request` в `*-in-adapter/jsonbean/` или подобном handcrafted-пакете без `@Generated` — `R-VLD-OAS-X5`.
   - В Java-коде `@Pattern("^\\+7\\d{10}$")` на поле, при этом то же `pattern` уже в OpenAPI YAML — `R-VLD-OAS-X4` (дублирование).
   - Контроллер с `@RestController` + `@RequestMapping` ручной без `implements <Tag>Api` — `R-VLD-OAS-4` (нарушение).
   - `@Value("${prop.required}")` — `R-VLD-CFG-X2`.
   - English в `message`-параметре аннотации — `R-VLD-MSG-X1`.

5. **При ревью OpenAPI YAML (`*.openapi.yaml`):**
   - Required-поля в `required:` массиве.
   - Constraints явно указаны: `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `format: email`/`uuid`/`date-time`.
   - Nested schemas (`$ref`) валидируются автоматически generated `@Valid`.
   - Если в коде нужна стрикт-валидация, которой нет в YAML — это либо отсутствие правила в YAML (добавить), либо custom-wrapper в коде.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-VLD-WHERE-1`, `R-VLD-OAS-X2`).

7. **Доменные ориентиры серьёзности** (`RFF-12`):
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
