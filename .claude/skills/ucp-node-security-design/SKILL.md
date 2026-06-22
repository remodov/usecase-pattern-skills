---
name: ucp-node-security-design
lang: node
description: Зашаблонить security-обвязку Node/NestJS-сервиса по UCP (коды R-SEC-*) — SAST в CI (tsc strict, eslint-plugin-security, semgrep), npm audit/osv-scanner/Trivy на CVE, Gitleaks, non-root образ, криптография (argon2, AES-GCM).
when_to_use: Триггеры — «настрой security-сканеры», «npm audit/eslint-security в CI», «harden Dockerfile». Старт сервиса или добавление security-CI.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Security — проектирование (Node / eslint-plugin-security + npm audit + Trivy + argon2)

Ты настраиваешь security-обвязку по **контракту** `backend/security/security-rules.md` (`R-SEC-*`) и **Node-реализации** `backend/security/node/security-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `auth-patterns` (auth-флоу, `AUTH-4`/`AUTH-17`), `observability` (PII `AUTH-16`), `node/nest-bootstrap` (CI/Dockerfile wiring, `NESTBOOT-4`/`NESTBOOT-13`/`NESTBOOT-15`).

2. **SAST** (`R-SEC-SAST-*`): `tsc --noEmit` в `strict` (`strictNullChecks` — null-safety) + `eslint` с `typescript-eslint` strict-пресетом + `eslint-plugin-security` (injection, path traversal, ReDoS, weak crypto, hardcoded credentials) + `semgrep` (`p/typescript`, `p/nodejs`) в CI; fail на HIGH/CRITICAL (`eslint --max-warnings 0` для security-правил); `|| true` запрещён; suppressions `// eslint-disable-next-line security/<rule> -- justify: ... до: YYYY-MM-DD` / semgrep `# nosemgrep: <rule-id>` с причиной и датой; SARIF в GitHub Security tab (`@microsoft/eslint-formatter-sarif`).

3. **CVE** (`R-SEC-DEP-*`): `npm audit --audit-level=high` / `osv-scanner --lockfile package-lock.json` + Trivy на merge в main/nightly/release; Renovate/Dependabot; CVSS ≥ 7.0 ломает сборку; `package-lock.json`/`pnpm-lock.yaml` коммитится, CI ставит через `npm ci`; suppressions `osv-scanner.toml` `[[IgnoredVulns]]` с `reason` + сроком; `overrides` в `package.json` для транзитивных фиксов.

4. **Секреты** (`R-SEC-SECRET-*`): Gitleaks pre-commit (через `husky`, `"prepare": "husky"` в `package.json`) + CI + weekly full-history; секреты через env/secret-store, читаются валидируемым конфигом (`NESTBOOT-4`); `.env` в `.gitignore`, `.env.example` без значений; `.gitleaks.toml` в корне.

5. **Образ** (`R-SEC-IMG-*`): Trivy в CI после сборки до push; base `node:22-slim` / `gcr.io/distroless/nodejs22` digest-pinned (`@sha256:`); `USER node` (или `USER 1000:1000` в distroless); probe (`@nestjs/terminus`, `NESTBOOT-13`); `CMD ["node", "dist/main.js"]` — не `npm start` (npm глотает SIGTERM).

6. **Криптография** (`R-SEC-CRYPTO-*`): пароли — `argon2` (argon2id) или `bcrypt`; никогда `createHash('md5'|'sha1'|'sha256')` без salt+KDF (`R-SEC-CRYPTO-1`); рандом для security — `crypto.randomBytes`/`crypto.randomUUID`/`crypto.randomInt` (не `Math.random` — `R-SEC-CRYPTO-2`); симметричное — `createCipheriv('aes-256-gcm', key, iv)` с 12-байтным рандомным IV на каждое шифрование (не ECB, не CBC без MAC — `R-SEC-CRYPTO-3`); TLS ≥ 1.2 (не понижать `tls.DEFAULT_MIN_VERSION`); JWT через библиотеку с `verify` + JWKS (`passport-jwt` + `jwks-rsa`, `AUTH-4`); `jwt.decode()` без `verify` — критично (`R-SEC-CRYPTO-5`); ключи через secret-store/KMS, инжект через env.

7. **Findings** (`R-SEC-FIND-*`): SLA по severity (CRITICAL — hotfix ≤24ч, HIGH — ≤2 нед, MEDIUM — ≤30 дней); suppressions со сроком; квартальный отчёт «просроченные»; SARIF (semgrep/osv-scanner/Trivy/eslint) в Security tab. Самопроверка по чеклисту (§7 Node-style-guide) + предложи `ucp-node-security-review`.

## Антипаттерны, которые НЕ генерировать

- CI без fail на HIGH/CRITICAL (`R-SEC-1`); `|| true` в CI-шаге сканирования; `// eslint-disable` / `nosemgrep` без кода правила и justify (`R-SEC-SAST-X1`); бессрочное подавление CVE (`R-SEC-DEP-X1`); незапиненные/pre-release зависимости (`R-SEC-DEP-X2`).
- Секреты в коде/конфиге (`R-SEC-SECRET-X1`); закоммиченный `.env` (`R-SEC-SECRET-X2`).
- Контейнер от root (`R-SEC-IMG-X1`); `:latest` base (`R-SEC-IMG-X2`); `npm start` в `CMD`.
- `createHash('md5'|'sha1')` для паролей / `Math.random` для security / `createCipheriv('aes-256-ecb', ...)` (`R-SEC-CRYPTO-1/2/3`); hardcoded ключи/IV (`R-SEC-CRYPTO-X1`); `jwt.decode()` без `verify` (`R-SEC-CRYPTO-5`).

После работы скилла — обязательно `ucp-node-security-review`.

$ARGUMENTS
