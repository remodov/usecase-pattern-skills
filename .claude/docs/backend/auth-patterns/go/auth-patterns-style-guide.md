# Auth Patterns — Go Style Guide (net/http + chi)

Реализация контракта `../auth-patterns-rules.md` (`AUTH-1..21`) на Go-стеке (stdlib `net/http` + chi).
Коды правил — общие с Java/Python; механизм: вместо Spring Security `oauth2ResourceServer`/`@PreAuthorize`
или FastAPI `Depends` — **chi-middleware + golang-jwt/jwt/v5 + JWKS-кеш**. Ошибки — значения (`apperr.Kind`
+ `errors.As` + `%w`); парадигма совпадает с `error-handling/go/error-handling-style-guide.md`.

Структура слоёв: `core/` (домен + access-policy), `adapters/in/http/` (chi-роутер + middleware),
`adapters/out/*` (HTTP-клиенты s2s).

---

## 1. Где какая проверка делается (`AUTH-1..3`)

`AUTH-1` — edge/gateway: аутентификация (JWT-подпись, `exp`, `iss`, `aud`) + rate limit; identity
прокидывается в `context.Context`. `AUTH-2` — BFF/application-layer: грубая RBAC по роли — декларативный
chi-middleware `RequireRoles("admin")` на группе роутов. `AUTH-3` — domain-handler: ABAC по ресурсу
(`order.CustomerID == principal.Sub`), не на gateway (он не знает доменную модель).

```go
// adapters/in/http/router.go
r := chi.NewRouter()
r.Use(middleware.AuthN(jwtValidator))           // AUTH-1: аутентификация на edge

r.Group(func(r chi.Router) {
    r.Use(middleware.RequireRoles("customer"))   // AUTH-2: RBAC по группе роутов
    r.Post("/orders", h.CreateOrder)
    r.Get("/orders/{id}", h.GetOrder)
})

r.Group(func(r chi.Router) {
    r.Use(middleware.RequireRoles("admin"))
    r.Post("/orders/{id}/cancel", h.AdminCancelOrder)
})
```

**PREFER:** один `AuthN`-middleware на всём роутере (или на общей группе), `RequireRoles` — на каждой
группе по ролевому признаку. **AVOID:** проверка `jwt.Valid()` внутри handler-функции или UseCase Handler.

---

## 2. JWT validation (`AUTH-4..6`)

`AUTH-4` — JWT валидируется через `github.com/golang-jwt/jwt/v5` + JWKS-keyfunc из
`github.com/MicahParks/keyfunc/v3`; самописный парсинг подписи запрещён. `AUTH-5` — JWK Set тянется
из IdP по `jwks_uri` с кешем (~5 мин); keyfunc обновляет ключи автоматически. `AUTH-6` — невалидная
подпись или просроченный `exp` → **401**, не 403; путать запрещено.

```go
// adapters/in/http/security/jwt.go
package security

type Principal struct {
    Sub   string
    Roles []string
}

type JWTValidator struct {
    jwks     *keyfunc.JWKS
    issuer   string
    audience string
}

func NewJWTValidator(jwksURI, issuer, audience string) (*JWTValidator, error) {
    jwks, err := keyfunc.NewDefault([]string{jwksURI})
    if err != nil {
        return nil, fmt.Errorf("jwks init: %w", err)
    }
    return &JWTValidator{jwks: jwks, issuer: issuer, audience: audience}, nil
}

func (v *JWTValidator) Validate(tokenStr string) (*Principal, error) {
    token, err := jwt.Parse(tokenStr, v.jwks.Keyfunc,
        jwt.WithIssuer(v.issuer),
        jwt.WithAudience(v.audience),
        jwt.WithValidMethods([]string{"RS256", "ES256"}),
        jwt.WithExpirationRequired(),
    )
    if err != nil || !token.Valid {
        return nil, &AuthError{Reason: "invalid token"}   // AUTH-6 → 401
    }
    claims, ok := token.Claims.(jwt.MapClaims)
    if !ok {
        return nil, &AuthError{Reason: "malformed claims"}
    }
    return &Principal{
        Sub:   claims["sub"].(string),
        Roles: extractRoles(claims),
    }, nil
}

// core/apperr/autherr.go
type AuthError struct{ Reason string }
func (e *AuthError) Error() string    { return "auth: " + e.Reason }
func (e *AuthError) Kind() Kind       { return Unauthenticated }   // mapKind → 401
```

