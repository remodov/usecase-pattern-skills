---
name: ucp-go-security-review
lang: go
description: Ревью security Go-сервиса (net/http + chi) по коду R-SEC-* — golangci-lint+gosec в CI, govulncheck+Trivy на CVE, Gitleaks, bcrypt/argon2, crypto/rand, AES-GCM, golang-jwt/jwt/v5+keyfunc, envconfig, distroless non-root, suppressions со сроком.
when_to_use: Изменения в .golangci.yml, CI workflow, Dockerfile, config/config.go, crypto-коде, JWT-middleware, go.sum или любом файле с //nolint:gosec.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(golangci-lint*)
---

# Ревью Security (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/security/spec.md`
(`R-SEC-*`) и его **Go-реализации** `backend/security/references/go/implementation.md`.
Инструментальный стек отличается от Java/Python: `golangci-lint`+`gosec`+`staticcheck` (SAST),
`govulncheck` (CVE), `crypto/rand` (случайность), `golang.org/x/crypto/bcrypt` или `argon2`
(пароли), `golang-jwt/jwt/v5`+`keyfunc` (JWT), `envconfig` (секреты).

## Зависимости

- **`.claude/docs/backend/security/spec.md`** — общий контракт (`R-SEC-*`).
- **`.claude/docs/backend/security/references/go/implementation.md`** — Go-реализация (golangci-lint,
  govulncheck, Gitleaks, bcrypt/argon2, crypto/rand, AES-GCM, golang-jwt, envconfig, distroless).
- Парные: `backend/auth-patterns/spec.md` (`auth-patterns/token-validated-by-library`/`auth-patterns/no-pii-in-logs-and-events`/`auth-patterns/no-secrets-in-repository`),
  `backend/observability/spec.md` (PII в логах), `backend/error-handling/references/go/implementation.md`
  (errcheck/errorlint, `%w`).

## Инструкции

1. **Прочти** `security/spec.md` и `references/go/implementation.md` (как это в Go). Цитируй конкретные коды
   (`security/suppressions-are-files-with-deadline`, `security/passwords-hashed-with-kdf`), не только префикс.

2. **Определи скоп.**
   - `.golangci.yml` — включены gosec, staticcheck, errcheck, errorlint, bodyclose, exhaustive.
   - `.github/workflows/*.yml` / `Makefile` — CI-шаги: golangci-lint, gosec SARIF, govulncheck, Trivy.
   - `Dockerfile` — base image с digest, non-root, HEALTHCHECK.
   - `config/config.go` или аналог — envconfig, нет хардкода.
   - `.gitleaks.toml`, `.pre-commit-config.yaml` — Gitleaks pre-commit + CI.
   - `go.mod` / `go.sum` — зафиксирован, Renovate/Dependabot, нет `replace` без CVE-обоснования.
   - `govuln-suppressions.json` — suppressions со сроком.
   - Crypto-код: bcrypt/argon2, `crypto/rand`, AES-GCM.
   - `adapters/in/http/middleware/*.go` — JWT-middleware через `golang-jwt/jwt/v5` + JWKS keyfunc.
   - `git diff` на изменённые `.go`, `.yml`, `Dockerfile`.
   - **Grep**: `math/rand` (не-security shuffle — ок; security-токен рядом → `security/csprng-for-security-values`),
     `"md5"\|"sha1"` в crypto-контексте, `//nolint:gosec` без кода, hardcoded `[a-zA-Z0-9]{32,}`,
     `USER root`, `:latest`, `jwt.Parse` без `WithValidMethods`.

