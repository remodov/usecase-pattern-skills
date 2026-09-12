# Security — реализация на Node (eslint-plugin-security / semgrep / npm audit / osv-scanner / Trivy / argon2)

Реализация язык-нейтрального контракта `../spec.md` (`R-SEC-*`) на Node. Коды общие с Java; меняется
набор инструментов:

| Слой | Java | Node |
|---|---|---|
| SAST по коду | Error Prone+NullAway, SpotBugs+FindSecBugs | `tsc --noEmit` strict (`strictNullChecks` = null-safety), `eslint` + `typescript-eslint` + `eslint-plugin-security`, `semgrep` |
| CVE зависимостей | OWASP Dependency-Check | `npm audit` / `osv-scanner` (OSV DB) |
| Секреты | Gitleaks | Gitleaks (язык-агностичен) |
| Образ | Trivy | Trivy |
| Пароли | BCrypt | `argon2` (предпочт.) / `bcrypt` |

`security/high-severity-breaks-build` — сборка падает на HIGH/CRITICAL finding (`npm audit --audit-level=high`; `eslint --max-warnings 0`
для security-правил; `|| true` в CI запрещён). `security/checks-layered-by-feedback-speed` — расслоение по скорости: tsc/eslint (каждый build/PR),
Gitleaks (pre-commit), npm audit/osv-scanner/Trivy (merge в main/nightly/release). `security/suppressions-are-files-with-deadline` —
suppressions/baselines — файлы в репо (`eslint.config.mjs` overrides, `.gitleaks.toml`, `osv-scanner.toml`
ignore-list, `audit-ci.json`), не разрозненные `// eslint-disable` без причины; каждое исключение — причина +
срок. `security/baseline-blocks-new-findings` — baseline на release: блокировать только **новые** findings.

## 1. SAST по коду (`R-SEC-SAST-*`)

`security/compile-time-analysis-enabled` — статанализ на каждом build: `tsc --noEmit` в `strict` (null-safety через `strictNullChecks`,
cross-ref `nest-bootstrap/layout-directs-dependencies-inward`) + `eslint` с `typescript-eslint` strict-пресетом. `security/code-security-scanner-required` —
`eslint-plugin-security` (+ `semgrep` с security-rulesets, например `p/typescript` + `p/nodejs`) обязательны:
injection (`child_process.exec` с конкатенацией, `eval`/`new Function`), path traversal
(`detect-non-literal-fs-filename`), небезопасные regex (ReDoS), weak crypto, hardcoded credentials; SARIF для
GitHub code scanning. `security/high-severity-breaks-build` — severity: HIGH/CRITICAL eslint-security/semgrep → fail; MEDIUM — отчёт +
комментарий; LOW — игнор. `security/suppressions-are-files-with-deadline` — suppressions
`// eslint-disable-next-line security/<rule> -- justify: ... до: YYYY-MM-DD` / semgrep `# nosemgrep: <rule-id>`
с причиной и датой.

`security/suppressions-are-files-with-deadline` ❌ `// eslint-disable` / `nosemgrep` без кода правила и justification (≥30 символов).

## 2. CVE в зависимостях (`R-SEC-DEP-*`)

`security/checks-layered-by-feedback-speed` — `npm audit --audit-level=high` (или `osv-scanner --lockfile package-lock.json` — шире база,
SARIF из коробки) обязателен; на merge в main + nightly + release. `security/dependency-updates-automated` — Renovate/Dependabot для
авто-PR (minor/patch авто, major — review). `security/high-severity-breaks-build` — severity: CVSS ≥ 7.0 ломает сборку; 4.0–6.9 —
отчёт + 30 дней; ниже — игнор. `security/suppressions-are-files-with-deadline` — suppressions с обоснованием/сроком (`osv-scanner.toml`
`[[IgnoredVulns]]` c `reason`; для транзитивных фиксов — `overrides` в `package.json`); lock-файл
(`package-lock.json`/`pnpm-lock.yaml`) коммитится, CI ставит через `npm ci` (воспроизводимость).

`security/suppressions-are-files-with-deadline` ❌ бессрочное подавление CVE (без срока в `reason`). `security/dependency-updates-automated` ❌ незапиненные/pre-release
зависимости в проде (`*`/`next`-теги, установка без lock-файла).

## 3. Секреты (`R-SEC-SECRET-*`)

`security/secret-scanning-before-push` — Gitleaks в pre-commit + CI + full history раз в неделю; `.gitleaks.toml` в корне.
`security/secret-scanning-before-push` — pre-commit hook через `husky` (`"prepare": "husky"` в `package.json`) — коммитится,
ставится одной командой `npm ci`. `security/leaked-secret-rotated-first` — утёк секрет — rotate в течение часа, затем чистка истории.

