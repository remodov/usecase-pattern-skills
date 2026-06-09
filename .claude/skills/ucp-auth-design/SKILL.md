---
name: ucp-auth-design
description: Зашаблонить Spring Security + OAuth2 Resource Server для UCP-сервиса на Java/Spring (коды AUTH-*) — валидация JWT, маппинг ролей, RBAC на эндпоинтах, ABAC-хелперы, audit log-аспект, раскладка секретов, идемпотентность.
when_to_use: При старте нового сервиса или добавлении auth в существующий. В цепочке — после ucp-pattern-design.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Проектирование паттернов аутентификации/авторизации

Ты шаблонируешь слой безопасности / auth для Java/Spring-сервиса по командному auth-patterns style guide.

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` (полный текст с примерами кода — `backend/auth-patterns/java/auth-patterns-style-guide.md`, открывай точечно по разделу). Цитируй правила `AUTH-N` **в design-обосновании ответа пользователю**, но **не в комментариях сгенерированного кода** (`JS-7.3` в `backend/java/java-style/java-rules.md`). Никаких `// AUTH-15`, `// AUTH-9` в исходниках — соответствие выражается через `@PreAuthorize`, наличие audit-таблицы, `JwtAuthenticationConverter` и т.д.

2. **Подтверди слой.** Определи:
   - **Gateway** — здесь только валидация JWT + rate limiting. Сервис обычно не Gateway; если перед тобой именно Gateway — генерируешь правила маршрутизации, но не RBAC handler-ов.
   - **BFF** — валидация JWT + RBAC по ролям, агрегация вызовов. При необходимости — сессия в Redis.
   - **Domain Service** — валидация JWT (передаётся от Gateway / BFF) + RBAC + ABAC по владельцу ресурса + audit log для admin.

   Спроси, если непонятно. По умолчанию для UCP — **Domain Service**.

3. **Подключить зависимости:**

   ```kotlin
   implementation("org.springframework.boot:spring-boot-starter-security")
   implementation("org.springframework.boot:spring-boot-starter-oauth2-resource-server")
   ```

4. **Сгенерировать `SecurityConfig`** (`AUTH-4`, `AUTH-7`):

   ```java
   @Configuration
   @EnableMethodSecurity
   public class SecurityConfig {

       @Bean
       SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
           http
               .csrf(AbstractHttpConfigurer::disable)
               .authorizeHttpRequests(auth -> auth
                   .requestMatchers("/actuator/health", "/actuator/prometheus").permitAll()
                   .anyRequest().authenticated())
               .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
               .oauth2ResourceServer(oauth -> oauth
                   .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthenticationConverter())));
           return http.build();
       }

       private JwtAuthenticationConverter jwtAuthenticationConverter() {
           var authorities = new JwtGrantedAuthoritiesConverter();
           authorities.setAuthorityPrefix("ROLE_");
           authorities.setAuthoritiesClaimName("realm_access.roles");
           var converter = new JwtAuthenticationConverter();
           converter.setJwtGrantedAuthoritiesConverter(authorities);
           return converter;
       }
   }
   ```

5. **`AuthenticatedX`-хелперы** (по одному на каждую задействованную роль):

   ```java
   @Component
   public class AuthenticatedCustomer {
       public CustomerId currentCustomerId() {
           var jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
           return CustomerId.of(UUID.fromString(jwt.getSubject()));
       }
   }
   ```

6. **`@Component("access")`** для нетривиального ABAC (если есть ≥ 2 эндпоинта с проверкой владения):

   ```java
   @Component("access")
   public class AccessPolicy {
       private final OrderRepository orders;

       public boolean canViewOrder(UUID orderId, Authentication auth) {
           var jwt = (Jwt) auth.getPrincipal();
           var order = orders.findById(OrderId.of(orderId)).orElse(null);
           if (order == null) return false;
           if (auth.getAuthorities().stream().anyMatch(a -> "ROLE_admin".equals(a.getAuthority()))) return true;
           return order.customerId().value().toString().equals(jwt.getSubject());
       }
   }
   ```

7. **На каждом REST-эндпоинте** — `@PreAuthorize` (`AUTH-9`):

   - Прямая проверка роли: `@PreAuthorize("hasRole('customer')")`.
   - Проверка владельца через бин: `@PreAuthorize("@access.canViewOrder(#id, authentication)")`.

8. **Audit log для admin** (`AUTH-15`):

   - Таблица `<bc>_audit_log` (шаблон в спеке §3.5).
   - Аспект `@Around("@within(InboundAdapter) && execution(* *(..))")`, который проверяет роль `admin` и пишет строку. Или явный вызов в Handler.

9. **Идемпотентность** (`AUTH-19`) — для денежных команд:

   - Заголовок `Idempotency-Key` в OpenAPI обязательный.
   - Таблица `idempotency_keys` (шаблон).
   - Handler сначала проверяет ключ, потом исполняет команду; в той же транзакции пишет ключ.

10. **PII / секреты** (`AUTH-16`..`AUTH-18`):

    - Logback-фильтр на маскирование email / phone / cardNumber (генерируй стандартный `MaskingPatternLogger`).
    - `RestControllerAdvice`: переписывай `cause.getMessage()` на статический title по коду ошибки (никогда не пробрасывай).
    - `application-prod.yml` — только плейсхолдеры (`${KAFKA_PASSWORD}`); секреты — внешние.

11. **Структура вывода:**

    1. **Определённый слой** + краткий обзор (1–2 абзаца).
    2. **Дерево файлов** новых файлов.
    3. **Каждый файл** в своём code block с путём.
    4. **Заметки по реализации**: что нужно в `application.yml` (`spring.security.oauth2.resourceserver.jwt.jwk-set-uri`), какие переменные окружения, какие тесты добавить (см. `ucp-test-design`).

$ARGUMENTS
