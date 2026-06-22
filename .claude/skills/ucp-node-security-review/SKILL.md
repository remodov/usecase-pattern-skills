---
name: ucp-node-security-review
lang: node
description: Ревью Node/NestJS-сервиса по security-style-guide (коды R-SEC-*) — SAST в CI (tsc strict, eslint-plugin-security, semgrep), npm audit/osv-scanner/Trivy на CVE, Gitleaks, suppressions со сроком, Dockerfile non-root, крипта без md5/AES-ECB.
when_to_use: Ревью package.json/CI-конфигов, Dockerfile, eslint-конфига, suppression-файлов, кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Security (Node / eslint-plugin-security + npm audit + Trivy + argon2)

Ты ревьюишь security на соответствие **контракту** `backend/security/security-rules.md` (`R-SEC-*`) и **Node-реализации** `backend/security/node/security-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/security/security-rules.md`** + **`backend/security/node/security-style-guide.md`**.
- Парные: `auth-patterns` (`AUTH-4`/`AUTH-17`), `observability` (`AUTH-16` PII), `node/nest-bootstrap` (`NESTBOOT-4` конфиг/секреты, CI/Dockerfile).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-SEC-CRYPTO-1`, `R-SEC-IMG-X1`), не префикс.

2. **Скоп.** `package.json`/`package-lock.json`, `tsconfig.json`, `eslint.config.mjs`, `.github/workflows/*`, `Dockerfile`, конфиг (`AppConfig`/env-схема), `.gitleaks.toml`, `osv-scanner.toml`/`audit-ci.json`, код с `node:crypto`; `git diff`.

3. **Прогон.**
   - **Enforcement (`R-SEC-1..4`):** CI падает на HIGH/CRITICAL (`|| true`/ослабленный `--audit-level` → `R-SEC-1`); расслоение по скорости (tsc/eslint каждый PR, audit/Trivy на main/release); suppressions — файлы со сроком, не россыпь `// eslint-disable`.
   - **SAST (`R-SEC-SAST-*`):** `tsc --noEmit` strict + eslint (`typescript-eslint` + `eslint-plugin-security`, + semgrep `p/typescript`/`p/nodejs`) в CI; `// eslint-disable`/`nosemgrep` без кода правила и justify → `R-SEC-SAST-X1`.
   - **CVE (`R-SEC-DEP-*`):** `npm audit --audit-level=high`/osv-scanner + Trivy на main/release; CVSS≥7 ломает; lock-файл коммитится, CI ставит `npm ci`. Бессрочное подавление → `R-SEC-DEP-X1`; `*`/`next`-теги без lock → `R-SEC-DEP-X2`.
   - **Секреты (`R-SEC-SECRET-*`):** Gitleaks pre-commit (husky)+CI; секреты в конфиге/коде → `R-SEC-SECRET-X1`; закоммиченный `.env` → `R-SEC-SECRET-X2` (только `.env.example` без значений).
   - **Образ (`R-SEC-IMG-*`):** Trivy; digest-pinned `node:22-slim`/distroless; `USER node`; `CMD ["node", "dist/main.js"]`, не `npm start` (глотает SIGTERM). Root → `R-SEC-IMG-X1`; `:latest` → `R-SEC-IMG-X2`.
   - **Крипта (`R-SEC-CRYPTO-*`):** argon2/bcrypt (md5/sha1 для паролей → `R-SEC-CRYPTO-1`); `crypto.randomBytes`/`randomUUID` (не `Math.random` → `R-SEC-CRYPTO-2`); AES-GCM с рандомным IV (ECB/CBC-без-MAC → `R-SEC-CRYPTO-3`); TLS ≥ 1.2 (`R-SEC-CRYPTO-4`); JWT через библиотеку с verify+JWKS (`jwt.decode()` без verify → `R-SEC-CRYPTO-5`); hardcoded ключи/IV → `R-SEC-CRYPTO-X1`.
   - **Findings (`R-SEC-FIND-*`):** SLA по severity; suppressions со сроком (`R-SEC-FIND-2`); SARIF в Security tab; молчаливый игнор → `R-SEC-FIND-X1`.

4. **Cross-check:** JWT-валидация/секреты в auth-флоу — `ucp-auth-review`; PII в логах — `ucp-node-observability-review`; CI/Dockerfile wiring — `ucp-node-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — md5/sha1 для паролей или `Math.random` для security или AES-ECB (`R-SEC-CRYPTO-1/2/3`), hardcoded ключи (`R-SEC-CRYPTO-X1`), секреты в коде/git (`R-SEC-SECRET-X1`), контейнер от root (`R-SEC-IMG-X1`), CI без fail на CRITICAL (`R-SEC-1`), `jwt.decode()` без verify (`R-SEC-CRYPTO-5`).
   - **Предупреждение** — `// eslint-disable`/suppression без срока (`R-SEC-SAST-X1`/`R-SEC-DEP-X1`), `:latest` base (`R-SEC-IMG-X2`), нет lock-файла/`npm ci` (`R-SEC-DEP-X2`), Gitleaks не в pre-commit, `npm start` в CMD.
   - **Замечание** — semgrep не подключён, нет SARIF в Security tab (`R-SEC-FIND-3`), MEDIUM без отчёта.

## Что не входит

- Auth-флоу (RBAC/ABAC/JWT-claims) — `ucp-auth-review`. PII в логах — `ucp-node-observability-review`.
- CI/Dockerfile-композиция bootstrap — `ucp-node-bootstrap-review`.

$ARGUMENTS
