# Security — Go Style Guide (net/http + chi)

Реализация контракта `../security-rules.md` (коды `R-SEC-*`, `R-SEC-SAST-*`, `R-SEC-DEP-*`, `R-SEC-SECRET-*`,
`R-SEC-IMG-*`, `R-SEC-CRYPTO-*`, `R-SEC-FIND-*`) на Go-стеке. Коды общие с Java/Python; меняется набор
инструментов:

| Слой | Java | Python | Go |
|---|---|---|---|
| SAST по коду | Error Prone+NullAway, SpotBugs+FindSecBugs | bandit, semgrep, ruff S-правила | `gosec`, `semgrep` (go-правила), `staticcheck`, `golangci-lint` |
| CVE зависимостей | OWASP Dependency-Check | pip-audit / safety, Trivy | `govulncheck` (Go Vulnerability DB), Trivy |
| Секреты | Gitleaks | Gitleaks | Gitleaks (язык-агностичен) |
| Образ | Trivy | Trivy | Trivy |
| Пароли | BCrypt factor ≥ 12 | argon2-cffi / bcrypt | `golang.org/x/crypto/bcrypt` cost ≥ 12 / `golang.org/x/crypto/argon2` |
| JWT | `oauth2ResourceServer().jwt()` | python-jose с верификацией | `github.com/golang-jwt/jwt/v5` + JWKS keyfunc |
| Случайность | `SecureRandom` | `secrets` | `crypto/rand` |

`R-SEC-1` — сборка падает на HIGH/CRITICAL (`golangci-lint --max-issues-per-linter=0 --max-same-issues=0`, gosec
`-severity=HIGH`). `R-SEC-2` — расслоение: `golangci-lint`/`gosec`/`staticcheck` (каждый PR), Gitleaks (pre-commit),
`govulncheck`/Trivy (merge в main/nightly/release). `R-SEC-3` — suppressions/baselines — файлы в репо
(`.golangci.yml`, `gosec-exclusions.sarif`, `.gitleaks.toml`), не разбросанные `//nolint:` без причины; каждое
исключение — причина + срок. `R-SEC-4` — baseline на release: блокировать только **новые** findings.

---

## 1. SAST по коду (`R-SEC-SAST-*`)

`R-SEC-SAST-1` — статанализ на каждом PR: `golangci-lint` с включёнными `gosec`, `staticcheck`, `errcheck`,
`errorlint`, `bodyclose`, `exhaustive`. Конфиг — `.golangci.yml` в корне, не отдельные флаги в CI-скрипте.

```yaml
# .golangci.yml (минимальный security-subset)
linters:
  enable:
    - gosec
    - staticcheck
    - errcheck
    - errorlint
    - bodyclose
    - exhaustive
linters-settings:
  gosec:
    severity: high
    confidence: high
issues:
  max-issues-per-linter: 0
  max-same-issues: 0
```

`R-SEC-SAST-2` — `gosec` (+ `semgrep` с go-security rulesets) обязательны: SQLi, path traversal, hardcoded
credentials, weak crypto, unsafe package, command injection, SSRF via unchecked URL; SARIF-вывод для GitHub
Code Scanning:

```bash
# CI step — PR gate
gosec -fmt sarif -out gosec.sarif -severity HIGH ./...
# upload sarif → GitHub Security tab (R-SEC-FIND-3)
```

`R-SEC-SAST-3` — severity-ответ: HIGH/CRITICAL gosec/semgrep/staticcheck → fail (выход ≠ 0); MEDIUM — отчёт
+ комментарий ревьюера; LOW — игнор в продакшн-конфиге. `golangci-lint run` возвращает exit code 1 при любых
enabled-findings — в CI без `--exit-code 0`.

`R-SEC-SAST-4` — suppressions через `//nolint:gosec // G401: используем sha1 только для non-security checksum
(content-id, не пароль); заменить до: 2026-12-01` — причина и дата обязательны. Blanket `//nolint` без кода
и объяснения — не принимается.

`R-SEC-SAST-X1` — `//nolint:gosec` без кода нарушения и justification ≥ 30 символов.

---

## 2. CVE в зависимостях (`R-SEC-DEP-*`)

