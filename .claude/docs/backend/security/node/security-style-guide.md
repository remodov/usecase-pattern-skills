# Security — Node Style Guide (eslint-plugin-security / semgrep / npm audit / osv-scanner / Trivy / argon2)

Реализация язык-нейтрального контракта `../security-rules.md` (`R-SEC-*`) на Node. Коды общие с Java; меняется
набор инструментов:

| Слой | Java | Node |
|---|---|---|
| SAST по коду | Error Prone+NullAway, SpotBugs+FindSecBugs | `tsc --noEmit` strict (`strictNullChecks` = null-safety), `eslint` + `typescript-eslint` + `eslint-plugin-security`, `semgrep` |
| CVE зависимостей | OWASP Dependency-Check | `npm audit` / `osv-scanner` (OSV DB) |
| Секреты | Gitleaks | Gitleaks (язык-агностичен) |
| Образ | Trivy | Trivy |
| Пароли | BCrypt | `argon2` (предпочт.) / `bcrypt` |

`R-SEC-1` — сборка падает на HIGH/CRITICAL finding (`npm audit --audit-level=high`; `eslint --max-warnings 0`
для security-правил; `|| true` в CI запрещён). `R-SEC-2` — расслоение по скорости: tsc/eslint (каждый build/PR),
Gitleaks (pre-commit), npm audit/osv-scanner/Trivy (merge в main/nightly/release). `R-SEC-3` —
suppressions/baselines — файлы в репо (`eslint.config.mjs` overrides, `.gitleaks.toml`, `osv-scanner.toml`
ignore-list, `audit-ci.json`), не разрозненные `// eslint-disable` без причины; каждое исключение — причина +
срок. `R-SEC-4` — baseline на release: блокировать только **новые** findings.

## 1. SAST по коду (`R-SEC-SAST-*`)

`R-SEC-SAST-1` — статанализ на каждом build: `tsc --noEmit` в `strict` (null-safety через `strictNullChecks`,
cross-ref `NESTBOOT-15`) + `eslint` с `typescript-eslint` strict-пресетом. `R-SEC-SAST-2` —
`eslint-plugin-security` (+ `semgrep` с security-rulesets, например `p/typescript` + `p/nodejs`) обязательны:
injection (`child_process.exec` с конкатенацией, `eval`/`new Function`), path traversal
(`detect-non-literal-fs-filename`), небезопасные regex (ReDoS), weak crypto, hardcoded credentials; SARIF для
GitHub code scanning. `R-SEC-SAST-3` — severity: HIGH/CRITICAL eslint-security/semgrep → fail; MEDIUM — отчёт +
комментарий; LOW — игнор. `R-SEC-SAST-4` — suppressions
`// eslint-disable-next-line security/<rule> -- justify: ... до: YYYY-MM-DD` / semgrep `# nosemgrep: <rule-id>`
с причиной и датой.

`R-SEC-SAST-X1` ❌ `// eslint-disable` / `nosemgrep` без кода правила и justification (≥30 символов).

## 2. CVE в зависимостях (`R-SEC-DEP-*`)

`R-SEC-DEP-1` — `npm audit --audit-level=high` (или `osv-scanner --lockfile package-lock.json` — шире база,
SARIF из коробки) обязателен; на merge в main + nightly + release. `R-SEC-DEP-2` — Renovate/Dependabot для
авто-PR (minor/patch авто, major — review). `R-SEC-DEP-3` — severity: CVSS ≥ 7.0 ломает сборку; 4.0–6.9 —
отчёт + 30 дней; ниже — игнор. `R-SEC-DEP-4` — suppressions с обоснованием/сроком (`osv-scanner.toml`
`[[IgnoredVulns]]` c `reason`; для транзитивных фиксов — `overrides` в `package.json`); lock-файл
(`package-lock.json`/`pnpm-lock.yaml`) коммитится, CI ставит через `npm ci` (воспроизводимость).

`R-SEC-DEP-X1` ❌ бессрочное подавление CVE (без срока в `reason`). `R-SEC-DEP-X2` ❌ незапиненные/pre-release
зависимости в проде (`*`/`next`-теги, установка без lock-файла).

## 3. Секреты (`R-SEC-SECRET-*`)

`R-SEC-SECRET-1` — Gitleaks в pre-commit + CI + full history раз в неделю; `.gitleaks.toml` в корне.
`R-SEC-SECRET-2` — pre-commit hook через `husky` (`"prepare": "husky"` в `package.json`) — коммитится,
ставится одной командой `npm ci`. `R-SEC-SECRET-3` — утёк секрет — rotate в течение часа, затем чистка истории.

