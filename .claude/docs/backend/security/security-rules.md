# Security — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/security-style-guide.md` (Error Prone/SpotBugs+FindSecBugs/OWASP DC/Trivy) и
> `python/security-style-guide.md` (bandit/semgrep/pip-audit/Trivy/argon2); открывай нужный точечно.
> Коды: `R-SEC-<GROUP>-<N>` — обязательно, `R-SEC-<GROUP>-X<N>` — антипаттерн (запрещено). **Коды общие для всех
> языков** — меняется набор инструментов; принципы (fail-on-finding, suppressions со сроком, non-root, сильная крипта) одни.
> Узкий: mandatory-набор SAST-инструментов + реакция на findings. Auth-флоу — `auth-patterns`, PII в логах — `observability`.

**MUST:**
- **R-SEC-1.** Сборка падает на security-finding: каждый инструмент в CI с `failOnError: true` для HIGH/CRITICAL. Иначе скан — дашборд, который никто не смотрит.
- **R-SEC-2.** Расслоение по скорости фидбека: Error Prone+NullAway (каждый build), Gitleaks-diff (pre-commit), SpotBugs+FindSecBugs (на PR), Dependency-Check+Trivy (merge в main/nightly/release). SAST по коду — на PR; supply chain — на main/release (CVE не появляются от PR).
- **R-SEC-3.** Все suppressions/baselines — файлы в репо (`spotbugs-exclude.xml`, `dependency-check-suppressions.xml`, `.gitleaks.toml`, `security-baseline.json`), не комментарии в коде; каждое исключение с причиной и сроком.
- **R-SEC-4.** Baseline-механика на release: supply chain сравнивает с `security-baseline.json` (обновляется на merge в main), блокирует только на **новые** findings; старый долг — отдельной задачей.

## 1. SAST по коду
**MUST:**
- **R-SEC-SAST-1.** Error Prone (+ NullAway) обязателен на всех сервисах через `net.ltgt.errorprone` — ловит на этапе компиляции (`EqualsHashCode`, `MissingOverride`, утечки ресурсов).
- **R-SEC-SAST-2.** SAST-сканер байткода/AST обязателен (Java: SpotBugs+FindSecBugs; Python: bandit+semgrep): SQLi, XSS, path traversal, weak crypto, XXE, hardcoded passwords; SARIF для GitHub code scanning.
- **R-SEC-SAST-3.** Severity-ответ: HIGH/CRITICAL SAST-finding (Java: SpotBugs/FindSecBugs/Error Prone; Python: bandit/semgrep) → `failOnError: true`; MEDIUM — отчёт + комментарий ревьюера; LOW — игнор.
- **R-SEC-SAST-4.** Suppressions в `config/spotbugs-exclude.xml` с обязательным `<!-- justify: ... до: YYYY-MM-DD -->`; без даты — не принимается.

**MUST NOT:**
- **R-SEC-SAST-X1.** Подавление SAST-finding на класс/метод без `justification` (≥ 30 символов).

## 2. CVE в зависимостях
**MUST:**
- **R-SEC-DEP-1.** OWASP Dependency-Check обязателен (NIST NVD); на merge в main + nightly + release (не на PR); локально не запускается (нет тёплого NVD-кэша); `NVD_API_KEY` обязателен.
- **R-SEC-DEP-2.** Renovate или Dependabot обязателен — авто-PR на minor/patch, major — manual review.
- **R-SEC-DEP-3.** Severity: CVSS ≥ 7.0 → `failBuildOnCVSS = 7.0` ломает сборку; 4.0–6.9 — отчёт + 30 дней на патч; ниже — игнор.
- **R-SEC-DEP-4.** Suppressions в `dependency-check-suppressions.xml` с обязательным `<notes>` (почему / когда патч / срок).

**MUST NOT:**
- **R-SEC-DEP-X1.** Подавление CVE без `until=` (бессрочное) — запрещено.
- **R-SEC-DEP-X2.** Snapshot-зависимости (`...-SNAPSHOT`) в production-сборке.

