---
name: ucp-go-security-review
lang: go
description: Ревью security Go-сервиса (net/http + chi) по коду R-SEC-* — golangci-lint+gosec в CI, govulncheck+Trivy на CVE, Gitleaks, bcrypt/argon2, crypto/rand, AES-GCM, golang-jwt/jwt/v5+keyfunc, envconfig, distroless non-root, suppressions со сроком.
when_to_use: Изменения в .golangci.yml, CI workflow, Dockerfile, config/config.go, crypto-коде, JWT-middleware, go.sum или любом файле с //nolint:gosec.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(golangci-lint*)
---

# Ревью Security (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/security/security-rules.md`
(`R-SEC-*`) и его **Go-реализации** `backend/security/go/security-style-guide.md`.
Инструментальный стек отличается от Java/Python: `golangci-lint`+`gosec`+`staticcheck` (SAST),
`govulncheck` (CVE), `crypto/rand` (случайность), `golang.org/x/crypto/bcrypt` или `argon2`
(пароли), `golang-jwt/jwt/v5`+`keyfunc` (JWT), `envconfig` (секреты).

## Зависимости

- **`.claude/docs/backend/security/security-rules.md`** — общий контракт (`R-SEC-*`).
- **`.claude/docs/backend/security/go/security-style-guide.md`** — Go-реализация (golangci-lint,
  govulncheck, Gitleaks, bcrypt/argon2, crypto/rand, AES-GCM, golang-jwt, envconfig, distroless).
- Парные: `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-4`/`AUTH-16`/`AUTH-17`),
  `backend/observability/observability-rules.md` (PII в логах), `backend/error-handling/go/error-handling-style-guide.md`
  (errcheck/errorlint, `%w`).

## Инструкции

1. **Прочти** `security-rules.md` (коды) и Go-style-guide (как это в Go). Цитируй конкретные коды
   (`R-SEC-SAST-X1`, `R-SEC-CRYPTO-1`), не только префикс.

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
   - **Grep**: `math/rand` (не-security shuffle — ок; security-токен рядом → `R-SEC-CRYPTO-2`),
     `"md5"\|"sha1"` в crypto-контексте, `//nolint:gosec` без кода, hardcoded `[a-zA-Z0-9]{32,}`,
     `USER root`, `:latest`, `jwt.Parse` без `WithValidMethods`.

