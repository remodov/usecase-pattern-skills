---
name: ucp-validation-design
description: Сгенерировать кастомный constraint (annotation + ConstraintValidator), validation group или cross-field-валидатор по Validation Style Guide. Создаёт пары @<DomainTerm>/`<DomainTerm>Validator` для доменных правил типа RussianPhone, VatNumber, Iso8601Duration. Решает: куда положить — common/validation/ для общих или core/<bc>/validation/ для domain-specific; isValid(null) → true для композиции с @NotNull; имя без префикса Valid/Check; class-level constraint для cross-field. Применяется когда стандартных Jakarta-аннотаций недостаточно. Триггеры: «нужен constraint для X», «custom validator», «cross-field валидация для DTO», «validation group для Y».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Validation — проектирование custom constraints

Ты генерируешь кастомные Jakarta Validation constraints, validation groups, cross-field-валидаторы по Validation Style Guide. Цель — корректная пара annotation + validator, которая проходит `ucp-validation-review` без findings.

## Инструкции

1. **Прочитай** `.claude/docs/validation-style-guide.md` — главный (`R-VLD-*`). Опционально `.claude/docs/rest-api-style-guide.md` `R-ERR-5`/`R-ERR-6` для понимания, как ошибка попадёт в violations.

2. **Уточни тип constraint:**
   - **Field-level custom** (`@RussianPhone`, `@VatNumber`) — валидирует одно поле по нестандартному формату.
   - **Validation group** (`OnCreate`, `OnUpdate`) — для одного DTO, который в разных контекстах требует разных полей.
   - **Cross-field class-level** (`@DateRange`, `@PasswordsMatch`) — правило с участием 2+ полей одного объекта.
   - **Composition of standard** — если описание сводится к набору `@NotBlank @Size(max=100) @Pattern(...)` — это НЕ custom, это просто комбинация standard-аннотаций на DTO-поле; не делай для этого custom constraint.

3. **Уточни параметры:**
   - **Имя:** `@<DomainTerm>` (`@RussianPhone`, `@VatNumber`). Без префиксов `Valid`/`Check`/`Is`. На русском только если термин не имеет английского эквивалента.
   - **Расположение:** доменно-специфичный → `core/<bc>/validation/` (часть domain-vocabulary); общий технический → `common/validation/`.
   - **Тип валидируемого значения:** `String`, `BigDecimal`, `LocalDate`, `<X>Request` для cross-field.
   - **Default message:** на русском, для пользователя. С `{value}`/`{min}`/`{max}` плейсхолдерами если параметры аннотации участвуют.
   - **Параметры аннотации:** ничего лишнего. Если для разных кейсов — разные значения, добавь `int min() default 0;` и подобные.

4. **Произведи код.**

   ### 4.1. Field-level custom constraint

   ```java
   // common/validation/RussianPhone.java (либо core/<bc>/validation/)
   package <pkg>.common.validation;

   import jakarta.validation.Constraint;
   import jakarta.validation.Payload;
   import java.lang.annotation.*;

   import static java.lang.annotation.ElementType.*;
   import static java.lang.annotation.RetentionPolicy.RUNTIME;

   @Target({ FIELD, PARAMETER, RECORD_COMPONENT })
   @Retention(RUNTIME)
   @Constraint(validatedBy = RussianPhoneValidator.class)
   public @interface RussianPhone {
       String message() default "Номер должен быть в формате +7XXXXXXXXXX";
       Class<?>[] groups() default {};
       Class<? extends Payload>[] payload() default {};
   }
   ```

   ```java
   // common/validation/RussianPhoneValidator.java
   package <pkg>.common.validation;

   import jakarta.validation.ConstraintValidator;
   import jakarta.validation.ConstraintValidatorContext;
   import java.util.regex.Pattern;

   public class RussianPhoneValidator implements ConstraintValidator<RussianPhone, String> {

       private static final Pattern PHONE = Pattern.compile("^\\+7\\d{10}$");

       @Override
       public boolean isValid(String value, ConstraintValidatorContext ctx) {
           return value == null || PHONE.matcher(value).matches();   // null — валидно (R-VLD-CC-4)
       }
   }
   ```

   Использование на DTO (для composition с @NotBlank):
   ```java
   public record CreateContactRequest(
       @NotBlank(message = "Телефон обязателен")
       @RussianPhone
       String phone
   ) {}
   ```

   ### 4.2. Validation group

   ```java
   // core/<bc>/validation/OnCreate.java
   /**
    * Применяется при создании нового экземпляра ресурса.
    * Поля, помеченные groups = OnCreate.class, обязательны для POST.
    */
   public interface OnCreate {}
   ```

   Использование:
   ```java
   public record OrderRequest(
       @NotNull(groups = OnCreate.class) Long customerId,
       @NotNull Money totalAmount,
       @Size(max = 1000) String comment
   ) {}

   // controller:
   @PostMapping
   public OrderJson create(@Validated(OnCreate.class) @RequestBody OrderRequest req) { ... }
   ```

   ### 4.3. Cross-field constraint (class-level)

   ```java
   // common/validation/DateRange.java
   @Target({ TYPE })
   @Retention(RUNTIME)
   @Constraint(validatedBy = DateRangeValidator.class)
   public @interface DateRange {
       String message() default "dateFrom должен быть не позже dateTo";
       String fromField() default "dateFrom";
       String toField() default "dateTo";
       Class<?>[] groups() default {};
       Class<? extends Payload>[] payload() default {};
   }
   ```

   ```java
   // common/validation/DateRangeValidator.java
   import org.springframework.beans.BeanWrapperImpl;

   public class DateRangeValidator implements ConstraintValidator<DateRange, Object> {

       private String fromField;
       private String toField;
       private String message;

       @Override
       public void initialize(DateRange annotation) {
           this.fromField = annotation.fromField();
           this.toField = annotation.toField();
           this.message = annotation.message();
       }

       @Override
       public boolean isValid(Object value, ConstraintValidatorContext ctx) {
           if (value == null) return true;
           var wrapper = new BeanWrapperImpl(value);
           var from = (LocalDate) wrapper.getPropertyValue(fromField);
           var to = (LocalDate) wrapper.getPropertyValue(toField);
           if (from == null || to == null) return true;            // обе пустые — другая аннотация
           if (!from.isAfter(to)) return true;

           ctx.disableDefaultConstraintViolation();
           ctx.buildConstraintViolationWithTemplate(message)
              .addPropertyNode(fromField)                          // ошибка прицепится к dateFrom
              .addConstraintViolation();
           return false;
       }
   }
   ```

   Использование (annotation на классе):
   ```java
   @DateRange(fromField = "dateFrom", toField = "dateTo")
   public record OrderFilterRequest(
       LocalDate dateFrom, LocalDate dateTo, ...
   ) {}
   ```

   ### 4.4. ВАЖНО: НЕ делать composition standard-аннотаций как custom

   Если правило сводится к `@NotBlank + @Size(max=100) + @Pattern(...)` без custom-логики — **просто навешай эти аннотации на поле DTO**. Не создавай `@OrderName` annotation, который объединяет их. Composition есть в Jakarta (`@OverridesAttribute`), но он **не одобряется** этим стандартом — теряется явность правил для читателя кода.

