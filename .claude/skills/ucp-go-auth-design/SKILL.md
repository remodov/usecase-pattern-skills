---
name: ucp-go-auth-design
lang: go
description: Зашаблонить auth Go-сервиса (net/http + chi) по UCP — JWT-валидация через golang-jwt/jwt/v5 + keyfunc JWKS-кеш, RBAC через chi-middleware RequireRoles, ABAC-AccessPolicy в core, audit-log admin-команд sqlc, секреты envconfig.
when_to_use: Триггеры — «настрой auth в Go», «JWT-валидация на chi», «RBAC/ABAC в Go-сервисе». При старте сервиса или добавлении auth.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Auth Patterns — проектирование (Go / net/http + chi)

Ты проектируешь auth по **контракту** `backend/auth-patterns/spec.md` (`AUTH-*`) и **Go-реализации** `backend/auth-patterns/references/go/implementation.md`.
Помни: в Go ошибки — значения; «зависимость» = конструкторная DI; «декоратор» = chi-middleware;
«resource-server библиотека» = `golang-jwt/jwt/v5` + `MicahParks/keyfunc/v3`.

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные:
   `backend/usecase-pattern/go/...` (ABAC в Handler), `backend/error-handling/go/...`
   (401/403-mapping через `apperr.Kind`, не светить cause), `backend/observability/go/...`
   (`auth-patterns/no-pii-in-logs-and-events` PII в slog), `backend/go/go-bootstrap/...` (секреты/envconfig).

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Go:
   - `core/` — домен + `core/apperr/` + `core/audit/` + `core/<aggregate>/access.go`.
   - `adapters/in/http/security/` — `JWTValidator`, `Principal`.
   - `adapters/in/http/middleware/` — `AuthN`, `RequireRoles`, `RequireIdempotencyKey`.
   - `adapters/in/http/httperr/` — `sanitize` (скрывает cause).
   - `adapters/out/<system>/` — outbound-клиенты с `oauth2.TokenSource` или mTLS.

3. **Где** (`AUTH-1..3`): edge/chi-middleware — аутентификация (JWT); группа роутов — RBAC по роли;
   domain-handler — ABAC по ресурсу.

4. **JWT validation** (`AUTH-4..6`): `JWTValidator` на `golang-jwt/jwt/v5` + `MicahParks/keyfunc/v3`
   (JWKS-кеш ~5м); проверка подписи/`exp`/`iss`/`aud`; невалидный → `AuthError{Kind: Unauthenticated}`
   → **401**. `AuthN`-middleware кладёт `*Principal` в `context.Context`. Самописный парсинг запрещён.

5. **RBAC** (`AUTH-7..9`): роли из `realm_access.roles` (Keycloak) или `scope` (OAuth2) → `Principal.Roles`
   в `extractRoles`; `RequireRoles("customer")` на каждой chi-группе; роли `customer`/`seller`/`admin`/`system`.

6. **ABAC** (`AUTH-10..12`): `AccessPolicy` в `core/<aggregate>/` — `CheckOwnership(aggregate, principal) error`;
   `admin` обходит + Handler пишет audit; нарушение → `ForbiddenError` (Kind Forbidden → 403).

7. **S2S/Audit/PII/Secrets** (`AUTH-13..18`): mTLS или `oauth2.TokenSource` (Client Credentials) в
   `adapters/out/*`; audit-log admin-команд через `audit.Logger`-порт + sqlc-adapter в `*_audit_log`;
   PII не в `error.Error()`/`slog`-атрибутах/Kafka-событиях; секреты через `envconfig` (env/Vault),
   не в git; edge `sanitize` не пишет `err.Error()` в `problem.detail`.

8. **Idempotency/Tokens** (`AUTH-19..21`): money-команды требуют `Idempotency-Key`-заголовок через
   `RequireIdempotencyKey`-middleware; дубль проверяется через redis-ключ или idempotency-таблицу в PostgreSQL;
   BFF — AT + RT в HttpOnly + Secure + SameSite cookie; RT с rotation (повтор старого → `RevokeFamily`).
   Самопроверка (§10 справочник) + предложи `ucp-go-auth-review`.

## Производимый код

Полные `.go`-файлы, `gofmt`; без комментариев — соответствие выражается именами/типами/структурой;
коды правил в комментариях **не цитируй**.

- `core/apperr/autherr.go` — `AuthError` (`Kind: Unauthenticated`), `ForbiddenError` (`Kind: Forbidden`); `KindOf` + edge-renderer обновляются.
- `adapters/in/http/security/jwt.go` — `Principal`, `JWTValidator`, конструктор `NewJWTValidator`.
- `adapters/in/http/security/extract.go` — `extractRoles(jwt.MapClaims) []string`.
- `adapters/in/http/middleware/authn.go` — `AuthN(v *JWTValidator) func(http.Handler) http.Handler`; кладёт Principal в ctx.
- `adapters/in/http/middleware/rbac.go` — `RequireRoles(roles ...string)`, `PrincipalFrom(ctx)`.
- `adapters/in/http/middleware/idempotency.go` — `RequireIdempotencyKey` для money-команд.
- `adapters/in/http/router.go` — chi-роутер с `AuthN` на всём + `RequireRoles` на группах.
- `core/<aggregate>/access.go` — `AccessPolicy` с `CheckOwnership`.
- `core/<aggregate>/handler/<use_case>.go` — ABAC + audit в Handler (только если admin-команда).
- `core/audit/audit.go` — `LogEntry`, `Logger`-порт.
- `adapters/out/audit/pg_audit.go` — sqlc-adapter, пишет в `*_audit_log`.
- `adapters/out/<system>/client.go` — outbound с `oauth2.TokenSource` или mTLS.
- `cmd/app/config.go` — `Config` через `envconfig`; секреты `required`.

## Антипаттерны, которые НЕ генерировать

- Самописный `jwt.Parse` без `keyfunc`/JWKS-кеша (`auth-patterns/token-validated-by-library`/`auth-patterns/token-validated-by-library`); `WithExpirationRequired()` пропущен.
- 403 вместо 401 при невалидном токене (`auth-patterns/401-not-403`); `AuthError.Kind != Unauthenticated`.
- Роут без `RequireRoles` (`auth-patterns/every-endpoint-has-role-check`); ABAC в middleware/контроллере вместо `AccessPolicy`/Handler (`auth-patterns/ownership-checked-in-domain`).
- `admin`-команда без записи в audit log (`auth-patterns/admin-bypass-is-audited`/`auth-patterns/admin-commands-write-audit-log`).
- Outbound-клиент без `Authorization`/mTLS (`auth-patterns/service-to-service-authenticated`); анонимный inter-service трафик.
- PII (`email`, `phone`, ФИО) в `error.Error()`, `slog.String(...)`, Kafka-payload (`auth-patterns/no-pii-in-logs-and-events`).
- Секреты в `config.go` hardcode или в git (`auth-patterns/no-secrets-in-repository`); `err.Error()` в `problem.detail` (`auth-patterns/error-response-hides-cause`).
- Money-команда без `Idempotency-Key` middleware (`auth-patterns/money-commands-need-idempotency-key`); RT в `localStorage` (`auth-patterns/token-in-httponly-cookie`); refresh без rotation (`auth-patterns/refresh-token-rotation`).

После работы скилла — обязательно `ucp-go-auth-review`.

$ARGUMENTS