**PREFER:** одна точка `Validate` на весь сервис, результат — `*Principal` в контекст.
**AVOID:** `jwt.ParseWithClaims` без `WithExpirationRequired()`; хранение raw-токена в `context.Context`.

---

## 3. RBAC: маппинг ролей (`AUTH-7..9`)

`AUTH-7` — роли маппятся из `realm_access.roles` (Keycloak) или `scope` (OAuth2) в `Principal.Roles`
в `extractRoles`. `AUTH-8` — разрешённые роли: `customer`, `seller`, `admin`, `system`. `AUTH-9` — на
каждой группе роутов обязателен `RequireRoles`; endpoint без него — критическое нарушение.

```go
// adapters/in/http/security/extract.go
func extractRoles(claims jwt.MapClaims) []string {
    // Keycloak: realm_access.roles
    if ra, ok := claims["realm_access"].(map[string]any); ok {
        if roles, ok := ra["roles"].([]any); ok {
            return toStrings(roles)
        }
    }
    // OAuth2 scope → split
    if scope, ok := claims["scope"].(string); ok {
        return strings.Fields(scope)
    }
    return nil
}

// adapters/in/http/middleware/rbac.go
const principalKey ctxKey = "principal"

func RequireRoles(roles ...string) func(http.Handler) http.Handler {
    allowed := make(map[string]struct{}, len(roles))
    for _, r := range roles {
        allowed[r] = struct{}{}
    }
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            p := PrincipalFrom(r.Context())
            if p == nil {
                httperr.Write(w, r, &apperr.AuthError{Reason: "unauthenticated"})
                return
            }
            for _, role := range p.Roles {
                if _, ok := allowed[role]; ok {
                    next.ServeHTTP(w, r)
                    return
                }
            }
            httperr.Write(w, r, &apperr.ForbiddenError{Required: roles})
        })
    }
}

func PrincipalFrom(ctx context.Context) *security.Principal {
    p, _ := ctx.Value(principalKey).(*security.Principal)
    return p
}
```

**PREFER:** `RequireRoles` на `chi.Group`, не на каждом отдельном роуте.
**AVOID:** сравнение ролей строками (`p.Roles[0] == "admin"`) вне middleware; строчная роль без константы.

---

## 4. ABAC: владение ресурсом (`AUTH-10..12`)

`AUTH-10` — команда с агрегатом по id — ABAC в Handler: `order.CustomerID == principal.Sub`; нарушение
→ `ForbiddenError`. `AUTH-11` — ABAC-логика в выделенном `AccessPolicy` или Handler, не в контроллере.
`AUTH-12` — роль `admin` обходит ABAC, но каждое действие — в audit log (`AUTH-15`).

```go
// core/order/access.go
type OrderAccessPolicy struct{}

func (p *OrderAccessPolicy) CheckOwnership(order *Order, principal *security.Principal) error {
    for _, role := range principal.Roles {
        if role == "admin" {
            return nil   // AUTH-12: admin проходит, audit пишет Handler
        }
    }
    if order.CustomerID != principal.Sub {
        return &apperr.ForbiddenError{Resource: "order", ResourceID: order.ID}
    }
    return nil
}

// core/order/handler/get_order.go
func (h *GetOrderHandler) Handle(ctx context.Context, cmd GetOrderCommand) (OrderView, error) {
    order, err := h.repo.ByID(ctx, cmd.OrderID)
    if err != nil {
        return OrderView{}, fmt.Errorf("load order %s: %w", cmd.OrderID, err)
    }
    principal := security.PrincipalFrom(ctx)
    if err := h.policy.CheckOwnership(order, principal); err != nil {   // AUTH-10
        return OrderView{}, err
    }
    return toView(order), nil
}
```

