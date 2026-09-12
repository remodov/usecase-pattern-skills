---
name: ucp-node-security-review
lang: node
description: Ревью Node/NestJS-сервиса по требованиям `security/*` — SAST в CI (tsc strict, eslint-plugin-security, semgrep), npm audit/osv-scanner/Trivy на CVE, Gitleaks, suppressions со сроком, Dockerfile non-root, крипта без md5/AES-ECB.
when_to_use: Ревью package.json/CI-конфигов, Dockerfile, eslint-конфига, suppression-файлов, кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Security (Node / eslint-plugin-security + npm audit + Trivy + argon2)

Ты ревьюишь security на соответствие **контракту** `backend/security/spec.md` (`R-SEC-*`) и **Node-реализации** `backend/security/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/security/spec.md`** + **`backend/security/references/node/implementation.md`**.
- Парные: `auth-patterns` (`auth-patterns/token-validated-by-library`/`auth-patterns/no-secrets-in-repository`), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `node/nest-bootstrap` (`nest-bootstrap/config-validated-at-startup` конфиг/секреты, CI/Dockerfile).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`security/passwords-hashed-with-kdf`, `security/image-pinned-and-nonroot`), не префикс.

2. **Скоп.** `package.json`/`package-lock.json`, `tsconfig.json`, `eslint.config.mjs`, `.github/workflows/*`, `Dockerfile`, конфиг (`AppConfig`/env-схема), `.gitleaks.toml`, `osv-scanner.toml`/`audit-ci.json`, код с `node:crypto`; `git diff`.

3. **Прогон.**
   - **Enforcement (`R-SEC-1..4`):** CI падает на HIGH/CRITICAL (`|| true`/ослабленный `--audit-level` → `security/high-severity-breaks-build`); расслоение по скорости (tsc/eslint каждый PR, audit/Trivy на main/release); suppressions — файлы со сроком, не россыпь `// eslint-disable`.
   - **SAST (`R-SEC-SAST-*`):** `tsc --noEmit` strict + eslint (`typescript-eslint` + `eslint-plugin-security`, + semgrep `p/typescript`/`p/nodejs`) в CI; `// eslint-disable`/`nosemgrep` без кода правила и justify → `security/suppressions-are-files-with-deadline`.
   - **CVE (`R-SEC-DEP-*`):** `npm audit --audit-level=high`/osv-scanner + Trivy на main/release; CVSS≥7 ломает; lock-файл коммитится, CI ставит `npm ci`. Бессрочное подавление → `security/suppressions-are-files-with-deadline`; `*`/`next`-теги без lock → `security/dependency-updates-automated`.
   - **Секреты (`R-SEC-SECRET-*`):** Gitleaks pre-commit (husky)+CI; секреты в конфиге/коде → `security/no-secret-values-in-config`; закоммиченный `.env` → `security/no-secret-values-in-config` (только `.env.example` без значений).
   - **Образ (`R-SEC-IMG-*`):** Trivy; digest-pinned `node:22-slim`/distroless; `USER node`; `CMD ["node", "dist/main.js"]`, не `npm start` (глотает SIGTERM). Root → `security/image-pinned-and-nonroot`; `:latest` → `security/image-pinned-and-nonroot`.
   - **Крипта (`R-SEC-CRYPTO-*`):** argon2/bcrypt (md5/sha1 для паролей → `security/passwords-hashed-with-kdf`); `crypto.randomBytes`/`randomUUID` (не `Math.random` → `security/csprng-for-security-values`); AES-GCM с рандомным IV (ECB/CBC-без-MAC → `security/authenticated-encryption-only`); TLS ≥ 1.2 (`security/modern-tls-only`); JWT через библиотеку с verify+JWKS (`jwt.decode()` без verify → `security/token-validated-by-library`); hardcoded ключи/IV → `security/no-hardcoded-keys`.
   - **Findings (`R-SEC-FIND-*`):** SLA по severity; suppressions со сроком (`security/suppressions-are-files-with-deadline`); SARIF в Security tab; молчаливый игнор → `security/every-finding-gets-a-decision`.

4. **Cross-check:** JWT-валидация/секреты в auth-флоу — `ucp-auth-review`; PII в логах — `ucp-node-observability-review`; CI/Dockerfile wiring — `ucp-node-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — md5/sha1 для паролей или `Math.random` для security или AES-ECB (`R-SEC-CRYPTO-1/2/3`), hardcoded ключи (`security/no-hardcoded-keys`), секреты в коде/git (`security/no-secret-values-in-config`), контейнер от root (`security/image-pinned-and-nonroot`), CI без fail на CRITICAL (`security/high-severity-breaks-build`), `jwt.decode()` без verify (`security/token-validated-by-library`).
   - **Предупреждение** — `// eslint-disable`/suppression без срока (`security/suppressions-are-files-with-deadline`/`security/suppressions-are-files-with-deadline`), `:latest` base (`security/image-pinned-and-nonroot`), нет lock-файла/`npm ci` (`security/dependency-updates-automated`), Gitleaks не в pre-commit, `npm start` в CMD.
   - **Замечание** — semgrep не подключён, нет SARIF в Security tab (`security/code-security-scanner-required`), MEDIUM без отчёта.

## Что не входит

- Auth-флоу (RBAC/ABAC/JWT-claims) — `ucp-auth-review`. PII в логах — `ucp-node-observability-review`.
- CI/Dockerfile-композиция bootstrap — `ucp-node-bootstrap-review`.

$ARGUMENTS