3. **Прогон по подгруппам.**

   ### `R-SEC-1..4` — Enforcement
   - CI падает на HIGH/CRITICAL gosec/staticcheck (`golangci-lint run` без `--exit-code 0`)?
     Нет → `R-SEC-1`.
   - Расслоение: golangci-lint/gosec/staticcheck на PR, govulncheck/Trivy на merge в main/release?
     Нет → `R-SEC-2`.
   - Все suppressions — файлы (`.golangci.yml`, `govuln-suppressions.json`, `.gitleaks.toml`),
     не россыпь `//nolint:` без обоснования? Нет → `R-SEC-3`.
   - Baseline-механика на release (блокировать только новые findings)? Нет → `R-SEC-4`.

   ### `R-SEC-SAST-*` — SAST
   - `.golangci.yml` включает gosec, staticcheck, errcheck, errorlint, bodyclose, exhaustive;
     `max-issues-per-linter: 0`? Нет → `R-SEC-SAST-1`.
   - gosec запускается с `--fmt sarif`; SARIF загружается в GitHub Security tab? Нет → `R-SEC-SAST-2`.
   - Severity-ответ: HIGH/CRITICAL → fail, MEDIUM → отчёт + ревьюер, LOW → игнор? Нет → `R-SEC-SAST-3`.
   - `//nolint:gosec` содержит код нарушения (`// G401: ...`) и дату (`до: YYYY-MM-DD`),
     обоснование ≥ 30 символов? Нет → `R-SEC-SAST-X1`.
   - Blanket `//nolint` без кода нарушения → `R-SEC-SAST-X1`.

   ### `R-SEC-DEP-*` — CVE
   - `govulncheck ./...` на merge в main/release; `go.sum` коммитится; `go mod tidy` в CI
     фейлит на расхождение? Нет → `R-SEC-DEP-1`.
   - Renovate или Dependabot (`ecosystem: gomod`) настроен? Нет → `R-SEC-DEP-2`.
   - CVSS ≥ 7.0 → govulncheck блокирует (exit code ≠ 0); 4.0–6.9 → отчёт + 30 дней? Нет → `R-SEC-DEP-3`.
   - Suppressions в `govuln-suppressions.json` с полем `"until"`? Нет → `R-SEC-DEP-X1`.
   - `replace`-директива в `go.mod` без CVE-обоснования в production-модуле → `R-SEC-DEP-X2`.
   - `v0.0.0-YYYYMMDD` pre-release в production без пояснения в README → `R-SEC-DEP-X2`.

   ### `R-SEC-SECRET-*` — Секреты
   - Gitleaks в pre-commit (`.pre-commit-config.yaml`) + CI + full history нightly? Нет → `R-SEC-SECRET-1`.
   - `.pre-commit-config.yaml` коммитится, `pre-commit install` одной командой? Нет → `R-SEC-SECRET-2`.
   - Секреты через `os.Getenv` / `envconfig` (struct-тег `envconfig:"..."`) — не хардкод в `config.yaml`?
     Хардкод → `R-SEC-SECRET-X1`.
   - `.env` в `.gitignore`; только `.env.example` с пустыми значениями? Закоммиченный `.env` → `R-SEC-SECRET-X2`.

   ### `R-SEC-IMG-*` — Контейнер
   - Trivy в CI после `docker build` до `docker push`, `--severity HIGH,CRITICAL --exit-code 1`? Нет → `R-SEC-IMG-1`.
   - Base image закреплён тегом + `@sha256:<digest>` (distroless/static или golang:X.Y-alpine + alpine finalt)?
     Нет → `R-SEC-IMG-X2`.
   - Финальный stage: `USER 65532:65532` (distroless:nonroot) или явный `adduser/addgroup`+`USER app:app`?
     Нет → `R-SEC-IMG-X1`.
   - `HEALTHCHECK` в Dockerfile или liveness/readiness-probe в k8s? Нет → `R-SEC-IMG-4`.

   ### `R-SEC-CRYPTO-*` — Криптография
   - Пароли: `golang.org/x/crypto/bcrypt` cost ≥ 12 или `golang.org/x/crypto/argon2`?
     `crypto/md5`/`crypto/sha1`/`crypto/sha256` для паролей → `R-SEC-CRYPTO-1`.
   - Случайность для security: только `crypto/rand`; `math/rand` в security-контексте (gosec G404) → `R-SEC-CRYPTO-2`.
   - Симметричное шифрование: AES-GCM с `io.ReadFull(rand.Reader, nonce)` (12 байт)?
     AES-ECB или CBC без MAC → `R-SEC-CRYPTO-3`.
   - TLS ≥ 1.2 (`tls.Config.MinVersion = tls.VersionTLS12`) если TLS терминируется в приложении? Нет → `R-SEC-CRYPTO-4`.
   - JWT: `jwt.Parse(..., jwks.Keyfunc, jwt.WithExpirationRequired(), jwt.WithValidMethods([]string{"RS256","ES256"}))`?
     Ручной парсинг без верификации подписи → `R-SEC-CRYPTO-5`.
   - Hardcoded ключи, nonce или IV в исходном коде → `R-SEC-CRYPTO-X1`.

   ### `R-SEC-FIND-*` — Реакция на findings
   - Severity → SLA: CRITICAL/HIGH → сборка падает; MEDIUM → отчёт + ≤ 30 дней; LOW → игнор?
     Молчаливый игнор → `R-SEC-FIND-X1`.
   - Все suppressions (`.golangci.yml`, `govuln-suppressions.json`) имеют срок (`до:` / `"until"`)?
     Бессрочное → `R-SEC-DEP-X1` / `R-SEC-SAST-X1`.
   - SARIF из gosec, semgrep, trivy загружается в GitHub Security tab? Нет → `R-SEC-FIND-3`.

4. **Cross-check:**
   - JWT-claims/RBAC/ABAC-проверки → `ucp-go-auth-review` (`AUTH-4`/`AUTH-17`).
   - PII в `slog`-атрибутах → `ucp-go-observability-review` (`AUTH-16`).
   - errcheck/errorlint в `.golangci.yml` → `ucp-go-error-handling-review` (`R-ERR-WHERE-X1`).
   - sqlc-генерированные запросы закрывают SQLi по природе; ручные строки в `pgx.Exec(fmt.Sprintf(...))` → `R-SEC-SAST-2` (gosec G202).

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `crypto/md5`/`sha1` для паролей (`R-SEC-CRYPTO-1`), `math/rand` в security-контексте
     (`R-SEC-CRYPTO-2`), AES-ECB (`R-SEC-CRYPTO-3`), hardcoded ключи/nonce (`R-SEC-CRYPTO-X1`),
     ручной JWT без верификации подписи (`R-SEC-CRYPTO-5`), секреты в коде/git (`R-SEC-SECRET-X1`),
     контейнер от root (`R-SEC-IMG-X1`), CI без fail на CRITICAL/HIGH (`R-SEC-1`).
   - **Предупреждение** — `//nolint:gosec` без кода и даты (`R-SEC-SAST-X1`), бессрочная suppression
     CVE (`R-SEC-DEP-X1`), `:latest` base image (`R-SEC-IMG-X2`), нет `go.sum` в репо (`R-SEC-DEP-1`),
     Gitleaks не настроен в pre-commit.
   - **Замечание** — нет SARIF в GitHub Security tab (`R-SEC-FIND-3`), нет Renovate/Dependabot
     (`R-SEC-DEP-2`), нет `HEALTHCHECK` в Dockerfile (`R-SEC-IMG-4`), semgrep не подключён.

## Что не входит

- Auth-флоу (JWT-claims, RBAC/ABAC) — `ucp-go-auth-review`.
- PII в slog-логах — `ucp-go-observability-review`.
- Retry/CB-конфиг, gobreaker, avast-retry-go — `ucp-go-resilience-review`.
- errcheck/errorlint как error-handling-concern — `ucp-go-error-handling-review`.

$ARGUMENTS