**PREFER:** `AccessPolicy` как отдельный тип в `core/<aggregate>/`; один метод на тип проверки.
**AVOID:** `if principal.Sub == order.CustomerID` напрямую в контроллере; ABAC в adapter-слое.

---

## 5. Service-to-service (`AUTH-13..14`)

`AUTH-13` — s2s: mTLS (Service Mesh / Istio) либо Client Credentials Flow
(`grant_type=client_credentials`, `scope=service:operation`). `AUTH-14` — outbound-клиенты в
`adapters/out/*` никогда не ходят без mTLS/`Bearer`; анонимный inter-service трафик — критическое
нарушение.

```go
// adapters/out/product/client.go
type Client struct {
    http      *http.Client   // сконфигурирован с TLS-certs для mTLS, либо с TokenSource
    tokenSrc  oauth2.TokenSource
    baseURL   string
}

func (c *Client) GetProduct(ctx context.Context, productID string) (Product, error) {
    req, _ := http.NewRequestWithContext(ctx, http.MethodGet,
        c.baseURL+"/products/"+productID, nil)

    // AUTH-14: Bearer из Client Credentials
    tok, err := c.tokenSrc.Token()
    if err != nil {
        return Product{}, &apperr.GatewayError{System: "product-svc", Op: "token", Err: err}
    }
    req.Header.Set("Authorization", "Bearer "+tok.AccessToken)

    resp, err := c.http.Do(req)
    if err != nil {
        return Product{}, &apperr.GatewayError{System: "product-svc", Op: "get-product", Err: err}
    }
    defer resp.Body.Close()
    // ... decode
}
```

Конфигурация `oauth2.TokenSource` через `golang.org/x/oauth2/clientcredentials.Config`:

```go
// cmd/app/wire.go
ccCfg := clientcredentials.Config{
    ClientID:     cfg.S2S.ClientID,
    ClientSecret: cfg.S2S.ClientSecret,   // AUTH-17: из env/Vault, не в git
    TokenURL:     cfg.S2S.TokenURL,
    Scopes:       []string{"service:product:read"},
}
productClient := product.NewClient(ccCfg.TokenSource(ctx), cfg.ProductSvcURL)
```

**PREFER:** `oauth2.ReuseTokenSource` (кеш токена до `expiry - delta`); mTLS-cert из файловой системы
монтируется через `tls.LoadX509KeyPair`, не хардкодится. **AVOID:** `http.DefaultClient` без
`Authorization`; ручное прикрепление токена без `TokenSource` (пропускает refresh).

---

## 6. Аудит admin-команд (`AUTH-15`)

`AUTH-15` — каждая state-changing команда от `admin` пишет строку в `*_audit_log` (`actor_id`,
`occurred_at`, `action`, `<aggregate>_id`, `metadata` JSONB) — через явный вызов в Handler или
обёртку-middleware.

```go
// core/audit/audit.go
type LogEntry struct {
    ActorID     string
    OccurredAt  time.Time
    Action      string
    AggregateID string
    Metadata    map[string]any
}

type Logger interface {
    Log(ctx context.Context, e LogEntry) error
}

// core/order/handler/admin_cancel_order.go
func (h *AdminCancelOrderHandler) Handle(ctx context.Context, cmd AdminCancelOrderCommand) error {
    principal := security.PrincipalFrom(ctx)

    order, err := h.repo.ByID(ctx, cmd.OrderID)
    if err != nil {
        return fmt.Errorf("load order %s: %w", cmd.OrderID, err)
    }
    if err := order.Cancel(cmd.Reason); err != nil {
        return err
    }
    if err := h.repo.Save(ctx, order); err != nil {
        return fmt.Errorf("save order %s: %w", cmd.OrderID, err)
    }
    return h.audit.Log(ctx, audit.LogEntry{    // AUTH-15: обязательно
        ActorID:     principal.Sub,
        OccurredAt:  time.Now().UTC(),
        Action:      "order.cancel",
        AggregateID: order.ID,
        Metadata:    map[string]any{"reason": cmd.Reason},
    })
}
```

