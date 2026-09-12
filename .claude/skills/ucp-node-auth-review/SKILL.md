---
name: ucp-node-auth-review
lang: node
description: Ревью аутентификации/авторизации NestJS-сервиса (Node) по UCP — JwtStrategy с jwks-rsa-кешем, RBAC через @Roles/RolesGuard + @Public, ABAC в Handler/AccessPolicy, s2s mTLS, audit-log, PII и секреты, Idempotency-Key для money.
when_to_use: Изменения в JwtStrategy, guards, контроллерах, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Auth Patterns (Node / NestJS + passport-jwt/jwks-rsa)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Node-реализации** `backend/auth-patterns/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/spec.md`** + **`backend/auth-patterns/references/node/implementation.md`**.
- Парные: `backend/error-handling/node/...` (401/403, cause), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `distributed-patterns` (`auth-patterns/money-commands-need-idempotency-key`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`auth-patterns/every-endpoint-has-role-check`, `auth-patterns/no-pii-in-logs-and-events`), не префикс.

2. **Скоп.** `JwtStrategy`/guards (`JwtAuthGuard`/`RolesGuard`/`@Roles`/`@Public`), `APP_GUARD`-регистрация, контроллеры, Handler-ABAC, `AccessPolicy`, конфиги секретов, audit-interceptor, outbound-клиенты (s2s); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** аутентификация на edge, RBAC на BFF, ABAC в domain-handler (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через `passport-jwt`+`jwks-rsa`, не самописный `jwt.decode` без подписи/claims (`auth-patterns/token-validated-by-library`); ручная распаковка ключей / JWKS без кеша (`auth-patterns/token-validated-by-library`); 403 вместо 401 на невалидный токен → нарушение `auth-patterns/401-not-403`.
   - **RBAC (`AUTH-7..9`):** роли из claim в `Principal` (`JwtStrategy.validate`); `@Roles(...)` или явный `@Public()` на **каждом** endpoint — без проверки → критично (`auth-patterns/every-endpoint-has-role-check`); роли из разрешённого набора (`auth-patterns/roles-from-token-claims`).
   - **ABAC (`AUTH-10..12`):** сравнение владельца с `principal.sub` в Handler/`AccessPolicy` (размазан по контроллерам → `auth-patterns/ownership-checked-in-domain`); admin обходит + audit (`auth-patterns/admin-bypass-is-audited`).
   - **S2S (`AUTH-13..14`):** mTLS/Client Credentials; анонимный inter-service вызов (axios/undici без `Bearer`/mTLS) → критично (`auth-patterns/service-to-service-authenticated`).
   - **Audit (`auth-patterns/admin-commands-write-audit-log`):** admin state-changing команды пишут `*_audit_log` (interceptor или явный вызов в Handler).
   - **PII/Secrets (`AUTH-16..18`):** PII в логах (нет pino `redact`)/exception/событиях → критично (`auth-patterns/no-pii-in-logs-and-events`); секреты в git/`.env`-в-репо → критично (`auth-patterns/no-secrets-in-repository`); `String(cause)` в `detail` (`auth-patterns/error-response-hides-cause`).
   - **Idempotency/Tokens (`AUTH-19..21`):** money-команда без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`); токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (`auth-patterns/refresh-token-rotation`).

4. **Cross-check:** 401/403-mapping и не-светить-cause — `ucp-node-error-handling-review`; PII в логах — `ucp-node-observability-review`; idempotency-таблица — `ucp-node-distributed-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — endpoint без проверки роли (`auth-patterns/every-endpoint-has-role-check`), самописная JWT-валидация без подписи/claims (`auth-patterns/token-validated-by-library`), анонимный s2s (`auth-patterns/service-to-service-authenticated`), PII в логах/событиях (`auth-patterns/no-pii-in-logs-and-events`), секреты в git (`auth-patterns/no-secrets-in-repository`), money без `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`), токен в `localStorage` (`auth-patterns/token-in-httponly-cookie`).
   - **Предупреждение** — 403 вместо 401 (`auth-patterns/401-not-403`), ABAC размазан по контроллерам (`auth-patterns/ownership-checked-in-domain`), admin без audit (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`), `String(cause)` в `detail` (`auth-patterns/error-response-hides-cause`), refresh без rotation (`auth-patterns/refresh-token-rotation`).
   - **Замечание** — JWKS без явного кеша (`auth-patterns/token-validated-by-library`), роль вне разрешённого набора (`auth-patterns/roles-from-token-claims`).

## Что не входит

- 401/403-mapping/problem+json — `ucp-node-error-handling-review`. PII в логах/спанах — `ucp-node-observability-review`.
- SAST/CVE/контейнер/криптография — `ucp-node-security-review`. Idempotency-таблица — `ucp-node-distributed-review`.

$ARGUMENTS
