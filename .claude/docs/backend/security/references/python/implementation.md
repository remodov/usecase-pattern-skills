# Security — реализация на Python (bandit / semgrep / pip-audit / Trivy / argon2)

Реализация язык-нейтрального контракта `../spec.md` (`R-SEC-*`) на Python. Коды общие с Java; меняется
набор инструментов:

| Слой | Java | Python |
|---|---|---|
| SAST по коду | Error Prone+NullAway, SpotBugs+FindSecBugs | `bandit`, `semgrep`, ruff `S`-правила (bandit-derived), `mypy --strict` (null-safety) |
| CVE зависимостей | OWASP Dependency-Check | `pip-audit` (PyPA) / `safety`, Trivy |
| Секреты | Gitleaks | Gitleaks (язык-агностичен) |
| Образ | Trivy | Trivy |
| Пароли | BCrypt | `argon2-cffi` (предпочт.) / `bcrypt` |

`security/high-severity-breaks-build` — сборка падает на HIGH/CRITICAL finding (CI `--exit-zero` запрещён). `security/checks-layered-by-feedback-speed` — расслоение по скорости:
ruff/bandit/mypy (каждый build/PR), Gitleaks (pre-commit), pip-audit/Trivy (merge в main/nightly/release).
`security/suppressions-are-files-with-deadline` — suppressions/baselines — файлы в репо (`.bandit`/`pyproject [tool.bandit]`, `.gitleaks.toml`, pip-audit
ignore-list), не разрозненные `# nosec` без причины; каждое исключение — причина + срок. `security/baseline-blocks-new-findings` — baseline на
release: блокировать только **новые** findings.

## 1. SAST по коду (`R-SEC-SAST-*`)

`security/compile-time-analysis-enabled` — статанализ на каждом build: `ruff` (включая `S`-набор) + `mypy --strict` (null-safety, cross-ref
`python-style/typed-public-signatures`). `security/code-security-scanner-required` — `bandit` (+ `semgrep` с security-rulesets) обязательны: SQLi, command injection,
hardcoded passwords, weak crypto, `eval`/`exec`, небезопасная десериализация; SARIF для GitHub code scanning.
`security/high-severity-breaks-build` — severity: HIGH/CRITICAL bandit/semgrep → fail; MEDIUM — отчёт + комментарий; LOW — игнор.
`security/suppressions-are-files-with-deadline` — suppressions `# nosec BXXX  # justify: ... до: YYYY-MM-DD` / `[tool.bandit] skips` с причиной и датой.

`security/suppressions-are-files-with-deadline` — `# nosec` без кода и justification (≥30 символов).

```toml
# pyproject.toml — конфиг bandit в репо (R-SEC-3: suppressions файлом, не разрозненными # nosec)
[tool.bandit]
exclude_dirs = ["tests", ".venv"]
# Каждый skip — с причиной и сроком (R-SEC-SAST-4); ничего «на всякий случай»:
skips = [
    "B101",  # assert_used — отключаем в тестах; justify: pytest-ассерты. до: 2026-12-31
]

[tool.bandit.assert_used]
skips = ["*/test_*.py", "*/conftest.py"]

# ruff подключает bandit-производный набор S (R-SEC-SAST-1):
[tool.ruff.lint]
select = ["E", "F", "S"]      # S = flake8-bandit: SQLi, hardcoded pwd, weak crypto, eval/exec
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]         # assert в тестах допустим
```

```bash
bandit -r src/ -ll -f sarif -o bandit.sarif    # -ll = fail на HIGH/CRITICAL (R-SEC-SAST-3); SARIF в Security tab
```

Точечное подавление в коде — только с кодом правила, обоснованием и сроком (`security/suppressions-are-files-with-deadline`):

```python
subprocess.run(args, shell=False)  # nosec B603  # justify: args — статический список, не из ввода. до: 2026-12-31
```

## 2. CVE в зависимостях (`R-SEC-DEP-*`)

`security/checks-layered-by-feedback-speed` — `pip-audit` (PyPA Advisory DB) обязателен; на merge в main + nightly + release. `security/dependency-updates-automated` —
Renovate/Dependabot для авто-PR (minor/patch авто, major — review). `security/high-severity-breaks-build` — severity: CVSS ≥ 7.0 ломает
сборку; 4.0–6.9 — отчёт + 30 дней; ниже — игнор. `security/suppressions-are-files-with-deadline` — suppressions с обоснованием/сроком; lock-файл
(`uv.lock`/`poetry.lock`) коммитится (воспроизводимость).

`security/suppressions-are-files-with-deadline` — бессрочное подавление CVE (без `until`). `security/dependency-updates-automated` — незапиненные/pre-release зависимости в
проде (`>=`-диапазоны без lock).

## 3. Секреты (`R-SEC-SECRET-*`)

