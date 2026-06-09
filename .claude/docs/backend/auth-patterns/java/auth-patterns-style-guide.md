# Auth Patterns — Style Guide

Правила авторизации и аутентификации для сервисов на Use Case Pattern.
Каждое правило имеет код вида `AUTH-N` — скиллы `ucp-auth-review`
и `ucp-auth-design` цитируют его в findings.

Скилл намеренно **узкий**: покрывает то, что встречается в типовых
UCP-сервисах (REST за JWT, BFF + Domain Service, маркетплейс из кейса).
OWASP Top 10, криптография ключей, фроды — вне его.

---

## 1. Где какая проверка делается

`AUTH-1` **Gateway / API edge** делает _аутентификацию_: валидация JWT (подпись, `exp`, `iss`, `aud`) и rate limiting. Прокидывает identity в downstream-сервисы.

`AUTH-2` **BFF / Application Layer** делает грубую _авторизацию по роли_ (RBAC): `@PreAuthorize("hasRole('ADMIN')")`, фильтрация endpoint-ов.

`AUTH-3` **Domain Service** делает _авторизацию по ресурсу_ (ABAC): `order.customerId == jwt.sub`, бизнес-правила. **Никогда не выносится на Gateway** — Gateway не знает доменную модель.

---

## 2. JWT validation

`AUTH-4` JWT проверяется через `oauth2ResourceServer().jwt()` Spring Security. Кастомный фильтр **запрещён** — это анти-паттерн, маскирующий ошибки.

```java
http.oauth2ResourceServer(oauth -> oauth
    .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtAuthConverter())));
```

`AUTH-5` JWK Set тянется из IdP по URL `spring.security.oauth2.resourceserver.jwt.jwk-set-uri`. Кеш по умолчанию 5 минут. Вручную распаковывать ключи **запрещено**.

`AUTH-6` При невалидной подписи / просроченном `exp` сервис возвращает **401**, не 403. 401 = «не аутентифицирован»; 403 = «прав не хватает». Путать запрещено.

---

## 3. RBAC: маппинг ролей

`AUTH-7` Роли в JWT кладутся IdP в `realm_access.roles` (Keycloak) или `scope` (стандартный OAuth2). **На вход handler-а они приходят как `SimpleGrantedAuthority` с префиксом `ROLE_`** — через `JwtAuthenticationConverter`:

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

`AUTH-8` Разрешённые роли в нашей методологии: `customer`, `seller`, `admin`, `system`. Любая другая роль появляется только через пересмотр Bounded Context.

`AUTH-9` На каждом REST-endpoint **обязательна** аннотация `@PreAuthorize("hasRole(...)")` или `@PreAuthorize("hasAnyRole(...)")`. Endpoint без проверки роли — критическое нарушение.

---

## 4. ABAC: владение ресурсом

`AUTH-10` Когда команда / запрос работают с агрегатом по id — **обязателен ABAC по владению**. Реализуется одним из двух способов:

- **`@PreAuthorize("@access.canEditOrder(#id, authentication.principal)")`** — для простых случаев.
- Внутри Handler-а: загрузить агрегат, сравнить `aggregate.<ownerId>` с `jwt.sub`, бросить `FORBIDDEN` если не совпало.

`AUTH-11` ABAC-логика выносится в `@Component("access")` бин или в Handler — но **не размазывается** по контроллерам.

`AUTH-12` Для роли `admin` ABAC по умолчанию **обходится** (полный доступ), но каждое действие admin **обязательно** пишется в audit log (`AUTH-15`).

---

## 5. Service-to-service

`AUTH-13` Сервис-к-сервису общение использует один из двух способов:

- **mTLS** (рекомендуется): двусторонний TLS на Kubernetes Service Mesh / Istio.
- **Client Credentials Flow** (`grant_type=client_credentials`): сервис получает свой `access_token` от IdP с `scope=service:operation`.

`AUTH-14` Внутренние клиенты в `adapter-out-*` **никогда** не делают `RestTemplate.exchange(...)` без mTLS / `Bearer`-заголовка. Анонимный inter-service трафик — критическое нарушение.

---

## 6. Аудит admin-команд

`AUTH-15` Каждая команда от роли `admin`, изменяющая состояние агрегата, **обязана** писать строку в `*_audit_log` таблицу с полями: кто (`actor_id`), когда (`occurred_at`), что (`action`), к чему (`order_id`), детали (`metadata` JSONB). Реализация — `@Around`-аспект или явный вызов в Handler.

---

## 7. PII и секреты

`AUTH-16` PII-поля (email, phone, ФИО, адрес) **не попадают**:
- в логи (даже на уровне DEBUG);
- в `Exception.getMessage()` и далее в ProblemDetails.detail;
- в Kafka-события (передавать только id, payload подгружается потребителем по запросу).

`AUTH-17` Секреты (`spring.security.oauth2.client.registration.*.client-secret`, JDBC-пароли, ключи шлюзов) **никогда** не коммитятся в git. Только через `application-${profile}.yml` в Vault / SealedSecrets.

`AUTH-18` `RestControllerAdvice` для `OrderDomainException` (и аналогов) **не выводит** `cause.getMessage()` в `detail` — только заранее заданное сообщение по коду.

---

## 8. Идемпотентность как часть auth-контракта

`AUTH-19` Любая команда, меняющая деньги или резерв (`CreateOrder`, `ConfirmPayment`, `Refund...`), **обязана** требовать заголовок `Idempotency-Key`. Повторный вызов с тем же ключом возвращает прежний результат, а не дубль (см. BR-010 в спеке Order).

---

## 9. Хранение токенов на клиенте (информативно для BFF/SPA)

`AUTH-20` Для SPA — **HttpOnly + Secure + SameSite=Lax cookie** (либо session-cookie у BFF, либо JWT-в-cookie). `localStorage` запрещён.

`AUTH-21` Refresh-токены — **с rotation**: при каждом обновлении старый инвалидируется. При повторном использовании старого RT — компрометация, инвалидируется вся цепочка.

---

## 10. Чек-лист обзора

| Группа | Правила |
|---|---|
| Где какая проверка | `AUTH-1`–`AUTH-3` |
| JWT validation | `AUTH-4`–`AUTH-6` |
| RBAC | `AUTH-7`–`AUTH-9` |
| ABAC | `AUTH-10`–`AUTH-12` |
| Service-to-service | `AUTH-13`–`AUTH-14` |
| Аудит admin | `AUTH-15` |
| PII / секреты / логи | `AUTH-16`–`AUTH-18` |
| Идемпотентность | `AUTH-19` |
| Клиентская сторона (BFF/SPA) | `AUTH-20`–`AUTH-21` |