## 3. Секреты в коде и истории
**MUST:**
- **R-SEC-SECRET-1.** Gitleaks в pre-commit + CI (pre-commit до push, CI страховочно + full history раз в неделю); `.gitleaks.toml` в корне.
- **R-SEC-SECRET-2.** Pre-commit hook через `husky`/`pre-commit`-framework, коммитится в репо, ставится одной командой (не ручная инструкция в README).
- **R-SEC-SECRET-3.** Утёк секрет — rotate сначала (в течение часа), удаление из истории потом (GitHub уже проиндексировал).

**MUST NOT:**
- **R-SEC-SECRET-X1.** Секреты в `application*.yml` — только `${ENV_VAR}`; локально `.env` (в `.gitignore`), prod — Vault/k8s secrets.
- **R-SEC-SECRET-X2.** Закоммиченный `.env` (даже «example») — используй `.env.example` без значений.

## 4. Container/image-уязвимости
**MUST:**
- **R-SEC-IMG-1.** Trivy обязателен для всех образов (base image, OS-пакеты, библиотеки), в CI после сборки до push.
- **R-SEC-IMG-2.** Base image — `eclipse-temurin:21-jre-alpine` / `distroless/java21:nonroot`, закреплён тегом+digest или digest (`@sha256:`); никогда `:latest`.
- **R-SEC-IMG-3.** Non-root user обязательно (`USER 1000:1000`) — иначе CVE → escape → root → metadata-service.
- **R-SEC-IMG-4.** `HEALTHCHECK` в Dockerfile или liveness/readiness в k8s обязательно.

**MUST NOT:**
- **R-SEC-IMG-X1.** Запуск контейнера от root (`USER root` или отсутствие `USER`).
- **R-SEC-IMG-X2.** `:latest`-тег base image — сборка не воспроизводима.

## 5. Криптография в коде
**MUST:**
- **R-SEC-CRYPTO-1.** Хеширование паролей — сильный KDF (Java: bcrypt factor ≥ 12; Python: argon2/bcrypt); никогда `MD5`/`SHA1`/`SHA256` без salt.
- **R-SEC-CRYPTO-2.** Random для security — только CSPRNG (Java: `SecureRandom`; Python: `secrets`); обычный PRNG — только не-security (jitter, shuffle).
- **R-SEC-CRYPTO-3.** Симметричное шифрование — `AES/GCM/NoPadding` с 12-байтным рандомным IV; не `AES/ECB`, не `AES/CBC` без MAC.
- **R-SEC-CRYPTO-4.** TLS — минимум 1.2 (Spring default); TLS 1.0/1.1 отключаются на reverse-proxy.
- **R-SEC-CRYPTO-5.** JWT verification — через `oauth2ResourceServer().jwt()` (`AUTH-4`); ручной парсинг без проверки подписи — критическая ошибка.

**MUST NOT:**
- **R-SEC-CRYPTO-X1.** Hardcoded ключи/IV в коде — Vault/KMS, инжект через ENV.

## 6. Реакция на findings
**MUST:**
- **R-SEC-FIND-1.** Severity → SLA: CRITICAL — сборка падает, hotfix ≤ 24ч; HIGH — падает, патч ≤ 2 недели; MEDIUM — отчёт, ≤ 30 дней; LOW — игнор.
- **R-SEC-FIND-2.** Suppressions имеют срок (`until=`); без срока — невыполненная задача; квартальный отчёт «просроченные».
- **R-SEC-FIND-3.** GitHub Code Scanning / SARIF — отчёты SAST/Trivy/CVE-сканера в GitHub Security tab (единый дашборд без отдельной инфры).

**MUST NOT:**
- **R-SEC-FIND-X1.** Игнорирование finding «не уверен, эксплуатируется ли» — не эксплуатируется → suppression с обоснованием; молчание = долг.
