---
name: ucp-py-security-design
lang: python
description: Зашаблонить security-обвязку Python-сервиса по UCP (требования security/*) — SAST в CI (ruff S + bandit + semgrep + mypy --strict), CVE (pip-audit, Trivy), Gitleaks, digest-pinned non-root образ, криптография (argon2, secrets, AES-GCM).
when_to_use: Триггеры — «настрой security-сканеры», «bandit/pip-audit в CI», «harden Dockerfile». Старт сервиса или добавление security-CI.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(bandit*) Bash(pip-audit*) Bash(ruff*)
---

# Security — проектирование (Python / bandit + pip-audit + Trivy + argon2)

Ты настраиваешь security-обвязку по **контракту** `backend/security/spec.md` (`R-SEC-*`) и **Python-реализации** `backend/security/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `auth-patterns` (auth-флоу, `auth-patterns/token-validated-by-library`), `observability` (PII `auth-patterns/no-pii-in-logs-and-events`), `python-bootstrap` (CI/Dockerfile wiring).

2. **SAST** (`R-SEC-SAST-*`): `ruff` (`S`-набор) + `bandit` (+ `semgrep` security-rules) + `mypy --strict` в CI; fail на HIGH/CRITICAL; suppressions `# nosec BXXX # justify: ... до: дата`.

3. **CVE** (`R-SEC-DEP-*`): `pip-audit` (+ Trivy для зависимостей) на merge в main/nightly/release; Renovate/Dependabot; CVSS ≥ 7.0 ломает сборку; lock-файл (`uv.lock`/`poetry.lock`) коммитится.

4. **Секреты** (`R-SEC-SECRET-*`): Gitleaks pre-commit + CI + weekly full-history; секреты через env/secret-store; `.env` в `.gitignore`, `.env.example` без значений.

5. **Образ** (`R-SEC-IMG-*`): Trivy в CI; base `python:3.12-slim`/distroless digest-pinned; non-root `USER`; probe.

6. **Криптография** (`R-SEC-CRYPTO-*`): `argon2-cffi`/`bcrypt` для паролей; модуль `secrets` (не `random`); `cryptography` AES-GCM; JWT через библиотеку (`auth-patterns/token-validated-by-library`); ключи через secret-store.

7. **Findings** (`R-SEC-FIND-*`): SLA по severity; suppressions со сроком; SARIF в Security tab. Самопроверка (§7) + предложи `ucp-py-security-review`.

## Антипаттерны, которые НЕ генерировать

- CI без fail на HIGH/CRITICAL (`security/high-severity-breaks-build`); `# nosec` без кода/justify (`security/suppressions-are-files-with-deadline`); бессрочное подавление CVE (`security/suppressions-are-files-with-deadline`).
- Секреты в settings/yaml/коде (`security/no-secret-values-in-config`); закоммиченный `.env` (`security/no-secret-values-in-config`).
- Контейнер от root (`security/image-pinned-and-nonroot`); `:latest` base (`security/image-pinned-and-nonroot`).
- `hashlib.md5`/`sha1` для паролей / `random` для security / AES-ECB (`R-SEC-CRYPTO-1/2/3`); hardcoded ключи (`security/no-hardcoded-keys`); ручной JWT без подписи (`security/token-validated-by-library`).

После работы скилла — обязательно `ucp-py-security-review`.

$ARGUMENTS
