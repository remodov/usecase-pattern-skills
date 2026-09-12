---
name: ucp-py-security-review
lang: python
description: Ревью Python-сервиса по требованиям `security/*` — SAST в CI (ruff S, bandit, semgrep, mypy --strict), pip-audit/Trivy на CVE, Gitleaks, suppressions со сроком, Dockerfile non-root, криптография без md5/AES-ECB.
when_to_use: Ревью pyproject/CI-конфигов, Dockerfile, settings, suppression-файлов, кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Security (Python / bandit + pip-audit + Trivy + argon2)

Ты ревьюишь security на соответствие **контракту** `backend/security/spec.md` (`R-SEC-*`) и **Python-реализации** `backend/security/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/security/spec.md`** + **`backend/security/references/python/implementation.md`**.
- Парные: `auth-patterns` (`auth-patterns/token-validated-by-library`/`auth-patterns/no-secrets-in-repository`), `observability` (`auth-patterns/no-pii-in-logs-and-events` PII), `python-bootstrap` (CI/Dockerfile).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`security/passwords-hashed-with-kdf`, `security/image-pinned-and-nonroot`), не префикс.

2. **Скоп.** `pyproject.toml` (`[tool.ruff]`/`[tool.bandit]`/`[tool.mypy]`), `.github/workflows/*`, `Dockerfile`, `settings`, `.gitleaks.toml`, suppression-файлы, код с криптографией; `git diff`.

3. **Прогон.**
   - **Enforcement (`R-SEC-1..4`):** CI падает на HIGH/CRITICAL (`--exit-zero`/без fail → `security/high-severity-breaks-build`); расслоение по скорости; suppressions — файлы со сроком, не россыпь.
   - **SAST (`R-SEC-SAST-*`):** ruff(`S`)+bandit(+semgrep)+`mypy --strict` в CI; `# nosec` без кода/justify → `security/suppressions-are-files-with-deadline`.
   - **CVE (`R-SEC-DEP-*`):** pip-audit+Trivy на main/release; CVSS≥7 ломает; lock-файл коммитится. Бессрочное подавление → `security/suppressions-are-files-with-deadline`; `>=`-диапазоны без lock → `security/dependency-updates-automated`.
   - **Секреты (`R-SEC-SECRET-*`):** Gitleaks pre-commit+CI; секреты в settings/yaml/коде → `security/no-secret-values-in-config`; закоммиченный `.env` → `security/no-secret-values-in-config`.
   - **Образ (`R-SEC-IMG-*`):** Trivy; digest-pinned base; non-root. Root → `security/image-pinned-and-nonroot`; `:latest` → `security/image-pinned-and-nonroot`.
   - **Крипта (`R-SEC-CRYPTO-*`):** argon2/bcrypt (md5/sha1 для паролей → `security/passwords-hashed-with-kdf`); `secrets` (не `random` → `security/csprng-for-security-values`); AES-GCM (ECB/CBC-без-MAC → `security/authenticated-encryption-only`); JWT через библиотеку (ручной без подписи → `security/token-validated-by-library`); hardcoded ключи → `security/no-hardcoded-keys`.
   - **Findings (`R-SEC-FIND-*`):** SLA по severity; suppressions со сроком (`security/suppressions-are-files-with-deadline`); SARIF в Security tab; молчаливый игнор → `security/every-finding-gets-a-decision`.

4. **Cross-check:** JWT-валидация/секреты в auth-флоу — `ucp-py-auth-review`; PII в логах — `ucp-py-observability-review`; CI/Dockerfile wiring — `ucp-py-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — md5/sha1 для паролей или `random` для security или AES-ECB (`R-SEC-CRYPTO-1/2/3`), hardcoded ключи (`security/no-hardcoded-keys`), секреты в коде/git (`security/no-secret-values-in-config`), контейнер от root (`security/image-pinned-and-nonroot`), CI без fail на CRITICAL (`security/high-severity-breaks-build`), ручной JWT без подписи (`security/token-validated-by-library`).
   - **Предупреждение** — `# nosec`/suppression без срока (`security/suppressions-are-files-with-deadline`/`security/suppressions-are-files-with-deadline`), `:latest` base (`security/image-pinned-and-nonroot`), нет lock-файла (`security/dependency-updates-automated`), Gitleaks не в pre-commit.
   - **Замечание** — semgrep не подключён, нет SARIF в Security tab (`security/code-security-scanner-required`), MEDIUM без отчёта.

## Что не входит

- Auth-флоу (RBAC/ABAC/JWT-claims) — `ucp-py-auth-review`. PII в логах — `ucp-py-observability-review`.
- CI/Dockerfile-композиция bootstrap — `ucp-py-bootstrap-review`.

$ARGUMENTS
