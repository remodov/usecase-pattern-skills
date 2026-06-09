---
name: ucp-py-security-review
lang: python
description: Ревью Python-сервиса по security-style-guide (коды R-SEC-*) — SAST в CI (ruff S, bandit, semgrep, mypy --strict), pip-audit/Trivy на CVE, Gitleaks, suppressions со сроком, Dockerfile non-root, криптография без md5/AES-ECB.
when_to_use: Ревью pyproject/CI-конфигов, Dockerfile, settings, suppression-файлов, кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Security (Python / bandit + pip-audit + Trivy + argon2)

Ты ревьюишь security на соответствие **контракту** `backend/security/security-rules.md` (`R-SEC-*`) и **Python-реализации** `backend/security/python/security-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/security/security-rules.md`** + **`backend/security/python/security-style-guide.md`**.
- Парные: `auth-patterns` (`AUTH-4`/`AUTH-17`), `observability` (`AUTH-16` PII), `python-bootstrap` (CI/Dockerfile).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-SEC-CRYPTO-1`, `R-SEC-IMG-X1`), не префикс.

2. **Скоп.** `pyproject.toml` (`[tool.ruff]`/`[tool.bandit]`/`[tool.mypy]`), `.github/workflows/*`, `Dockerfile`, `settings`, `.gitleaks.toml`, suppression-файлы, код с криптографией; `git diff`.

3. **Прогон.**
   - **Enforcement (`R-SEC-1..4`):** CI падает на HIGH/CRITICAL (`--exit-zero`/без fail → `R-SEC-1`); расслоение по скорости; suppressions — файлы со сроком, не россыпь.
   - **SAST (`R-SEC-SAST-*`):** ruff(`S`)+bandit(+semgrep)+`mypy --strict` в CI; `# nosec` без кода/justify → `R-SEC-SAST-X1`.
   - **CVE (`R-SEC-DEP-*`):** pip-audit+Trivy на main/release; CVSS≥7 ломает; lock-файл коммитится. Бессрочное подавление → `R-SEC-DEP-X1`; `>=`-диапазоны без lock → `R-SEC-DEP-X2`.
   - **Секреты (`R-SEC-SECRET-*`):** Gitleaks pre-commit+CI; секреты в settings/yaml/коде → `R-SEC-SECRET-X1`; закоммиченный `.env` → `R-SEC-SECRET-X2`.
   - **Образ (`R-SEC-IMG-*`):** Trivy; digest-pinned base; non-root. Root → `R-SEC-IMG-X1`; `:latest` → `R-SEC-IMG-X2`.
   - **Крипта (`R-SEC-CRYPTO-*`):** argon2/bcrypt (md5/sha1 для паролей → `R-SEC-CRYPTO-1`); `secrets` (не `random` → `R-SEC-CRYPTO-2`); AES-GCM (ECB/CBC-без-MAC → `R-SEC-CRYPTO-3`); JWT через библиотеку (ручной без подписи → `R-SEC-CRYPTO-5`); hardcoded ключи → `R-SEC-CRYPTO-X1`.
   - **Findings (`R-SEC-FIND-*`):** SLA по severity; suppressions со сроком (`R-SEC-FIND-2`); SARIF в Security tab; молчаливый игнор → `R-SEC-FIND-X1`.

4. **Cross-check:** JWT-валидация/секреты в auth-флоу — `ucp-py-auth-review`; PII в логах — `ucp-py-observability-review`; CI/Dockerfile wiring — `ucp-py-bootstrap-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — md5/sha1 для паролей или `random` для security или AES-ECB (`R-SEC-CRYPTO-1/2/3`), hardcoded ключи (`R-SEC-CRYPTO-X1`), секреты в коде/git (`R-SEC-SECRET-X1`), контейнер от root (`R-SEC-IMG-X1`), CI без fail на CRITICAL (`R-SEC-1`), ручной JWT без подписи (`R-SEC-CRYPTO-5`).
   - **Предупреждение** — `# nosec`/suppression без срока (`R-SEC-SAST-X1`/`R-SEC-DEP-X1`), `:latest` base (`R-SEC-IMG-X2`), нет lock-файла (`R-SEC-DEP-X2`), Gitleaks не в pre-commit.
   - **Замечание** — semgrep не подключён, нет SARIF в Security tab (`R-SEC-FIND-3`), MEDIUM без отчёта.

## Что не входит

- Auth-флоу (RBAC/ABAC/JWT-claims) — `ucp-py-auth-review`. PII в логах — `ucp-py-observability-review`.
- CI/Dockerfile-композиция bootstrap — `ucp-py-bootstrap-review`.

$ARGUMENTS
