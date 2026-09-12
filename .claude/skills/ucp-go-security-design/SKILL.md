---
name: ucp-go-security-design
lang: go
description: Зашаблонить security-обвязку Go-сервиса по UCP (требования security/*) — SAST (golangci-lint + gosec + semgrep), CVE (govulncheck + Trivy), Gitleaks, digest-pinned non-root образ, криптография (bcrypt/argon2/AES-GCM/golang-jwt).
when_to_use: Триггеры — «настрой security-сканеры», «gosec/govulncheck в CI», «harden Dockerfile». Старт сервиса или добавление security-CI.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(golangci-lint*)
---

# Security — проектирование (Go / net/http + chi)

Ты настраиваешь security-обвязку по **контракту** `backend/security/spec.md` (`R-SEC-*`) и **Go-реализации** `backend/security/references/go/implementation.md`.

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные: `auth-patterns` (auth-флоу, JWT-middleware `auth-patterns/token-validated-by-library`), `observability` (PII `auth-patterns/no-pii-in-logs-and-events`/`R-OBS-*`), `go-bootstrap` (CI/Dockerfile wiring).

2. **SAST** (`R-SEC-SAST-*`): `golangci-lint` с включёнными `gosec`, `staticcheck`, `errcheck`, `errorlint`, `bodyclose` в CI; `gosec -fmt sarif -severity HIGH` для GitHub Security tab; fail на HIGH/CRITICAL; suppressions `//nolint:gosec // G<N>: причина; заменить до: YYYY-MM-DD`.

3. **CVE** (`R-SEC-DEP-*`): `govulncheck` (Go Vulnerability Database) + Trivy на merge в main/nightly/release (не на PR); `go.sum` коммитится; Renovate/Dependabot (`ecosystem: gomod`); CVSS ≥ 7.0 ломает сборку; подавления в `govuln-suppressions.json` с `"until"`.

4. **Секреты** (`R-SEC-SECRET-*`): Gitleaks pre-commit + CI + weekly full-history; `.pre-commit-config.yaml` в репо; секреты только через `os.Getenv`/`envconfig`; `.env` в `.gitignore`, `.env.example` без значений.

5. **Образ** (`R-SEC-IMG-*`): Trivy в CI после `docker build` до `docker push`; base `golang:1.23-alpine3.20@sha256:<digest>` builder + `gcr.io/distroless/static-debian12:nonroot@sha256:<digest>` финальный stage; `USER 65532:65532`; `HEALTHCHECK` или k8s-probe.

6. **Криптография** (`R-SEC-CRYPTO-*`): `golang.org/x/crypto/bcrypt` cost ≥ 12 (или `argon2id`) для паролей; `crypto/rand` (не `math/rand`) для security; `crypto/aes`+`crypto/cipher` AES-GCM с `io.ReadFull(rand.Reader, nonce)` (12 байт); JWT через `github.com/golang-jwt/jwt/v5` с JWKS keyfunc (`github.com/MicahParks/keyfunc/v3`), `WithValidMethods([]string{"RS256","ES256"})`; ключи через env/Vault.

7. **Findings** (`R-SEC-FIND-*`): SLA по severity (CRITICAL/HIGH — сборка падает); suppressions со сроком; SARIF из `gosec`, `semgrep`, `trivy image --format sarif` → GitHub Security tab. Самопроверка по чеклисту из `go/implementation.md` §«Чеклист подключения» + предложи `ucp-go-security-review`.

## Антипаттерны, которые НЕ генерировать

- CI без fail на HIGH/CRITICAL (`security/high-severity-breaks-build`); `//nolint:gosec` без кода нарушения и justification ≥ 30 символов (`security/suppressions-are-files-with-deadline`); бессрочное подавление CVE (`security/suppressions-are-files-with-deadline`).
- Секреты в `config.yaml`/коде (`security/no-secret-values-in-config`); закоммиченный `.env` (`security/no-secret-values-in-config`).
- Контейнер от root или без `USER` в финальном stage (`security/image-pinned-and-nonroot`); `:latest` base image (`security/image-pinned-and-nonroot`).
- `crypto/md5`/`crypto/sha1` для паролей / `math/rand` для security / AES-ECB (`R-SEC-CRYPTO-1/2/3`); hardcoded ключи или nonce в коде (`security/no-hardcoded-keys`); ручной парсинг JWT без верификации подписи (`security/token-validated-by-library`).

После работы скилла — обязательно `ucp-go-security-review`.

$ARGUMENTS
