---
name: ucp-go-auth-review
lang: go
description: Ревью аутентификации/авторизации Go-сервиса (net/http + chi) по UCP — golang-jwt + keyfunc JWKS, RequireRoles-middleware, ABAC в Handler/AccessPolicy, s2s oauth2.TokenSource, audit sqlc, PII/секреты envconfig, idempotency-key для money.
when_to_use: Изменения в security/*.go, chi-middleware, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике, outbound-клиентах s2s.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Auth Patterns (Go / net/http + chi)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Go-реализации** `backend/auth-patterns/references/go/implementation.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/spec.md`** + **`backend/auth-patterns/references/go/implementation.md`**.
- Парные: `backend/error-handling/go/...` (401/403, `apperr.Kind`, `errors.As`), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `distributed-patterns` (`auth-patterns/money-commands-need-idempotency-key`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй коды (`auth-patterns/every-endpoint-has-role-check`, `auth-patterns/no-pii-in-logs-and-events`), не префикс.

2. **Скоп.** `adapters/in/http/security/` (`JWTValidator`, `Principal`, `extractRoles`), `adapters/in/http/middleware/` (`AuthN`, `RequireRoles`, `RequireIdempotencyKey`), `core/<aggregate>/access.go` (ABAC), `core/<aggregate>/handler/` (ABAC + audit), `adapters/out/*` (s2s-клиенты), `cmd/app/config.go` (секреты); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** `AuthN`-middleware аутентифицирует на edge, `RequireRoles` на chi-группе (BFF), ABAC в domain-handler/`AccessPolicy` (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через `github.com/golang-jwt/jwt/v5` + `github.com/MicahParks/keyfunc/v3`; самописный парсинг подписи (`jwt.ParseWithClaims` без `WithExpirationRequired()`) → нарушение `auth-patterns/token-validated-by-library`; JWKS-keyfunc с кешем — `auth-patterns/token-validated-by-library`; невалидная подпись/просроченный `exp` → 401, не 403 → `auth-patterns/401-not-403`.
   - **RBAC (`AUTH-7..9`):** роли из `realm_access.roles` (Keycloak) или `scope` (OAuth2) в `extractRoles` → `Principal.Roles` — `auth-patterns/roles-from-token-claims`; роли из разрешённого набора (`customer`/`seller`/`admin`/`system`) — `auth-patterns/roles-from-token-claims`; `RequireRoles` на **каждой** chi-группе — без проверки → критично (`auth-patterns/every-endpoint-has-role-check`).
   - **ABAC (`AUTH-10..12`):** `order.CustomerID == principal.Sub` в Handler/`AccessPolicy` — `auth-patterns/ownership-checked-in-domain`; ABAC-логика размазана по контроллерам → нарушение `auth-patterns/ownership-checked-in-domain`; `admin` обходит ABAC + audit → `auth-patterns/admin-bypass-is-audited`.
   - **S2S (`AUTH-13..14`):** mTLS (Istio/Service Mesh) или Client Credentials через `oauth2.TokenSource` (`golang.org/x/oauth2/clientcredentials`); анонимный inter-service вызов (голый `http.DefaultClient` без `Authorization`) → критично (`auth-patterns/service-to-service-authenticated`).
   - **Audit (`auth-patterns/admin-commands-write-audit-log`):** каждая admin state-changing команда вызывает `audit.Logger.Log(...)` с `actor_id`/`occurred_at`/`action`/`aggregate_id`/`metadata` через sqlc-адаптер.
   - **PII/Secrets (`AUTH-16..18`):** PII (email, phone, ФИО) в `slog`-атрибутах / `error.Error()` / Kafka-событиях → критично (`auth-patterns/no-pii-in-logs-and-events`); секреты в git / hardcode в `config.go` → критично (`auth-patterns/no-secrets-in-repository`); `err.Error()` напрямую в `problem.detail` через edge-renderer → `auth-patterns/error-response-hides-cause`.
   - **Idempotency (`auth-patterns/money-commands-need-idempotency-key`):** money-команды (`CreateOrder`, `ConfirmPayment`, `Refund`) без `RequireIdempotencyKey`-middleware → критично (`auth-patterns/money-commands-need-idempotency-key`).
   - **Токены на клиенте (`AUTH-20..21`):** AT/RT в `localStorage` → критично (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (старый RT не инвалидируется) → `auth-patterns/refresh-token-rotation`.

4. **Cross-check:** 401/403-mapping и `apperr.Kind` → `ucp-go-error-handling-review`; PII в `slog`-спанах → `ucp-go-observability-review`; idempotency-таблица/redis-ключ → `ucp-go-distributed-review`. Проверь `Grep` на `http.DefaultClient` без `Authorization`, `jwt.Parse` без `WithExpirationRequired`, прямые строки ролей вне middleware.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — endpoint без `RequireRoles` (`auth-patterns/every-endpoint-has-role-check`), самописная JWT-валидация без подписи/claims (`auth-patterns/token-validated-by-library`), анонимный s2s (`auth-patterns/service-to-service-authenticated`), PII в `slog`/`error.Error()`/событиях (`auth-patterns/no-pii-in-logs-and-events`), секреты в git (`auth-patterns/no-secrets-in-repository`), money без `RequireIdempotencyKey` (`auth-patterns/money-commands-need-idempotency-key`), AT/RT в `localStorage` (`auth-patterns/token-in-httponly-cookie`).
   - **Предупреждение** — 403 вместо 401 на невалидный токен (`auth-patterns/401-not-403`), ABAC в контроллере вместо `AccessPolicy`/Handler (`auth-patterns/ownership-checked-in-domain`), admin без audit (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`), `err.Error()` в `detail` (`auth-patterns/error-response-hides-cause`), refresh без rotation (`auth-patterns/refresh-token-rotation`).
   - **Замечание** — keyfunc без явного TTL кеша (`auth-patterns/token-validated-by-library`), роль вне разрешённого набора (`auth-patterns/roles-from-token-claims`), `oauth2.TokenSource` без `ReuseTokenSource` (лишние запросы к IdP).

## Что не входит

- 401/403-mapping, `apperr.Kind`, `errors.As` — `ucp-go-error-handling-review`. PII в логах/спанах — `ucp-go-observability-review`.
- SAST/CVE/контейнер/криптография ключей — `ucp-go-security-review`. Idempotency-таблица/redis — `ucp-go-distributed-review`.

$ARGUMENTS