`R-SEC-DEP-1` — `govulncheck` обязателен (Go Vulnerability Database, GHSA); на merge в main + nightly + release
(не на PR — база обновляется непрерывно, интеграция медленнее).

```bash
# CI step — main/nightly/release gate
govulncheck ./...
# Trivy дополнительно по образу (R-SEC-IMG-1)
```

`go.sum` коммитится всегда — обеспечивает воспроизводимость; `go mod tidy` в CI фейлит, если `go.sum` не
актуален.

`R-SEC-DEP-2` — Renovate или Dependabot (`ecosystem: gomod`) — авто-PR на minor/patch, major — manual review.
Lockfile (`go.sum`) обновляется автоматически Renovate.

`R-SEC-DEP-3` — severity: CVSS ≥ 7.0 → `govulncheck` блокирует сборку (`-json` + CI-скрипт проверяет
`"severity": "HIGH|CRITICAL"`); 4.0–6.9 — отчёт + 30 дней; ниже — игнор.

`R-SEC-DEP-4` — suppressions в `govuln-suppressions.json` или `govulncheck -ignore` с обоснованием и сроком.

```json
// govuln-suppressions.json
{
  "suppressions": [
    {
      "vuln": "GO-2024-XXXX",
      "reason": "функция не вызывается в нашем коде-пути",
      "until": "2026-09-01"
    }
  ]
}
```

`R-SEC-DEP-X1` — бессрочное подавление (`until` отсутствует). `R-SEC-DEP-X2` — `replace` директива в
`go.mod` на форк без CVE-обоснования в production-модуле; `v0.0.0-YYYYMMDD` pre-release в production без
пояснения в README.

---

## 3. Секреты (`R-SEC-SECRET-*`)

`R-SEC-SECRET-1` — Gitleaks в pre-commit + CI + full history раз в неделю; `.gitleaks.toml` в корне:

```toml
# .gitleaks.toml
title = "gitleaks config"

[[rules]]
description = "Internal API key"
id = "internal-api-key"
regex = '''internal_api_key\s*=\s*['\"][a-zA-Z0-9]{32,}['\"]'''
tags = ["key", "internal"]
```

`R-SEC-SECRET-2` — pre-commit hook через `.pre-commit-config.yaml`, коммитится в репо, ставится одной
командой `pre-commit install`. Не ручная инструкция «скопируйте хук в .git/hooks».

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

`R-SEC-SECRET-3` — утёк секрет — rotate в течение часа (GitHub уже проиндексировал), удаление из истории
потом (`git filter-repo`).

`R-SEC-SECRET-X1` — секреты в `config.yaml` / исходном коде — только через `os.Getenv` / `envconfig`:

```go
// config/config.go
type Config struct {
    DatabaseURL string `envconfig:"DATABASE_URL,required"`
    JWTSecret   string `envconfig:"JWT_SECRET,required"`
    RedisURL    string `envconfig:"REDIS_URL,required"`
}

func Load() (Config, error) {
    var c Config
    return c, envconfig.Process("", &c)
}
```

Локально — `.env` (в `.gitignore`), prod — Vault / k8s Secret / AWS Secrets Manager.

`R-SEC-SECRET-X2` — закоммиченный `.env` (даже «example» с placeholder-значениями вроде
`JWT_SECRET=changeme`). Используй `.env.example` с пустыми значениями (`JWT_SECRET=`).

---

## 4. Container/image (`R-SEC-IMG-*`)

`R-SEC-IMG-1` — Trivy на все образы в CI после `docker build`, до `docker push`:

```yaml
# .github/workflows/build.yml (фрагмент)
- name: Scan image
  run: |
    trivy image \
      --exit-code 1 \
      --severity HIGH,CRITICAL \
      --format sarif \
      --output trivy.sarif \
      orders-service:${{ github.sha }}
```

`R-SEC-IMG-2` — base image закреплён тегом + digest; не `:latest`:

```dockerfile
FROM golang:1.23-alpine3.20@sha256:<digest> AS builder

FROM gcr.io/distroless/static-debian12:nonroot@sha256:<digest>
# или alpine для Go: alpine:3.20@sha256:<digest>
```

Distroless/static хорош для Go (статически слинкованный бинарь — не нужен libc).