**PREFER:** `audit.Logger` — порт-интерфейс в `core/audit/`; adapter пишет в таблицу `order_audit_log`
через sqlc. **AVOID:** прямой `INSERT` без порта; audit в chi-middleware без доменного контекста
(нет доступа к `aggregate_id`).

---

## 7. PII и секреты (`AUTH-16..18`)

`AUTH-16` — PII (email, phone, ФИО, адрес) не в логах (`slog`), не в `error.Error()` / `problem.detail`,
не в Kafka-событиях (только id; PII подгружает потребитель). `AUTH-17` — секреты (client-secret,
пароли, ключи) не в git; читаются через `github.com/kelseyhightower/envconfig` из env / Vault.
`AUTH-18` — edge error-renderer не пишет `err.Error()` в `detail` напрямую.

```go
// adapters/in/http/httperr/render.go
func sanitize(err error) string {
    // AUTH-18: для технических ошибок — общая фраза; domain — по коду
    var d *apperr.DomainError
    if errors.As(err, &d) {
        return d.UserMessage   // заранее заданное сообщение, не stack/причина
    }
    return "internal error"
}

// Пример: AuthError НЕ содержит PII
type CustomerNotFoundError struct {
    CustomerID string   // OK — только id
    // НЕТ: Email string, Phone string
}
func (e *CustomerNotFoundError) Error() string {
    return fmt.Sprintf("customer not found: id=%s", e.CustomerID)
}
```

Конфигурация через envconfig:

```go
// cmd/app/config.go
type Config struct {
    S2S struct {
        ClientSecret string `envconfig:"S2S_CLIENT_SECRET,required"`
    }
    DB struct {
        Password string `envconfig:"DB_PASSWORD,required"`
    }
    JWKSUri  string `envconfig:"JWKS_URI,required"`
    Audience string `envconfig:"JWT_AUDIENCE,required"`
    Issuer   string `envconfig:"JWT_ISSUER,required"`
}
```

**PREFER:** `apperr.DomainError` с предопределённым `UserMessage` по коду ошибки; PII-поля в
`slog.Attr` помечать `slog.String("customer_id", id)`, не `slog.String("email", email)`.
**AVOID:** `fmt.Sprintf("customer email %s not found", email)` в `Error()`; `err.Error()` в `detail`;
секреты в `config.go` hardcode.

---

## 8. Идемпотентность (`AUTH-19`)

`AUTH-19` — команда, меняющая деньги/резерв (`CreateOrder`, `ConfirmPayment`, `Refund`), требует
`Idempotency-Key`; повтор с тем же ключом возвращает прежний результат, не дубль.

```go
// adapters/in/http/middleware/idempotency.go
func RequireIdempotencyKey(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        key := r.Header.Get("Idempotency-Key")
        if key == "" {
            httperr.Write(w, r, &apperr.ValidationError{
                Field:   "Idempotency-Key",
                Message: "header required",
            })
            return
        }
        ctx := context.WithValue(r.Context(), idempotencyKeyCtx, key)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// router.go — только на money-командах
r.With(middleware.RequireIdempotencyKey).
    Post("/orders", h.CreateOrder)
r.With(middleware.RequireIdempotencyKey).
    Post("/orders/{id}/payment/confirm", h.ConfirmPayment)
```

Проверка дубля в Handler — через redis-ключ или idempotency-таблицу в PostgreSQL.
Cross-ref: `R-DIST-IDEM-3` (distributed style-guide).

**PREFER:** отдельный `RequireIdempotencyKey` middleware; ответ на дубль — тот же status + body из
кеша/таблицы. **AVOID:** `Idempotency-Key` как часть тела запроса (это заголовок-контракт, не
domain-поле); retry без идемпотентности на write-операциях (`R-ERR-RETRY-3`).

---

## 9. Хранение токенов на клиенте — BFF (`AUTH-20..21`)

`AUTH-20` — для SPA — HttpOnly + Secure + SameSite=Lax cookie (session-cookie у BFF или JWT-в-cookie);
`localStorage` запрещён. `AUTH-21` — refresh-токены с rotation: при обновлении старый инвалидируется;
повторное использование старого RT — компрометация, инвалидируется вся цепочка.

