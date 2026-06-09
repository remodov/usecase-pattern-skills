# Auth Patterns — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/auth-patterns-style-guide.md` (Spring Security + OAuth2 Resource Server) и
> `python/auth-patterns-style-guide.md` (FastAPI Depends + PyJWT/authlib + JWKS); открывай нужный точечно.
> Коды: `AUTH-<N>` — обязательно. X-кодов нет; запреты вшиты в формулировки. **Коды общие для всех языков** —
> меняется механизм (`@PreAuthorize`/`oauth2ResourceServer` ↔ FastAPI-зависимости + JWKS-клиент).
> Скилл намеренно узкий: REST за JWT, BFF + Domain Service. OWASP Top 10, криптография ключей, фроды — вне его.

## 1. Где какая проверка делается
**MUST:**
- **AUTH-1.** Gateway / API edge делает **аутентификацию**: валидация JWT (подпись, `exp`, `iss`, `aud`) + rate limiting; прокидывает identity в downstream.
- **AUTH-2.** BFF / Application Layer делает грубую **авторизацию по роли** по роли (RBAC): декларативная проверка роли на эндпоинте (Java: `@PreAuthorize`; Python: `Depends(require_roles)`).
- **AUTH-3.** Domain Service делает **авторизацию по ресурсу** (ABAC): `order.customerId == jwt.sub`, бизнес-правила. Никогда не на Gateway — он не знает доменную модель.

## 2. JWT validation
**MUST:**
- **AUTH-4.** JWT проверяется библиотекой resource-server (Java: `oauth2ResourceServer().jwt()`; Python: PyJWT/authlib + JWKS). Самописный парсинг подписи запрещён.
- **AUTH-5.** JWK Set тянется из IdP по `jwk-set-uri` (кеш 5 мин); вручную распаковывать ключи запрещено.
- **AUTH-6.** Невалидная подпись / просроченный `exp` → **401** (не аутентифицирован), не 403 (прав не хватает). Путать запрещено.

## 3. RBAC: маппинг ролей
**MUST:**
- **AUTH-7.** Роли из JWT (`realm_access.roles` Keycloak / `scope` OAuth2) маппятся в authorities/роли через конвертер claim'ов библиотеки.
- **AUTH-8.** Разрешённые роли: `customer`, `seller`, `admin`, `system`. Любая другая — только через пересмотр Bounded Context.
- **AUTH-9.** На каждом REST-endpoint обязательна декларативная проверка роли (Java: `@PreAuthorize`; Python: `Depends(require_roles)`). Endpoint без проверки роли — критическое нарушение.

## 4. ABAC: владение ресурсом
**MUST:**
- **AUTH-10.** Команда/запрос с агрегатом по id — обязателен ABAC по владению: декларативная проверка владения (Java: `@PreAuthorize("@access...")`; Python: проверка в Handler) либо сравнение `aggregate.<ownerId>` с `jwt.sub` в Handler с `FORBIDDEN`.
- **AUTH-11.** ABAC-логика — в выделенном access-компоненте или Handler, не размазана по контроллерам.
- **AUTH-12.** Роль `admin` обходит ABAC (полный доступ), но каждое действие обязательно в audit log (`AUTH-15`).

## 5. Service-to-service
**MUST:**
- **AUTH-13.** Сервис-к-сервису: mTLS (рекомендуется, Service Mesh / Istio) либо Client Credentials Flow (`grant_type=client_credentials`, `scope=service:operation`).
- **AUTH-14.** Внутренние клиенты в `adapter-out-*` никогда не делают вызов без mTLS / `Bearer`-заголовка. Анонимный inter-service трафик — критическое нарушение.

## 6. Аудит admin-команд
**MUST:**
- **AUTH-15.** Каждая state-changing команда от `admin` обязана писать строку в `*_audit_log`: `actor_id`, `occurred_at`, `action`, `<aggregate>_id`, `metadata` JSONB. Реализация — аспект/декоратор или явный вызов в Handler.

## 7. PII и секреты
**MUST:**
- **AUTH-16.** PII (email, phone, ФИО, адрес) не попадает в логи (даже DEBUG), в текст исключения / `problem.detail`, в Kafka-события (только id, payload подгружается потребителем).
- **AUTH-17.** Секреты (client-secret, JDBC-пароли, ключи шлюзов) никогда не в git — только через `application-${profile}.yml` в Vault / SealedSecrets.
- **AUTH-18.** Edge exception-handler для domain-exception не выводит текст причины в `detail` — только заранее заданное сообщение по коду.

## 8. Идемпотентность как часть auth-контракта
**MUST:**
- **AUTH-19.** Любая команда, меняющая деньги/резерв (`CreateOrder`, `ConfirmPayment`, `Refund…`), обязана требовать `Idempotency-Key`; повторный вызов с тем же ключом возвращает прежний результат, не дубль.

## 9. Хранение токенов на клиенте (BFF/SPA)
**MUST:**
- **AUTH-20.** Для SPA — HttpOnly + Secure + SameSite=Lax cookie (session-cookie у BFF или JWT-в-cookie). `localStorage` запрещён.
- **AUTH-21.** Refresh-токены с rotation: при обновлении старый инвалидируется; повторное использование старого RT — компрометация, инвалидируется вся цепочка.