`R-SEC-IMG-3` — non-root пользователь обязательно:

```dockerfile
FROM gcr.io/distroless/static-debian12:nonroot@sha256:<digest>
COPY --from=builder /app/orders-service /orders-service
EXPOSE 8080
USER 65532:65532
ENTRYPOINT ["/orders-service"]
```

В distroless:nonroot `USER 65532:65532` — встроенный nonroot; для alpine — явный `RUN adduser`:

```dockerfile
RUN addgroup -S app && adduser -S app -G app
USER app:app
```

`R-SEC-IMG-4` — HEALTHCHECK в Dockerfile или liveness/readiness в k8s:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["/orders-service", "-health-check"] || exit 1
```

Либо k8s-probe на `/health/live` и `/health/ready` (стандартный эндпоинт chi-роутера).

`R-SEC-IMG-X1` — `USER root` или отсутствие `USER` в финальном stage. `R-SEC-IMG-X2` — `:latest` base image.

---

## 5. Криптография (`R-SEC-CRYPTO-*`)

`R-SEC-CRYPTO-1` — хеширование паролей — `golang.org/x/crypto/bcrypt` cost ≥ 12, или `golang.org/x/crypto/argon2`
(argon2id). Никогда `crypto/md5`, `crypto/sha1`, `crypto/sha256` без KDF для паролей:

```go
// core/customer/password.go
import "golang.org/x/crypto/bcrypt"

const bcryptCost = 12

func HashPassword(plain string) (string, error) {
    b, err := bcrypt.GenerateFromPassword([]byte(plain), bcryptCost)
    if err != nil {
        return "", fmt.Errorf("hash password: %w", err)
    }
    return string(b), nil
}

func CheckPassword(hash, plain string) error {
    if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(plain)); err != nil {
        return &InvalidCredentialsError{}
    }
    return nil
}
```

`R-SEC-CRYPTO-2` — случайность для security — только `crypto/rand`; `math/rand` — только non-security (shuffle,
jitter):

```go
import "crypto/rand"

func GenerateToken(n int) (string, error) {
    b := make([]byte, n)
    if _, err := rand.Read(b); err != nil {
        return "", fmt.Errorf("generate token: %w", err)
    }
    return base64.URLEncoding.EncodeToString(b), nil
}
```

gosec G404 ловит `math/rand` в security-контексте автоматически.

`R-SEC-CRYPTO-3` — симметричное шифрование — AES-GCM с рандомным nonce (12 байт); не AES-ECB, не CBC без MAC:

```go
import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/rand"
    "io"
)

func Encrypt(key, plaintext []byte) ([]byte, error) {
    block, err := aes.NewCipher(key)
    if err != nil {
        return nil, fmt.Errorf("aes cipher: %w", err)
    }
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return nil, fmt.Errorf("aes-gcm: %w", err)
    }
    nonce := make([]byte, gcm.NonceSize())
    if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
        return nil, fmt.Errorf("generate nonce: %w", err)
    }
    return gcm.Seal(nonce, nonce, plaintext, nil), nil
}

func Decrypt(key, ciphertext []byte) ([]byte, error) {
    block, err := aes.NewCipher(key)
    if err != nil {
        return nil, fmt.Errorf("aes cipher: %w", err)
    }
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return nil, fmt.Errorf("aes-gcm: %w", err)
    }
    if len(ciphertext) < gcm.NonceSize() {
        return nil, fmt.Errorf("ciphertext too short")
    }
    nonce, ct := ciphertext[:gcm.NonceSize()], ciphertext[gcm.NonceSize():]
    return gcm.Open(nil, nonce, ct, nil)
}
```

`R-SEC-CRYPTO-4` — TLS ≥ 1.2. Go 1.21+ по умолчанию: `tls.Config.MinVersion = tls.VersionTLS12`. Настраивается
на reverse-proxy (nginx/Caddy); в сервисе явно, если TLS терминируется на уровне приложения.

`R-SEC-CRYPTO-5` — JWT-верификация только через `github.com/golang-jwt/jwt/v5` с проверкой подписи; ручной
парсинг без верификации — критическая ошибка. JWKS keyfunc через `github.com/MicahParks/keyfunc`:

```go
// adapters/in/http/middleware/jwt.go
import (
    "github.com/golang-jwt/jwt/v5"
    "github.com/MicahParks/keyfunc/v3"
)