`R-SEC-SECRET-X1` ❌ секреты в конфиге/коде — только env / secret-store, читаются валидируемым конфигом
(`NESTBOOT-4`, `AUTH-17`); локально `.env` (в `.gitignore`). `R-SEC-SECRET-X2` ❌ закоммиченный `.env`
(даже example) — `.env.example` без значений.

## 4. Container/image (`R-SEC-IMG-*`)

`R-SEC-IMG-1` — Trivy на все образы в CI до push. `R-SEC-IMG-2` — base image `node:22-slim` /
`gcr.io/distroless/nodejs22`, закреплён digest (`@sha256:`), не `:latest`. `R-SEC-IMG-3` — non-root: в
`node`-образах есть готовый пользователь — `USER node` (или `USER 1000:1000` в distroless-вариантах без него).
`R-SEC-IMG-4` — health/readiness probe (`@nestjs/terminus`, `NESTBOOT-13`); `CMD ["node", "dist/main.js"]`
напрямую, не через `npm start` (npm глотает SIGTERM — ломает graceful shutdown).

`R-SEC-IMG-X1` ❌ контейнер от root. `R-SEC-IMG-X2` ❌ `:latest` base image (невоспроизводимо).

## 5. Криптография (`R-SEC-CRYPTO-*`)

Всё — через **`node:crypto`** и проверенные обёртки; самописные примитивы запрещены.

`R-SEC-CRYPTO-1` — пароли — `argon2` (npm `argon2`, argon2id) или `bcrypt`; никогда
`createHash('md5'|'sha1'|'sha256')` без salt+KDF. `R-SEC-CRYPTO-2` — рандом для security —
`crypto.randomBytes`/`crypto.randomUUID`/`crypto.randomInt`, не `Math.random` (он — только не-security:
jitter/shuffle). `R-SEC-CRYPTO-3` — симметричное — `createCipheriv('aes-256-gcm', key, iv)` с 12-байтным
рандомным IV на каждое шифрование; не ECB, не CBC без MAC:

```ts
// PREFER
const iv = randomBytes(12);
const cipher = createCipheriv('aes-256-gcm', key, iv);
// AVOID
createCipheriv('aes-256-ecb', key, null);          // ECB — паттерны открытого текста видны
createHash('md5').update(password).digest('hex'); // не KDF
```

`R-SEC-CRYPTO-4` — TLS ≥ 1.2 (Node-дефолт `tls.DEFAULT_MIN_VERSION = 'TLSv1.2'` не понижать; 1.0/1.1 — off на
reverse-proxy). `R-SEC-CRYPTO-5` — JWT-верификация через библиотеку с проверкой подписи и JWKS
(`passport-jwt` + `jwks-rsa`, `AUTH-4`); `jwt.decode()` без `verify` — критично.

`R-SEC-CRYPTO-X1` ❌ hardcoded ключи/IV в коде — secret-store/KMS, инжект через env.

## 6. Реакция на findings (`R-SEC-FIND-*`)

`R-SEC-FIND-1` — severity → SLA: CRITICAL — сборка падает, hotfix ≤24ч; HIGH — падает, патч ≤2 нед; MEDIUM —
≤30 дней; LOW — игнор. `R-SEC-FIND-2` — suppressions со сроком; квартальный отчёт «просроченные».
`R-SEC-FIND-3` — SARIF в GitHub Security tab (semgrep/osv-scanner/Trivy отдают SARIF; eslint — через
`@microsoft/eslint-formatter-sarif`).

`R-SEC-FIND-X1` ❌ игнор finding «не уверен» молчанием — либо suppression с обоснованием, либо фикс.

## 7. Чеклист подключения к новому сервису (Node/NestJS)

1. `tsc --noEmit` strict + eslint(`typescript-eslint` + `eslint-plugin-security`) (+ semgrep) в CI с fail на
   HIGH/CRITICAL; suppressions со сроком.
2. `npm audit`/osv-scanner + Trivy на main/release; lock-файл коммитится, `npm ci`; нет бессрочных подавлений.
3. Gitleaks pre-commit (husky) + CI; секреты только через env/secret-store; нет закоммиченного `.env`.
4. Образ: digest-pinned base, `USER node`, probe, `node dist/main.js` (не `npm start`); не `:latest`/root.
5. Крипта: argon2/bcrypt, `crypto.randomBytes`/`randomUUID`, AES-GCM; нет md5/sha1/ECB/`Math.random`/hardcoded ключей.
6. Findings → SLA по severity; SARIF в Security tab.
