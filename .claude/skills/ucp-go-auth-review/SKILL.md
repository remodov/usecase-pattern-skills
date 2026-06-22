---
name: ucp-go-auth-review
lang: go
description: Ревью аутентификации/авторизации Go-сервиса (net/http + chi) по UCP (коды AUTH-*) — golang-jwt + keyfunc JWKS, RequireRoles-middleware, ABAC в Handler/AccessPolicy, s2s oauth2.TokenSource, audit sqlc, PII/секреты envconfig, idempotency-key для money.
when_to_use: Изменения в security/*.go, chi-middleware, Handler-ABAC, AccessPolicy, конфигах секретов, audit-логике, outbound-клиентах s2s.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Auth Patterns (Go / net/http + chi)

Ты ревьюишь auth на соответствие **контракту** `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-*`) и **Go-реализации** `backend/auth-patterns/go/auth-patterns-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/auth-patterns/auth-patterns-rules.md`** + **`backend/auth-patterns/go/auth-patterns-style-guide.md`**.
- Парные: `backend/error-handling/go/...` (401/403, `apperr.Kind`, `errors.As`), `observability` (`AUTH-16` PII), `distributed-patterns` (`AUTH-19`/`R-DIST-IDEM`).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй коды (`AUTH-9`, `AUTH-16`), не префикс.

2. **Скоп.** `adapters/in/http/security/` (`JWTValidator`, `Principal`, `extractRoles`), `adapters/in/http/middleware/` (`AuthN`, `RequireRoles`, `RequireIdempotencyKey`), `core/<aggregate>/access.go` (ABAC), `core/<aggregate>/handler/` (ABAC + audit), `adapters/out/*` (s2s-клиенты), `cmd/app/config.go` (секреты); `git diff`.

3. **Прогон.**
   - **Где (`AUTH-1..3`):** `AuthN`-middleware аутентифицирует на edge, `RequireRoles` на chi-группе (BFF), ABAC в domain-handler/`AccessPolicy` (не на gateway).
   - **JWT (`AUTH-4..6`):** валидация через `github.com/golang-jwt/jwt/v5` + `github.com/MicahParks/keyfunc/v3`; самописный парсинг подписи (`jwt.ParseWithClaims` без `WithExpirationRequired()`) → нарушение `AUTH-4`; JWKS-keyfunc с кешем — `AUTH-5`; невалидная подпись/просроченный `exp` → 401, не 403 → `AUTH-6`.
   - **RBAC (`AUTH-7..9`):** роли из `realm_access.roles` (Keycloak) или `scope` (OAuth2) в `extractRoles` → `Principal.Roles` — `AUTH-7`; роли из разрешённого набора (`customer`/`seller`/`admin`/`system`) — `AUTH-8`; `RequireRoles` на **каждой** chi-группе — без проверки → критично (`AUTH-9`).
   - **ABAC (`AUTH-10..12`):** `order.CustomerID == principal.Sub` в Handler/`AccessPolicy` — `AUTH-10`; ABAC-логика размазана по контроллерам → нарушение `AUTH-11`; `admin` обходит ABAC + audit → `AUTH-12`.
   - **S2S (`AUTH-13..14`):** mTLS (Istio/Service Mesh) или Client Credentials через `oauth2.TokenSource` (`golang.org/x/oauth2/clientcredentials`); анонимный inter-service вызов (голый `http.DefaultClient` без `Authorization`) → критично (`AUTH-14`).
   - **Audit (`AUTH-15`):** каждая admin state-changing команда вызывает `audit.Logger.Log(...)` с `actor_id`/`occurred_at`/`action`/`aggregate_id`/`metadata` через sqlc-адаптер.
   - **PII/Secrets (`AUTH-16..18`):** PII (email, phone, ФИО) в `slog`-атрибутах / `error.Error()` / Kafka-событиях → критично (`AUTH-16`); секреты в git / hardcode в `config.go` → критично (`AUTH-17`); `err.Error()` напрямую в `problem.detail` через edge-renderer → `AUTH-18`.
   - **Idempotency (`AUTH-19`):** money-команды (`CreateOrder`, `ConfirmPayment`, `Refund`) без `RequireIdempotencyKey`-middleware → критично (`AUTH-19`).
   - **Токены на клиенте (`AUTH-20..21`):** AT/RT в `localStorage` → критично (`AUTH-20`); refresh без rotation (старый RT не инвалидируется) → `AUTH-21`.

4. **Cross-check:** 401/403-mapping и `apperr.Kind` → `ucp-go-error-handling-review`; PII в `slog`-спанах → `ucp-go-observability-review`; idempotency-таблица/redis-ключ → `ucp-go-distributed-review`. Проверь `Grep` на `http.DefaultClient` без `Authorization`, `jwt.Parse` без `WithExpirationRequired`, прямые строки ролей вне middleware.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — endpoint без `RequireRoles` (`AUTH-9`), самописная JWT-валидация без подписи/claims (`AUTH-4`), анонимный s2s (`AUTH-14`), PII в `slog`/`error.Error()`/событиях (`AUTH-16`), секреты в git (`AUTH-17`), money без `RequireIdempotencyKey` (`AUTH-19`), AT/RT в `localStorage` (`AUTH-20`).
   - **Предупреждение** — 403 вместо 401 на невалидный токен (`AUTH-6`), ABAC в контроллере вместо `AccessPolicy`/Handler (`AUTH-11`), admin без audit (`AUTH-12`/`AUTH-15`), `err.Error()` в `detail` (`AUTH-18`), refresh без rotation (`AUTH-21`).
   - **Замечание** — keyfunc без явного TTL кеша (`AUTH-5`), роль вне разрешённого набора (`AUTH-8`), `oauth2.TokenSource` без `ReuseTokenSource` (лишние запросы к IdP).

## Что не входит

- 401/403-mapping, `apperr.Kind`, `errors.As` — `ucp-go-error-handling-review`. PII в логах/спанах — `ucp-go-observability-review`.
- SAST/CVE/контейнер/криптография ключей — `ucp-go-security-review`. Idempotency-таблица/redis — `ucp-go-distributed-review`.

$ARGUMENTS