3. **Прогон по подгруппам.**

   ### `R-SEC-1..4` — Enforcement
   - CI падает на HIGH/CRITICAL gosec/staticcheck (`golangci-lint run` без `--exit-code 0`)?
     Нет → `security/high-severity-breaks-build`.
   - Расслоение: golangci-lint/gosec/staticcheck на PR, govulncheck/Trivy на merge в main/release?
     Нет → `security/checks-layered-by-feedback-speed`.
   - Все suppressions — файлы (`.golangci.yml`, `govuln-suppressions.json`, `.gitleaks.toml`),
     не россыпь `//nolint:` без обоснования? Нет → `security/suppressions-are-files-with-deadline`.
   - Baseline-механика на release (блокировать только новые findings)? Нет → `security/baseline-blocks-new-findings`.

   ### `R-SEC-SAST-*` — SAST
   - `.golangci.yml` включает gosec, staticcheck, errcheck, errorlint, bodyclose, exhaustive;
     `max-issues-per-linter: 0`? Нет → `security/compile-time-analysis-enabled`.
   - gosec запускается с `--fmt sarif`; SARIF загружается в GitHub Security tab? Нет → `security/code-security-scanner-required`.
   - Severity-ответ: HIGH/CRITICAL → fail, MEDIUM → отчёт + ревьюер, LOW → игнор? Нет → `security/high-severity-breaks-build`.
   - `//nolint:gosec` содержит код нарушения (`// G401: ...`) и дату (`до: YYYY-MM-DD`),
     обоснование ≥ 30 символов? Нет → `security/suppressions-are-files-with-deadline`.
   - Blanket `//nolint` без кода нарушения → `security/suppressions-are-files-with-deadline`.

   ### `R-SEC-DEP-*` — CVE
   - `govulncheck ./...` на merge в main/release; `go.sum` коммитится; `go mod tidy` в CI
     фейлит на расхождение? Нет → `security/checks-layered-by-feedback-speed`.
   - Renovate или Dependabot (`ecosystem: gomod`) настроен? Нет → `security/dependency-updates-automated`.
   - CVSS ≥ 7.0 → govulncheck блокирует (exit code ≠ 0); 4.0–6.9 → отчёт + 30 дней? Нет → `security/high-severity-breaks-build`.
   - Suppressions в `govuln-suppressions.json` с полем `"until"`? Нет → `security/suppressions-are-files-with-deadline`.
   - `replace`-директива в `go.mod` без CVE-обоснования в production-модуле → `security/dependency-updates-automated`.
   - `v0.0.0-YYYYMMDD` pre-release в production без пояснения в README → `security/dependency-updates-automated`.

   ### `R-SEC-SECRET-*` — Секреты
   - Gitleaks в pre-commit (`.pre-commit-config.yaml`) + CI + full history нightly? Нет → `security/secret-scanning-before-push`.
   - `.pre-commit-config.yaml` коммитится, `pre-commit install` одной командой? Нет → `security/secret-scanning-before-push`.
   - Секреты через `os.Getenv` / `envconfig` (struct-тег `envconfig:"..."`) — не хардкод в `config.yaml`?
     Хардкод → `security/no-secret-values-in-config`.
   - `.env` в `.gitignore`; только `.env.example` с пустыми значениями? Закоммиченный `.env` → `security/no-secret-values-in-config`.

   ### `R-SEC-IMG-*` — Контейнер
   - Trivy в CI после `docker build` до `docker push`, `--severity HIGH,CRITICAL --exit-code 1`? Нет → `security/image-scanning-before-push`.
   - Base image закреплён тегом + `@sha256:<digest>` (distroless/static или golang:X.Y-alpine + alpine finalt)?
     Нет → `security/image-pinned-and-nonroot`.
   - Финальный stage: `USER 65532:65532` (distroless:nonroot) или явный `adduser/addgroup`+`USER app:app`?
     Нет → `security/image-pinned-and-nonroot`.
   - `HEALTHCHECK` в Dockerfile или liveness/readiness-probe в k8s? Нет → `security/image-pinned-and-nonroot`.

   ### `R-SEC-CRYPTO-*` — Криптография
   - Пароли: `golang.org/x/crypto/bcrypt` cost ≥ 12 или `golang.org/x/crypto/argon2`?
     `crypto/md5`/`crypto/sha1`/`crypto/sha256` для паролей → `security/passwords-hashed-with-kdf`.
   - Случайность для security: только `crypto/rand`; `math/rand` в security-контексте (gosec G404) → `security/csprng-for-security-values`.
   - Симметричное шифрование: AES-GCM с `io.ReadFull(rand.Reader, nonce)` (12 байт)?
     AES-ECB или CBC без MAC → `security/authenticated-encryption-only`.
   - TLS ≥ 1.2 (`tls.Config.MinVersion = tls.VersionTLS12`) если TLS терминируется в приложении? Нет → `security/modern-tls-only`.
   - JWT: `jwt.Parse(..., jwks.Keyfunc, jwt.WithExpirationRequired(), jwt.WithValidMethods([]string{"RS256","ES256"}))`?
     Ручной парсинг без верификации подписи → `security/token-validated-by-library`.
   - Hardcoded ключи, nonce или IV в исходном коде → `security/no-hardcoded-keys`.

   ### `R-SEC-FIND-*` — Реакция на findings
   - Severity → SLA: CRITICAL/HIGH → сборка падает; MEDIUM → отчёт + ≤ 30 дней; LOW → игнор?
     Молчаливый игнор → `security/every-finding-gets-a-decision`.
   - Все suppressions (`.golangci.yml`, `govuln-suppressions.json`) имеют срок (`до:` / `"until"`)?
     Бессрочное → `security/suppressions-are-files-with-deadline` / `security/suppressions-are-files-with-deadline`.
   - SARIF из gosec, semgrep, trivy загружается в GitHub Security tab? Нет → `security/code-security-scanner-required`.