5. **Самопроверка перед выдачей** (`R-VLD-CC-*`, `R-VLD-XF-*`, `R-VLD-GRP-*`):
   - Annotation interface + ConstraintValidator implementation — **обязательно пара**, в одном пакете.
   - `@Target({ FIELD, PARAMETER, RECORD_COMPONENT })` для field-level (RECORD_COMPONENT нужен для record-полей в Java 16+).
   - `@Target({ TYPE })` для cross-field class-level.
   - `@Retention(RUNTIME)` обязательно.
   - `Class<?>[] groups() default {};` и `Class<? extends Payload>[] payload() default {};` — **обязательные** методы Jakarta-spec.
   - `default message()` на русском.
   - `isValid(null, ctx)` возвращает `true` для field-level (композируется с `@NotNull`/`@NotBlank`).
   - Имя без префиксов `Valid`/`Check`/`Is`.
   - Расположение: доменное → `core/<bc>/validation/`; общее → `common/validation/`.
   - Validator stateless (без `@Autowired`-полей с runtime-state).
   - Для cross-field — `addPropertyNode(<field>)` чтобы ошибка прицепилась к конкретному полю в violations.

6. **Структура вывода:**
   1. **Решения** — тип constraint (field/group/cross-field), имя, расположение (`core/<bc>/validation/` или `common/validation/`), message.
   2. **Дерево новых файлов** — путь к annotation + validator.
   3. **Каждый файл — отдельный code block** с путём в заголовке.
   4. **Пример использования** на DTO — отдельный code block с полем/классом, где аннотация применяется. Покажи композицию с standard-аннотациями (`@NotBlank @RussianPhone`).
   5. **Заметки по реализации:**
      - Команды проверки: `./gradlew compileJava`, `./gradlew test --tests *<X>ValidatorTest`.
      - Sample unit-тест validator-а: 3 кейса (valid, invalid, null → true).
      - **TODO:** message-bundle для i18n (`{key}` в message + `messages_ru.properties`).
   6. **Финальный шаг:** «после генерации запусти `ucp-validation-review` для верификации; добавь использование на конкретный DTO через PR».

## Что НЕ делает

- Не пишет DTO. Структура входных DTO определяется OpenAPI YAML (см. `R-VLD-OAS-2`).
- Не модифицирует контроллеры — добавление `@Valid` на параметре делается отдельным шагом (это часть `ucp-pattern-design` или `ucp-api-design`).
- Не пишет `@RestControllerAdvice` для маппинга в ProblemDetails — стандартный обработчик из Spring + `R-ERR-5` уже это покрывает.
- Не модифицирует generated DTO из openapi-generator (`R-VLD-OAS-X1`).
- Не пишет domain invariants в Aggregate — это `ucp-ddd-tactical-design`.

После — обязательно `ucp-validation-review` для верификации.

$ARGUMENTS