```go
// adapters/in/http/bff/auth_handler.go — callback после OIDC

func (h *AuthHandler) Callback(w http.ResponseWriter, r *http.Request) {
    tokens, err := h.oidc.Exchange(r.Context(), r.URL.Query().Get("code"))
    if err != nil {
        httperr.Write(w, r, &apperr.AuthError{Reason: "code exchange failed"})
        return
    }

    http.SetCookie(w, &http.Cookie{
        Name:     "session",
        Value:    tokens.AccessToken,   // или opaque session-id → server-side store
        HttpOnly: true,                 // AUTH-20: не доступно JS
        Secure:   true,
        SameSite: http.SameSiteLaxMode,
        Path:     "/",
    })
    http.SetCookie(w, &http.Cookie{
        Name:     "refresh_token",
        Value:    tokens.RefreshToken,
        HttpOnly: true,
        Secure:   true,
        SameSite: http.SameSiteStrictMode,
        Path:     "/auth/refresh",      // scope ограничен refresh-endpoint
    })
    http.Redirect(w, r, "/", http.StatusFound)
}

func (h *AuthHandler) Refresh(w http.ResponseWriter, r *http.Request) {
    rtCookie, err := r.Cookie("refresh_token")
    if err != nil {
        httperr.Write(w, r, &apperr.AuthError{Reason: "refresh token missing"})
        return
    }
    tokens, err := h.oidc.Refresh(r.Context(), rtCookie.Value)
    if err != nil {
        // AUTH-21: компрометация → инвалидируем цепочку
        h.tokenStore.RevokeFamily(r.Context(), rtCookie.Value)
        http.SetCookie(w, clearCookie("refresh_token"))
        httperr.Write(w, r, &apperr.AuthError{Reason: "refresh failed"})
        return
    }
    // AUTH-21: старый RT инвалидируется в IdP через rotation
    http.SetCookie(w, &http.Cookie{
        Name:     "refresh_token",
        Value:    tokens.RefreshToken,
        HttpOnly: true, Secure: true,
        SameSite: http.SameSiteStrictMode,
        Path:     "/auth/refresh",
    })
}
```

**PREFER:** BFF держит RT в HttpOnly cookie, на `Path: /auth/refresh`; AT — короткоживущий (≤15 мин).
**AVOID:** передача RT через `localStorage`/`sessionStorage`; AT в cookie без `HttpOnly`; один cookie без
ограничения `Path`.

---

## Чеклист подключения к новому сервису (Go)

- [ ] `apperr`: `Kind` расширен на `Unauthenticated` (→ 401) и `Forbidden` (→ 403); `KindOf` + edge-renderer обновлены.
- [ ] `JWTValidator` с JWKS-keyfunc (`keyfunc/v3`): проверка подписи, `exp`, `iss`, `aud`; невалидный → 401.
- [ ] `AuthN`-middleware кладёт `*Principal` в `context.Context`; стоит первым в цепочке.
- [ ] На каждой chi-группе — `RequireRoles`; нет ни одного публичного роута без проверки роли.
- [ ] `extractRoles` маппит `realm_access.roles` (Keycloak) или `scope` (OAuth2) → `Principal.Roles`.
- [ ] `AccessPolicy` в `core/<aggregate>/` для ABAC по владению; `admin` обходит + audit.
- [ ] `audit.Logger`-порт + adapter пишет в `*_audit_log` для каждой admin-команды.
- [ ] s2s-клиенты в `adapters/out/*` — `oauth2.TokenSource` (Client Credentials) или mTLS; анонимный трафик запрещён.
- [ ] `RequireIdempotencyKey` на всех money-командах (`CreateOrder`, `ConfirmPayment`, `Refund`).
- [ ] PII не в `error.Error()`, не в `slog`-атрибутах, не в Kafka-событиях; edge-renderer использует `sanitize`.
- [ ] Секреты через `envconfig` из env/Vault; `jwt_secret`, `client_secret`, `db_password` не в git.
- [ ] BFF: AT + RT в HttpOnly + Secure + SameSite cookie; `localStorage` не используется; RT с rotation.
