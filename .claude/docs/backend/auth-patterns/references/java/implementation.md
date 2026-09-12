# Auth Patterns — реализация

Правила авторизации и аутентификации для сервисов на Use Case Pattern.
Каждое правило имеет код вида `AUTH-N` — скиллы `ucp-auth-review`
и `ucp-auth-design` цитируют его в findings.

Скилл намеренно **узкий**: покрывает то, что встречается в типовых
UCP-сервисах (REST за JWT, BFF + Domain Service, маркетплейс из кейса).
OWASP Top 10, криптография ключей, фроды — вне его.

---

## 1. Где какая проверка делается

`auth-patterns/checks-split-by-layer` **Gateway / API edge** делает _аутентификацию_: валидация JWT (подпись, `exp`, `iss`, `aud`) и rate limiting. Прокидывает identity в downstream-сервисы.

`auth-patterns/checks-split-by-layer` **BFF / Application Layer** делает грубую _авторизацию по роли_ (RBAC): `@PreAuthorize("hasRole('ADMIN')")`, фильтрация endpoint-ов.

`auth-patterns/checks-split-by-layer` **Domain Service** делает _авторизацию по ресурсу_ (ABAC): `order.customerId == jwt.sub`, бизнес-правила. **Никогда не выносится на Gateway** — Gateway не знает доменную модель.

---

## 2. JWT validation

`auth-patterns/token-validated-by-library` JWT проверяется через `oauth2ResourceServer().jwt()` Spring Security. Кастомный фильтр **запрещён** — это анти-паттерн, маскирующий ошибки.

```java
http.oauth2ResourceServer(oauth -> oauth
    .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthConverter())));
```

`auth-patterns/token-validated-by-library` JWK Set тянется из IdP по URL `spring.security.oauth2.resourceserver.jwt.jwk-set-uri`. Кеш по умолчанию 5 минут. Вручную распаковывать ключи **запрещено**.

`auth-patterns/401-not-403` При невалидной подписи / просроченном `exp` сервис возвращает **401**, не 403. 401 = «не аутентифицирован»; 403 = «прав не хватает». Путать запрещено.

---

## 3. RBAC: маппинг ролей

`auth-patterns/roles-from-token-claims` Роли в JWT кладутся IdP в `realm_access.roles` (Keycloak) или `scope` (стандартный OAuth2). **На вход handler-а они приходят как `SimpleGrantedAuthority` с префиксом `ROLE_`** — через `JwtAuthenticationConverter`:

```java
@Bean
JwtAuthenticationConverter jwtAuthConverter() {
    var authorities = new JwtGrantedAuthoritiesConverter();
    authorities.setAuthorityPrefix("ROLE_");
    authorities.setAuthoritiesClaimName("realm_access.roles");
    var converter = new JwtAuthenticationConverter();
    converter.setJwtGrantedAuthoritiesConverter(authorities);
    return converter;
}
```

`auth-patterns/roles-from-token-claims` Разрешённые роли в нашей методологии: `customer`, `seller`, `admin`, `system`. Любая другая роль появляется только через пересмотр Bounded Context.

`auth-patterns/every-endpoint-has-role-check` На каждом REST-endpoint **обязательна** аннотация `@PreAuthorize("hasRole(...)")` или `@PreAuthorize("hasAnyRole(...)")`. Endpoint без проверки роли — критическое нарушение.

---

## 4. ABAC: владение ресурсом

`auth-patterns/ownership-checked-in-domain` Когда команда / запрос работают с агрегатом по id — **обязателен ABAC по владению**. Реализуется одним из двух способов:

- **`@PreAuthorize("@access.canEditOrder(#id, authentication.principal)")`** — для простых случаев.
- Внутри Handler-а: загрузить агрегат, сравнить `aggregate.<ownerId>` с `jwt.sub`, бросить `FORBIDDEN` если не совпало.

`auth-patterns/ownership-checked-in-domain` ABAC-логика выносится в `@Component("access")` бин или в Handler — но **не размазывается** по контроллерам.

