---
name: ucp-go-security-design
lang: go
description: Зашаблонить security-обвязку Go-сервиса по UCP (коды R-SEC-*) — SAST (golangci-lint + gosec + semgrep), CVE (govulncheck + Trivy), Gitleaks, digest-pinned non-root образ, криптография (bcrypt/argon2/AES-GCM/golang-jwt).
when_to_use: Триггеры — «настрой security-сканеры», «gosec/govulncheck в CI», «harden Dockerfile». Старт сервиса или добавление security-CI.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(golangci-lint*)
---

# Security — проектирование (Go / net/http + chi)

Ты настраиваешь security-обвязку по **контракту** `backend/security/security-rules.md` (`R-SEC-*`) и **Go-реализации** `backend/security/go/security-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Go-style-guide. Коды в обосновании, не в коде. Связанные: `auth-patterns` (auth-флоу, JWT-middleware `AUTH-4`), `observability` (PII `AUTH-16`/`R-OBS-*`), `go-bootstrap` (CI/Dockerfile wiring).

2. **SAST** (`R-SEC-SAST-*`): `golangci-lint` с включёнными `gosec`, `staticcheck`, `errcheck`, `errorlint`, `bodyclose` в CI; `gosec -fmt sarif -severity HIGH` для GitHub Security tab; fail на HIGH/CRITICAL; suppressions `//nolint:gosec // G<N>: причина; заменить до: YYYY-MM-DD`.

3. **CVE** (`R-SEC-DEP-*`): `govulncheck` (Go Vulnerability Database) + Trivy на merge в main/nightly/release (не на PR); `go.sum` коммитится; Renovate/Dependabot (`ecosystem: gomod`); CVSS ≥ 7.0 ломает сборку; подавления в `govuln-suppressions.json` с `"until"`.

4. **Секреты** (`R-SEC-SECRET-*`): Gitleaks pre-commit + CI + weekly full-history; `.pre-commit-config.yaml` в репо; секреты только через `os.Getenv`/`envconfig`; `.env` в `.gitignore`, `.env.example` без значений.

5. **Образ** (`R-SEC-IMG-*`): Trivy в CI после `docker build` до `docker push`; base `golang:1.23-alpine3.20@sha256:<digest>` builder + `gcr.io/distroless/static-debian12:nonroot@sha256:<digest>` финальный stage; `USER 65532:65532`; `HEALTHCHECK` или k8s-probe.

6. **Криптография** (`R-SEC-CRYPTO-*`): `golang.org/x/crypto/bcrypt` cost ≥ 12 (или `argon2id`) для паролей; `crypto/rand` (не `math/rand`) для security; `crypto/aes`+`crypto/cipher` AES-GCM с `io.ReadFull(rand.Reader, nonce)` (12 байт); JWT через `github.com/golang-jwt/jwt/v5` с JWKS keyfunc (`github.com/MicahParks/keyfunc/v3`), `WithValidMethods([]string{"RS256","ES256"})`; ключи через env/Vault.

7. **Findings** (`R-SEC-FIND-*`): SLA по severity (CRITICAL/HIGH — сборка падает); suppressions со сроком; SARIF из `gosec`, `semgrep`, `trivy image --format sarif` → GitHub Security tab. Самопроверка по чеклисту из `go/security-style-guide.md` §«Чеклист подключения» + предложи `ucp-go-security-review`.

## Антипаттерны, которые НЕ генерировать

- CI без fail на HIGH/CRITICAL (`R-SEC-1`); `//nolint:gosec` без кода нарушения и justification ≥ 30 символов (`R-SEC-SAST-X1`); бессрочное подавление CVE (`R-SEC-DEP-X1`).
- Секреты в `config.yaml`/коде (`R-SEC-SECRET-X1`); закоммиченный `.env` (`R-SEC-SECRET-X2`).
- Контейнер от root или без `USER` в финальном stage (`R-SEC-IMG-X1`); `:latest` base image (`R-SEC-IMG-X2`).
- `crypto/md5`/`crypto/sha1` для паролей / `math/rand` для security / AES-ECB (`R-SEC-CRYPTO-1/2/3`); hardcoded ключи или nonce в коде (`R-SEC-CRYPTO-X1`); ручной парсинг JWT без верификации подписи (`R-SEC-CRYPTO-5`).

После работы скилла — обязательно `ucp-go-security-review`.

$ARGUMENTS
