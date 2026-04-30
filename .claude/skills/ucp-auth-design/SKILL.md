---
name: ucp-auth-design
description: Scaffold Spring Security + OAuth2 Resource Server config for a UCP-style service — JWT validation, role mapping, RBAC on endpoints, ABAC helpers (`AuthenticatedX`, `@Component("access")`), audit log aspect, secrets layout, idempotency. Use when starting a new service or adding auth to an existing one.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Auth Patterns Design

You are scaffolding the security/auth layer for a Java/Spring service following the team's auth-patterns style guide.

## Instructions

1. **Read the style guide** from `.claude/docs/auth-patterns-style-guide.md`. Cite `AUTH-N` rules **в design-обосновании ответа пользователю**, но **не в комментариях сгенерённого кода** (`JS-7.3` в `java-style-guide.md`). Никаких `// AUTH-15`, `// AUTH-9` в исходниках — соответствие выражается через `@PreAuthorize`, наличие audit-таблицы, `JwtAuthenticationConverter` и т.д.

2. **Confirm the layer.** Determine:
   - **Gateway** — здесь только JWT validation + rate limiting. Сервис обычно не Gateway; если перед тобой именно Gateway — генерируешь правила маршрутизации, но не RBAC handler-ов.
   - **BFF** — JWT validation + RBAC по ролям, агрегация вызовов. Сессия в Redis при необходимости.
   - **Domain Service** — JWT validation (передаётся от Gateway/BFF) + RBAC + ABAC по владению ресурсом + audit log для admin.

   Спроси если непонятно. По умолчанию для UCP — **Domain Service**.

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

5. **`AuthenticatedX` хелперы** (по одному на роль, что задействована):

   ```java
   @Component
   public class AuthenticatedCustomer {
       public CustomerId currentCustomerId() {
           var jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
           return CustomerId.of(UUID.fromString(jwt.getSubject()));
       }
   }
   ```

6. **`@Component("access")`** для не-тривиального ABAC (если есть ≥ 2 эндпоинта с проверкой владения):

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

7. **На каждом REST-endpoint** — `@PreAuthorize` (`AUTH-9`):

   - Прямой роле-чек: `@PreAuthorize("hasRole('customer')")`.
   - Ownership через бин: `@PreAuthorize("@access.canViewOrder(#id, authentication)")`.

8. **Audit log для admin** (`AUTH-15`):

   - Таблица `<bc>_audit_log` (см. шаблон в спеке §3.5).
   - Аспект `@Around("@within(InboundAdapter) && execution(* *(..))")` который проверяет роль `admin` и пишет строку. Или явный вызов в Handler.

9. **Идемпотентность** (`AUTH-19`) — для денежных команд:

   - Header `Idempotency-Key` в OpenAPI обязательный.
   - Таблица `idempotency_keys` (см. шаблон).
   - Handler сначала чекает ключ, потом исполняет команду; в той же транзакции пишет ключ.

10. **PII / секреты** (`AUTH-16`..`AUTH-18`):

    - Logback фильтр на маскирование email/phone/cardNumber (генерируй стандартный `MaskingPatternLogger`).
    - `RestControllerAdvice`: переписывай `cause.getMessage()` на статический title по коду ошибки (никогда не пробрасывай).
    - `application-prod.yml` — только плейсхолдеры (`${KAFKA_PASSWORD}`); секреты — внешние.

11. **Output structure:**

    1. **Detected layer** + summary (1–2 параграфа).
    2. **File tree** новых файлов.
    3. **Каждый файл** в своём code block с путём.
    4. **Implementation notes**: что нужно в `application.yml` (`spring.security.oauth2.resourceserver.jwt.jwk-set-uri`), какие переменные окружения, какие тесты добавить (см. `ucp-test-design`).

$ARGUMENTS