`auth-patterns/admin-bypass-is-audited` Для роли `admin` ABAC по умолчанию **обходится** (полный доступ), но каждое действие admin **обязательно** пишется в audit log (`auth-patterns/admin-commands-write-audit-log`).

---

## 5. Service-to-service

`auth-patterns/service-to-service-authenticated` Сервис-к-сервису общение использует один из двух способов:

- **mTLS** (рекомендуется): двусторонний TLS на Kubernetes Service Mesh / Istio.
- **Client Credentials Flow** (`grant_type=client_credentials`): сервис получает свой `access_token` от IdP с `scope=service:operation`.

`auth-patterns/service-to-service-authenticated` Внутренние клиенты в `adapter-out-*` **никогда** не делают `RestTemplate.exchange(...)` без mTLS / `Bearer`-заголовка. Анонимный inter-service трафик — критическое нарушение.

---

## 6. Аудит admin-команд

`auth-patterns/admin-commands-write-audit-log` Каждая команда от роли `admin`, изменяющая состояние агрегата, **обязана** писать строку в `*_audit_log` таблицу с полями: кто (`actor_id`), когда (`occurred_at`), что (`action`), к чему (`order_id`), детали (`metadata` JSONB). Реализация — `@Around`-аспект или явный вызов в Handler.

---

## 7. PII и секреты

`auth-patterns/no-pii-in-logs-and-events` PII-поля (email, phone, ФИО, адрес) **не попадают**:
- в логи (даже на уровне DEBUG);
- в `Exception.getMessage()` и далее в ProblemDetails.detail;
- в Kafka-события (передавать только id, payload подгружается потребителем по запросу).

`auth-patterns/no-secrets-in-repository` Секреты (`spring.security.oauth2.client.registration.*.client-secret`, JDBC-пароли, ключи шлюзов) **никогда** не коммитятся в git. Только через `application-${profile}.yml` в Vault / SealedSecrets.

`auth-patterns/error-response-hides-cause` `RestControllerAdvice` для доменных семейств (`OrderException` и аналогов) **не выводит** `cause.getMessage()` в `detail` — только заранее заданное сообщение по коду.

---

## 8. Идемпотентность как часть auth-контракта

`auth-patterns/money-commands-need-idempotency-key` Любая команда, меняющая деньги или резерв (`CreateOrder`, `ConfirmPayment`, `Refund...`), **обязана** требовать заголовок `Idempotency-Key`. Повторный вызов с тем же ключом возвращает прежний результат, а не дубль (см. BR-010 в спеке Order).

---

## 9. Хранение токенов на клиенте (информативно для BFF/SPA)

`auth-patterns/token-in-httponly-cookie` Для SPA — **HttpOnly + Secure + SameSite=Lax cookie** (либо session-cookie у BFF, либо JWT-в-cookie). `localStorage` запрещён.

`auth-patterns/refresh-token-rotation` Refresh-токены — **с rotation**: при каждом обновлении старый инвалидируется. При повторном использовании старого RT — компрометация, инвалидируется вся цепочка.

---

## 10. Чек-лист обзора

| Группа | Правила |
|---|---|
| Где какая проверка | `auth-patterns/checks-split-by-layer`–`auth-patterns/checks-split-by-layer` |
| JWT validation | `auth-patterns/token-validated-by-library`–`auth-patterns/401-not-403` |
| RBAC | `auth-patterns/roles-from-token-claims`–`auth-patterns/every-endpoint-has-role-check` |
| ABAC | `auth-patterns/ownership-checked-in-domain`–`auth-patterns/admin-bypass-is-audited` |
| Service-to-service | `auth-patterns/service-to-service-authenticated`–`auth-patterns/service-to-service-authenticated` |
| Аудит admin | `auth-patterns/admin-commands-write-audit-log` |
| PII / секреты / логи | `auth-patterns/no-pii-in-logs-and-events`–`auth-patterns/error-response-hides-cause` |
| Идемпотентность | `auth-patterns/money-commands-need-idempotency-key` |
| Клиентская сторона (BFF/SPA) | `auth-patterns/token-in-httponly-cookie`–`auth-patterns/refresh-token-rotation` |