4. **Cross-check:**
   - JWT-claims/RBAC/ABAC-проверки → `ucp-go-auth-review` (`auth-patterns/token-validated-by-library`/`auth-patterns/no-secrets-in-repository`).
   - PII в `slog`-атрибутах → `ucp-go-observability-review` (`auth-patterns/no-pii-in-logs-and-events`).
   - errcheck/errorlint в `.golangci.yml` → `ucp-go-error-handling-review` (`error-handling/catch-does-not-swallow`).
   - sqlc-генерированные запросы закрывают SQLi по природе; ручные строки в `pgx.Exec(fmt.Sprintf(...))` → `security/code-security-scanner-required` (gosec G202).

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `crypto/md5`/`sha1` для паролей (`security/passwords-hashed-with-kdf`), `math/rand` в security-контексте
     (`security/csprng-for-security-values`), AES-ECB (`security/authenticated-encryption-only`), hardcoded ключи/nonce (`security/no-hardcoded-keys`),
     ручной JWT без верификации подписи (`security/token-validated-by-library`), секреты в коде/git (`security/no-secret-values-in-config`),
     контейнер от root (`security/image-pinned-and-nonroot`), CI без fail на CRITICAL/HIGH (`security/high-severity-breaks-build`).
   - **Предупреждение** — `//nolint:gosec` без кода и даты (`security/suppressions-are-files-with-deadline`), бессрочная suppression
     CVE (`security/suppressions-are-files-with-deadline`), `:latest` base image (`security/image-pinned-and-nonroot`), нет `go.sum` в репо (`security/checks-layered-by-feedback-speed`),
     Gitleaks не настроен в pre-commit.
   - **Замечание** — нет SARIF в GitHub Security tab (`security/code-security-scanner-required`), нет Renovate/Dependabot
     (`security/dependency-updates-automated`), нет `HEALTHCHECK` в Dockerfile (`security/image-pinned-and-nonroot`), semgrep не подключён.

## Что не входит

- Auth-флоу (JWT-claims, RBAC/ABAC) — `ucp-go-auth-review`.
- PII в slog-логах — `ucp-go-observability-review`.
- Retry/CB-конфиг, gobreaker, avast-retry-go — `ucp-go-resilience-review`.
- errcheck/errorlint как error-handling-concern — `ucp-go-error-handling-review`.

$ARGUMENTS