func JWTMiddleware(jwksURL, issuer, audience string) func(http.Handler) http.Handler {
    jwks, err := keyfunc.NewDefault([]string{jwksURL})
    if err != nil {
        panic(fmt.Sprintf("init jwks: %v", err))
    }
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            raw := extractBearer(r)
            if raw == "" {
                writeUnauthorized(w)
                return
            }
            token, err := jwt.Parse(raw, jwks.Keyfunc,
                jwt.WithExpirationRequired(),
                jwt.WithValidMethods([]string{"RS256", "ES256"}),
                jwt.WithIssuer(issuer),
                jwt.WithAudience(audience),
            )
            if err != nil || !token.Valid {
                writeUnauthorized(w)
                return
            }
            claims, ok := token.Claims.(jwt.MapClaims)
            if !ok {
                writeUnauthorized(w)
                return
            }
            next.ServeHTTP(w, r.WithContext(WithClaims(r.Context(), claims)))
        })
    }
}
```

`R-SEC-CRYPTO-X1` — hardcoded ключи или nonce в коде. Ключи — только через `envconfig` из Vault/KMS; nonce
генерируется через `crypto/rand` на каждое шифрование.

---

## 6. Реакция на findings (`R-SEC-FIND-*`)

`R-SEC-FIND-1` — severity → SLA: CRITICAL — сборка падает, hotfix ≤ 24ч; HIGH — падает, патч ≤ 2 нед;
MEDIUM — отчёт + ≤ 30 дней; LOW — игнор. В CI: `gosec -severity HIGH` и `govulncheck` отдают exit code 1 →
сборка красная автоматически.

`R-SEC-FIND-2` — suppressions имеют срок:

```go
//nolint:gosec // G304: путь пришёл от trusted-конфига, не от пользователя; заменить на embed до: 2026-12-01
f, err := os.Open(cfg.TemplatePath)
```

Квартальный аудит `grep -rn 'до:' .` — найти просроченные. В `govuln-suppressions.json` поле `"until"` обязательно.

`R-SEC-FIND-3` — SARIF из `gosec`, `semgrep`, `trivy image --format sarif` — загружается в GitHub Security tab
через `github/codeql-action/upload-sarif`. Единый дашборд без отдельной инфры:

```yaml
- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: gosec.sarif
```

`R-SEC-FIND-X1` — игнор finding «не уверен, эксплуатируется ли»: либо `//nolint:gosec` с обоснованием, либо
фикс. Молчание = накапливаемый долг без SLA.

---

## Чеклист подключения к новому сервису (Go)

1. `golangci-lint` с gosec+staticcheck+errcheck+errorlint+bodyclose включён в CI (`--max-issues-per-linter=0`);
   gosec SARIF → GitHub Security tab; `//nolint:` только с кодом и датой.
2. `govulncheck` + Trivy на main/release; `go.sum` коммитится; Renovate/Dependabot настроен; нет бессрочных
   подавлений CVE.
3. Gitleaks pre-commit + CI + weekly full-history; `.pre-commit-config.yaml` в репо; секреты только через
   `envconfig` + Vault/k8s Secret; нет закоммиченного `.env`.
4. Dockerfile: distroless/static или alpine с digest-pinned base (`@sha256:`), `USER 65532:65532` / non-root,
   `HEALTHCHECK` или k8s-probe; не `:latest`, не root.
5. Пароли — `bcrypt` cost ≥ 12 или `argon2id`; random — только `crypto/rand`; симметрика — AES-GCM с
   `io.ReadFull(rand.Reader, nonce)`; нет `md5`/`sha1`/ECB; JWT — `golang-jwt/jwt/v5` с JWKS keyfunc и
   `WithValidMethods`; нет ручного парсинга без верификации.
6. Ключи и secrets — только из env/Vault, никогда в коде; nonce генерируется на каждое шифрование.
7. Findings → SLA по severity (CRITICAL/HIGH — сборка падает); suppressions со сроком; SARIF-дашборд
   в GitHub Security tab.
