---
name: ucp-node-auth-review
lang: node
description: Ревью аутентификации/авторизации NestJS-сервиса (Node) по UCP (коды AUTH-*) — JwtStrategy с jwks-rsa-кешем, RBAC через @Roles/RolesGuard + @Public, ABAC в Handler/AccessPolicy, s2s mTLS, audit-log, PII и секреты, Idempotency-Key для money.
when_to_use: Изменения в JwtStrategy, guards, контроллерах, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Auth Patterns (Node / NestJS + passport-jwt/jwks-rsa)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-*`) и **Node-реализации** `backend/auth-patterns/node/auth-patterns-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/auth-patterns-rules.md`** + **`backend/auth-patterns/node/auth-patterns-style-guide.md`**.
- Парные: `backend/error-handling/node/...` (401/403, cause), `observability` (`AUTH-16` PII), `distributed-patterns` (`AUTH-19`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`AUTH-9`, `AUTH-16`), не префикс.

2. **Скоп.** `JwtStrategy`/guards (`JwtAuthGuard`/`RolesGuard`/`@Roles`/`@Public`), `APP_GUARD`-регистрация, контроллеры, Handler-ABAC, `AccessPolicy`, конфиги секретов, audit-interceptor, outbound-клиенты (s2s); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** аутентификация на edge, RBAC на BFF, ABAC в domain-handler (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через `passport-jwt`+`jwks-rsa`, не самописный `jwt.decode` без подписи/claims (`AUTH-4`); ручная распаковка ключей / JWKS без кеша (`AUTH-5`); 403 вместо 401 на невалидный токен → нарушение `AUTH-6`.
   - **RBAC (`AUTH-7..9`):** роли из claim в `Principal` (`JwtStrategy.validate`); `@Roles(...)` или явный `@Public()` на **каждом** endpoint — без проверки → критично (`AUTH-9`); роли из разрешённого набора (`AUTH-8`).
   - **ABAC (`AUTH-10..12`):** сравнение владельца с `principal.sub` в Handler/`AccessPolicy` (размазан по контроллерам → `AUTH-11`); admin обходит + audit (`AUTH-12`).
   - **S2S (`AUTH-13..14`):** mTLS/Client Credentials; анонимный inter-service вызов (axios/undici без `Bearer`/mTLS) → критично (`AUTH-14`).
   - **Audit (`AUTH-15`):** admin state-changing команды пишут `*_audit_log` (interceptor или явный вызов в Handler).
   - **PII/Secrets (`AUTH-16..18`):** PII в логах (нет pino `redact`)/exception/событиях → критично (`AUTH-16`); секреты в git/`.env`-в-репо → критично (`AUTH-17`); `String(cause)` в `detail` (`AUTH-18`).
   - **Idempotency/Tokens (`AUTH-19..21`):** money-команда без `Idempotency-Key` (`AUTH-19`); токен в `localStorage` (`AUTH-20`); refresh без rotation (`AUTH-21`).

4. **Cross-check:** 401/403-mapping и не-светить-cause — `ucp-node-error-handling-review`; PII в логах — `ucp-node-observability-review`; idempotency-таблица — `ucp-node-distributed-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — endpoint без проверки роли (`AUTH-9`), самописная JWT-валидация без подписи/claims (`AUTH-4`), анонимный s2s (`AUTH-14`), PII в логах/событиях (`AUTH-16`), секреты в git (`AUTH-17`), money без `Idempotency-Key` (`AUTH-19`), токен в `localStorage` (`AUTH-20`).
   - **Предупреждение** — 403 вместо 401 (`AUTH-6`), ABAC размазан по контроллерам (`AUTH-11`), admin без audit (`AUTH-12`/`AUTH-15`), `String(cause)` в `detail` (`AUTH-18`), refresh без rotation (`AUTH-21`).
   - **Замечание** — JWKS без явного кеша (`AUTH-5`), роль вне разрешённого набора (`AUTH-8`).

## Что не входит

- 401/403-mapping/problem+json — `ucp-node-error-handling-review`. PII в логах/спанах — `ucp-node-observability-review`.
- SAST/CVE/контейнер/криптография — `ucp-node-security-review`. Idempotency-таблица — `ucp-node-distributed-review`.

$ARGUMENTS
