# Security — Python Style Guide (bandit / semgrep / pip-audit / Trivy / argon2)

Реализация язык-нейтрального контракта `../security-rules.md` (`R-SEC-*`) на Python. Коды общие с Java; меняется
набор инструментов:

| Слой | Java | Python |
|---|---|---|
| SAST по коду | Error Prone+NullAway, SpotBugs+FindSecBugs | `bandit`, `semgrep`, ruff `S`-правила (bandit-derived), `mypy --strict` (null-safety) |
| CVE зависимостей | OWASP Dependency-Check | `pip-audit` (PyPA) / `safety`, Trivy |
| Секреты | Gitleaks | Gitleaks (язык-агностичен) |
| Образ | Trivy | Trivy |
| Пароли | BCrypt | `argon2-cffi` (предпочт.) / `bcrypt` |

`R-SEC-1` — сборка падает на HIGH/CRITICAL finding (CI `--exit-zero` запрещён). `R-SEC-2` — расслоение по скорости:
ruff/bandit/mypy (каждый build/PR), Gitleaks (pre-commit), pip-audit/Trivy (merge в main/nightly/release).
`R-SEC-3` — suppressions/baselines — файлы в репо (`.bandit`/`pyproject [tool.bandit]`, `.gitleaks.toml`, pip-audit
ignore-list), не разрозненные `# nosec` без причины; каждое исключение — причина + срок. `R-SEC-4` — baseline на
release: блокировать только **новые** findings.

## 1. SAST по коду (`R-SEC-SAST-*`)

`R-SEC-SAST-1` — статанализ на каждом build: `ruff` (включая `S`-набор) + `mypy --strict` (null-safety, cross-ref
`PY-6.1`). `R-SEC-SAST-2` — `bandit` (+ `semgrep` с security-rulesets) обязательны: SQLi, command injection,
hardcoded passwords, weak crypto, `eval`/`exec`, небезопасная десериализация; SARIF для GitHub code scanning.
`R-SEC-SAST-3` — severity: HIGH/CRITICAL bandit/semgrep → fail; MEDIUM — отчёт + комментарий; LOW — игнор.
`R-SEC-SAST-4` — suppressions `# nosec BXXX  # justify: ... до: YYYY-MM-DD` / `[tool.bandit] skips` с причиной и датой.

`R-SEC-SAST-X1` — `# nosec` без кода и justification (≥30 символов).

## 2. CVE в зависимостях (`R-SEC-DEP-*`)

`R-SEC-DEP-1` — `pip-audit` (PyPA Advisory DB) обязателен; на merge в main + nightly + release. `R-SEC-DEP-2` —
Renovate/Dependabot для авто-PR (minor/patch авто, major — review). `R-SEC-DEP-3` — severity: CVSS ≥ 7.0 ломает
сборку; 4.0–6.9 — отчёт + 30 дней; ниже — игнор. `R-SEC-DEP-4` — suppressions с обоснованием/сроком; lock-файл
(`uv.lock`/`poetry.lock`) коммитится (воспроизводимость).

`R-SEC-DEP-X1` — бессрочное подавление CVE (без `until`). `R-SEC-DEP-X2` — незапиненные/pre-release зависимости в
проде (`>=`-диапазоны без lock).

## 3. Секреты (`R-SEC-SECRET-*`)

`R-SEC-SECRET-1` — Gitleaks в pre-commit + CI + full history раз в неделю; `.gitleaks.toml` в корне. `R-SEC-SECRET-2` —
pre-commit hook через `pre-commit`-framework, коммитится, ставится одной командой. `R-SEC-SECRET-3` — утёк секрет —
rotate в течение часа, затем чистка истории.

`R-SEC-SECRET-X1` — секреты в `settings`/yaml — только `${ENV_VAR}` / secret-store; локально `.env` (в `.gitignore`).
`R-SEC-SECRET-X2` — закоммиченный `.env` (даже example) — `.env.example` без значений.

## 4. Container/image (`R-SEC-IMG-*`)

`R-SEC-IMG-1` — Trivy на все образы в CI до push. `R-SEC-IMG-2` — base image `python:3.12-slim` / distroless,
закреплён digest (`@sha256:`), не `:latest`. `R-SEC-IMG-3` — non-root (`USER 1000:1000`). `R-SEC-IMG-4` — health/
readiness probe.

`R-SEC-IMG-X1` — контейнер от root. `R-SEC-IMG-X2` — `:latest` base image (невоспроизводимо).

## 5. Криптография (`R-SEC-CRYPTO-*`)

`R-SEC-CRYPTO-1` — пароли — `argon2-cffi` (или `bcrypt`), никогда `hashlib.md5`/`sha1`/`sha256` без salt+KDF.
`R-SEC-CRYPTO-2` — рандом для security — модуль **`secrets`** (`secrets.token_*`), не `random` (`random` — только
не-security: jitter/shuffle). `R-SEC-CRYPTO-3` — симметричное — `cryptography` AES-GCM (`AESGCM`) с рандомным nonce;
не AES-ECB, не CBC без MAC. `R-SEC-CRYPTO-4` — TLS ≥ 1.2. `R-SEC-CRYPTO-5` — JWT-верификация через библиотеку с
проверкой подписи (`AUTH-4`); ручной парсинг без подписи — критично.

`R-SEC-CRYPTO-X1` — hardcoded ключи/nonce в коде — secret-store/KMS, инжект через env.

## 6. Реакция на findings (`R-SEC-FIND-*`)

`R-SEC-FIND-1` — severity → SLA: CRITICAL — сборка падает, hotfix ≤24ч; HIGH — падает, патч ≤2 нед; MEDIUM — ≤30
дней; LOW — игнор. `R-SEC-FIND-2` — suppressions со сроком (`until`); квартальный отчёт «просроченные». `R-SEC-FIND-3` —
SARIF в GitHub Security tab (bandit/Trivy/pip-audit).

`R-SEC-FIND-X1` — игнор finding «не уверен» молчанием — либо suppression с обоснованием, либо фикс.

## 7. Чеклист подключения к новому сервису (Python)

1. ruff(`S`)+bandit(+semgrep)+mypy в CI с fail на HIGH/CRITICAL; suppressions со сроком.
2. pip-audit + Trivy на main/release; lock-файл коммитится; нет бессрочных подавлений.
3. Gitleaks pre-commit+CI; секреты только через env/secret-store; нет закоммиченного `.env`.
4. Образ: digest-pinned base, non-root, probe; не `:latest`/root.
5. Крипта: argon2/bcrypt, `secrets`, AES-GCM; нет md5/sha1/ECB/hardcoded ключей.
6. Findings → SLA по severity; SARIF в Security tab.