`security/secret-scanning-before-push` — Gitleaks в pre-commit + CI + full history раз в неделю; `.gitleaks.toml` в корне. `security/secret-scanning-before-push` —
pre-commit hook через `pre-commit`-framework, коммитится, ставится одной командой. `security/leaked-secret-rotated-first` — утёк секрет —
rotate в течение часа, затем чистка истории.

`security/no-secret-values-in-config` — секреты в `settings`/yaml — только `${ENV_VAR}` / secret-store; локально `.env` (в `.gitignore`).
`security/no-secret-values-in-config` — закоммиченный `.env` (даже example) — `.env.example` без значений.

PII/секреты не попадают в логи и тела ошибок (cross-ref `auth-patterns/no-pii-in-logs-and-events`, `error-handling/integration-and-technical-mapping`):

```python
# settings/secrets — типобезопасно, значение из env, не в git (R-SEC-SECRET-X1)
class Settings(BaseSettings):
    db_password: SecretStr                                  # SecretStr → repr/log = '**********'
    model_config = SettingsConfigDict(env_prefix="APP_")

# Логи: id'ы — да, PII — нет
logger.info("order created", order_id=order.id, customer_id=order.customer_id)  # OK: ссылки
# logger.info("order", email=req.email, card=req.card_number)   # ❌ PII/PAN в логах (AUTH-16)

# В problem+json detail — фраза + traceId, не сырой str(exc)/PII (R-ERR-MAP-X3)
```

## 4. Container/image (`R-SEC-IMG-*`)

`security/image-scanning-before-push` — Trivy на все образы в CI до push. `security/image-pinned-and-nonroot` — base image `python:3.12-slim` / distroless,
закреплён digest (`@sha256:`), не `:latest`. `security/image-pinned-and-nonroot` — non-root (`USER 1000:1000`). `security/image-pinned-and-nonroot` — health/
readiness probe.

`security/image-pinned-and-nonroot` — контейнер от root. `security/image-pinned-and-nonroot` — `:latest` base image (невоспроизводимо).

```dockerfile
# Dockerfile — multi-stage, non-root, digest-pinned, с HEALTHCHECK
# R-SEC-IMG-2: slim + digest, не :latest (R-SEC-IMG-X2)
FROM python:3.12-slim@sha256:<digest> AS build
WORKDIR /app
COPY pyproject.toml uv.lock ./                 # lock коммитится (R-SEC-DEP-4)
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

FROM python:3.12-slim@sha256:<digest>
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY src/ ./src/
ENV PATH="/app/.venv/bin:$PATH"

USER 1000:1000                                 # R-SEC-IMG-3: non-root (R-SEC-IMG-X1)

# R-SEC-IMG-4: HEALTHCHECK (или k8s liveness/readiness)
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 <image>   # R-SEC-IMG-1: fail на HIGH/CRITICAL до push
```

## 5. Криптография (`R-SEC-CRYPTO-*`)

`security/passwords-hashed-with-kdf` — пароли — `argon2-cffi` (или `bcrypt`), никогда `hashlib.md5`/`sha1`/`sha256` без salt+KDF.
`security/csprng-for-security-values` — рандом для security — модуль **`secrets`** (`secrets.token_*`), не `random` (`random` — только
не-security: jitter/shuffle). `security/authenticated-encryption-only` — симметричное — `cryptography` AES-GCM (`AESGCM`) с рандомным nonce;
не AES-ECB, не CBC без MAC. `security/modern-tls-only` — TLS ≥ 1.2. `security/token-validated-by-library` — JWT-верификация через библиотеку с
проверкой подписи (`auth-patterns/token-validated-by-library`); ручной парсинг без подписи — критично.

`security/no-hardcoded-keys` — hardcoded ключи/nonce в коде — secret-store/KMS, инжект через env.

## 6. Реакция на findings (`R-SEC-FIND-*`)

`security/high-severity-breaks-build` — severity → SLA: CRITICAL — сборка падает, hotfix ≤24ч; HIGH — падает, патч ≤2 нед; MEDIUM — ≤30
дней; LOW — игнор. `security/suppressions-are-files-with-deadline` — suppressions со сроком (`until`); квартальный отчёт «просроченные». `security/code-security-scanner-required` —
SARIF в GitHub Security tab (bandit/Trivy/pip-audit).

`security/every-finding-gets-a-decision` — игнор finding «не уверен» молчанием — либо suppression с обоснованием, либо фикс.

## 7. Чеклист подключения к новому сервису (Python)

1. ruff(`S`)+bandit(+semgrep)+mypy в CI с fail на HIGH/CRITICAL; suppressions со сроком.
2. pip-audit + Trivy на main/release; lock-файл коммитится; нет бессрочных подавлений.
3. Gitleaks pre-commit+CI; секреты только через env/secret-store; нет закоммиченного `.env`.
4. Образ: digest-pinned base, non-root, probe; не `:latest`/root.
5. Крипта: argon2/bcrypt, `secrets`, AES-GCM; нет md5/sha1/ECB/hardcoded ключей.
6. Findings → SLA по severity; SARIF в Security tab.