`security/no-secret-values-in-config` ❌ секреты в конфиге/коде — только env / secret-store, читаются валидируемым конфигом
(`nest-bootstrap/config-validated-at-startup`, `auth-patterns/no-secrets-in-repository`); локально `.env` (в `.gitignore`). `security/no-secret-values-in-config` ❌ закоммиченный `.env`
(даже example) — `.env.example` без значений.

## 4. Container/image (`R-SEC-IMG-*`)

`security/image-scanning-before-push` — Trivy на все образы в CI до push. `security/image-pinned-and-nonroot` — base image `node:22-slim` /
`gcr.io/distroless/nodejs22`, закреплён digest (`@sha256:`), не `:latest`. `security/image-pinned-and-nonroot` — non-root: в
`node`-образах есть готовый пользователь — `USER node` (или `USER 1000:1000` в distroless-вариантах без него).
`security/image-pinned-and-nonroot` — health/readiness probe (`@nestjs/terminus`, `nest-bootstrap/liveness-and-readiness-split`); `CMD ["node", "dist/main.js"]`
напрямую, не через `npm start` (npm глотает SIGTERM — ломает graceful shutdown).

`security/image-pinned-and-nonroot` ❌ контейнер от root. `security/image-pinned-and-nonroot` ❌ `:latest` base image (невоспроизводимо).

## 5. Криптография (`R-SEC-CRYPTO-*`)

Всё — через **`node:crypto`** и проверенные обёртки; самописные примитивы запрещены.

`security/passwords-hashed-with-kdf` — пароли — `argon2` (npm `argon2`, argon2id) или `bcrypt`; никогда
`createHash('md5'|'sha1'|'sha256')` без salt+KDF. `security/csprng-for-security-values` — рандом для security —
`crypto.randomBytes`/`crypto.randomUUID`/`crypto.randomInt`, не `Math.random` (он — только не-security:
jitter/shuffle). `security/authenticated-encryption-only` — симметричное — `createCipheriv('aes-256-gcm', key, iv)` с 12-байтным
рандомным IV на каждое шифрование; не ECB, не CBC без MAC:

```ts
// PREFER
const iv = randomBytes(12);
const cipher = createCipheriv('aes-256-gcm', key, iv);
// AVOID
createCipheriv('aes-256-ecb', key, null);          // ECB — паттерны открытого текста видны
createHash('md5').update(password).digest('hex'); // не KDF
```

`security/modern-tls-only` — TLS ≥ 1.2 (Node-дефолт `tls.DEFAULT_MIN_VERSION = 'TLSv1.2'` не понижать; 1.0/1.1 — off на
reverse-proxy). `security/token-validated-by-library` — JWT-верификация через библиотеку с проверкой подписи и JWKS
(`passport-jwt` + `jwks-rsa`, `auth-patterns/token-validated-by-library`); `jwt.decode()` без `verify` — критично.

`security/no-hardcoded-keys` ❌ hardcoded ключи/IV в коде — secret-store/KMS, инжект через env.

## 6. Реакция на findings (`R-SEC-FIND-*`)

`security/high-severity-breaks-build` — severity → SLA: CRITICAL — сборка падает, hotfix ≤24ч; HIGH — падает, патч ≤2 нед; MEDIUM —
≤30 дней; LOW — игнор. `security/suppressions-are-files-with-deadline` — suppressions со сроком; квартальный отчёт «просроченные».
`security/code-security-scanner-required` — SARIF в GitHub Security tab (semgrep/osv-scanner/Trivy отдают SARIF; eslint — через
`@microsoft/eslint-formatter-sarif`).

`security/every-finding-gets-a-decision` ❌ игнор finding «не уверен» молчанием — либо suppression с обоснованием, либо фикс.

## 7. Чеклист подключения к новому сервису (Node/NestJS)

1. `tsc --noEmit` strict + eslint(`typescript-eslint` + `eslint-plugin-security`) (+ semgrep) в CI с fail на
   HIGH/CRITICAL; suppressions со сроком.
2. `npm audit`/osv-scanner + Trivy на main/release; lock-файл коммитится, `npm ci`; нет бессрочных подавлений.
3. Gitleaks pre-commit (husky) + CI; секреты только через env/secret-store; нет закоммиченного `.env`.
4. Образ: digest-pinned base, `USER node`, probe, `node dist/main.js` (не `npm start`); не `:latest`/root.
5. Крипта: argon2/bcrypt, `crypto.randomBytes`/`randomUUID`, AES-GCM; нет md5/sha1/ECB/`Math.random`/hardcoded ключей.
6. Findings → SLA по severity; SARIF в Security tab.
