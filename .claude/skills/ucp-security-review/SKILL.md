---
name: ucp-security-review
description: Ревью Java/Spring-сервиса по требованиям `security/*` — SAST в CI (Error Prone, SpotBugs+FindSecBugs, OWASP Dependency-Check, Gitleaks, Trivy), suppressions со сроком, Dockerfile non-root, криптография без MD5/SHA1/AES-ECB.
when_to_use: Ревью build.gradle, CI-workflows, Dockerfile, application.yml, suppression-файлов, Java-кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью backend/security/SAST-настройки сервиса

Ты ревьюишь Java/Spring-сервис на соответствие `backend/security/spec.md` (`R-SEC-*`) и enforcement-уровню `backend/java/spring-bootstrap/spec.md` (`BS-SEC-*`). Главные точки контроля: подключение всех mandatory-инструментов, severity-thresholds, suppressions с обоснованием и сроком, Dockerfile-гигиена, криптография в коде.

## Зависимости

- **`.claude/docs/backend/security/spec.md`** — индекс всех правил (полный текст — `references/<lang>/implementation.md`). Каждое нарушение цитируется кодом из подгрупп: `R-SEC-SAST-*` (SpotBugs/FindSecBugs/Error Prone), `R-SEC-DEP-*` (CVE в зависимостях), `R-SEC-SECRET-*` (секреты), `R-SEC-IMG-*` (контейнеры), `R-SEC-CRYPTO-*` (криптография), `R-SEC-FIND-*` (реакция на findings).
- **`.claude/docs/backend/java/spring-bootstrap/spec.md`** — `BS-SEC-*` для enforcement (наличие плагинов в build.gradle, CI-степы).
- Парные документы: `backend/auth-patterns/spec.md` (для контекста авторизации), `backend/observability/spec.md` (PII в логах — отдельный гайд, не дублируем).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/security/spec.md` и `BS-SEC-*` секцию из `backend/java/spring-bootstrap/spec.md`. Цитируй конкретные коды (`security/suppressions-are-files-with-deadline`, `spring-bootstrap/thresholds-are-not-weakened`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - `build.gradle` / `build.gradle.kts` / `settings.gradle*` — наличие плагинов и dependencies (`R-SEC-SAST-1/2`, `security/checks-layered-by-feedback-speed`).
   - `.github/workflows/*.yml` или `.gitlab-ci.yml` — security-job, Trivy-job, fail-on-error (`security/high-severity-breaks-build`/`security/checks-layered-by-feedback-speed`).
   - `Dockerfile`, `infra/Dockerfile`, `docker/Dockerfile` — non-root, digest-pin, healthcheck (`R-SEC-IMG-*`).
   - `config/spotbugs-exclude.xml`, `config/dependency-check-suppressions.xml` — наличие, обоснования с `until=` (`security/suppressions-are-files-with-deadline`, `security/suppressions-are-files-with-deadline`).
   - `.gitleaks.toml`, `.pre-commit-config.yaml`, `.husky/` — gitleaks setup (`R-SEC-SECRET-*`).
   - `application*.yml` — отсутствие plain-секретов (`security/no-secret-values-in-config`).
   - Любые `.java` файлы с импортами `MessageDigest`, `Cipher`, `SecureRandom`, `Random`, `Base64`, `BCrypt`, `KeyStore` — крипто-проверка (`R-SEC-CRYPTO-*`).
   - `git diff` на недавно изменённые файлы из перечисленных категорий.

3. **Прогон по подгруппам кодов.**

   ### `R-SEC-SAST-*` — SAST по коду
   - `build.gradle` содержит `net.ltgt.errorprone` plugin? `error_prone_core` в `errorprone` configuration? — `security/compile-time-analysis-enabled`.
   - `build.gradle` содержит `com.github.spotbugs` plugin + `findsecbugs-plugin` в `spotbugsPlugins`? — `security/code-security-scanner-required`.
   - `spotbugs { effort = 'max', reportLevel = 'low', ignoreFailures = false }`? — `security/high-severity-breaks-build`.
   - В CI `./gradlew spotbugsMain` запускается и failOnError? — `security/high-severity-breaks-build`.
   - В `config/spotbugs-exclude.xml` каждое исключение содержит `<!-- justify: ... до: YYYY-MM-DD -->`? Без даты — нарушение `security/suppressions-are-files-with-deadline`.
   - Поиск в Java-коде: `@SuppressFBWarnings(...)` без `justification` параметра — `security/suppressions-are-files-with-deadline`.

   ### `R-SEC-DEP-*` — CVE в зависимостях
   - `org.owasp.dependencycheck` plugin подключён? — `security/checks-layered-by-feedback-speed`.
   - `failBuildOnCVSS = 7.0` (или ниже)? — `security/high-severity-breaks-build`.
   - `nvd { apiKey = System.getenv('NVD_API_KEY') }`? Без ключа — rate-limit убьёт CI — `security/checks-layered-by-feedback-speed`.
   - В CI `NVD_API_KEY` прокинут из secrets? — `security/checks-layered-by-feedback-speed`.
   - `renovate.json` или `.github/dependabot.yml` существует? — `security/dependency-updates-automated`.
   - В `config/dependency-check-suppressions.xml` каждый `<suppress>` имеет `until="..."`? Без `until=` — нарушение `security/suppressions-are-files-with-deadline`.
   - В `<notes>` каждого suppression — реальное обоснование (не «false positive», а почему именно), длиной ≥ 30 символов? — `security/suppressions-are-files-with-deadline`.
   - `git grep -E "[a-zA-Z0-9.-]+:[a-zA-Z0-9.-]+:[0-9]+\.[0-9]+\.[0-9]+-SNAPSHOT"` находит SNAPSHOT в зависимостях? — `security/dependency-updates-automated`.

   ### `R-SEC-SECRET-*` — секреты
   - `.gitleaks.toml` существует? — `security/secret-scanning-before-push`.
   - В CI gitleaks-step с `fetch-depth: 0` (для history scan)? — `security/secret-scanning-before-push`.
   - `.pre-commit-config.yaml` или `.husky/pre-commit` с gitleaks? Если только в README — `security/secret-scanning-before-push` нарушено.
   - `git ls-files | xargs grep -lE "(api_key|secret|password)\s*[:=]"` в `application*.yml` находит plain-значения (не `${...}`)? — `security/no-secret-values-in-config`.
   - `git ls-files | grep "\.env$"` находит `.env` файлы (не `.env.example`)? — `security/no-secret-values-in-config`.

   ### `R-SEC-IMG-*` — контейнеры
   - В CI Trivy-step с `severity: HIGH,CRITICAL` и `exit-code: 1`? — `security/image-scanning-before-push`.
   - В `Dockerfile`: base image с digest (`@sha256:...`) или хотя бы с phaseable-tag (не `:latest`)? — `security/image-pinned-and-nonroot`/`security/image-pinned-and-nonroot`.
   - Base image из allowlist: `eclipse-temurin:*`, `gcr.io/distroless/*`, `azul/zulu-openjdk:*`? — `security/image-pinned-and-nonroot`.
   - `USER 1000:1000` (или другой не-root UID) в Dockerfile? Если нет / `USER root` — `security/image-pinned-and-nonroot`/`security/image-pinned-and-nonroot`.
   - `HEALTHCHECK` или liveness/readiness в k8s-манифестах рядом? — `security/image-pinned-and-nonroot`.

   ### `R-SEC-CRYPTO-*` — криптография в коде
   Поиск патернов:
   - `MessageDigest.getInstance("MD5")` или `"SHA-1"` или `"SHA1"` — `security/passwords-hashed-with-kdf` (FindSecBugs тоже ловит, но проверь в коде явно).
   - `new Random()` в коде, который не тест и не для jitter — `security/csprng-for-security-values`. Должен быть `SecureRandom`.
   - `Cipher.getInstance("AES")` без mode (default — ECB!), `Cipher.getInstance("AES/ECB/...")`, `Cipher.getInstance("AES/CBC/...")` без MAC — `security/authenticated-encryption-only`.
   - `Jwts.parser().setSigningKey(...).parse(...)` без явной проверки подписи — `security/token-validated-by-library`.
   - Hardcoded `byte[] key = {0x01, ...}` или `String SECRET = "..."` рядом с `Cipher` — `security/no-hardcoded-keys`.
   - Хеширование пароля через что угодно кроме `BCryptPasswordEncoder` (или `Argon2PasswordEncoder` / `Pbkdf2PasswordEncoder`) — `security/passwords-hashed-with-kdf`.

   ### `R-SEC-FIND-*` — реакция на findings
   - Suppressions с истёкшим `until=` — отдельная заметка для каждого.
   - В CI workflow `if: always()` на upload SARIF (иначе падение early-step не публикует отчёт) — `security/code-security-scanner-required`.

   ### `BS-SEC-*` (enforcement-уровень из bootstrap-guide)
   - Все mandatory-инструменты подключены — отсутствие любого = `BS-SEC-N` критическое (см. секцию в spring-bootstrap-rules).
   - `./gradlew check` запускает spotbugs + dependency-check как dependsOn — `spring-bootstrap/security-checks-split-by-task`.

4. **При ревью кода ищи паттерны-нарушения:**
   - В `build.gradle`: `ignoreFailures = true` для spotbugs — превращает security в дашборд (`security/high-severity-breaks-build`).
   - В `dependencyCheck`: `failBuildOnCVSS = 11` или `failBuildOnCVSS = 0` (фейк-thresholds).
   - В CI: security-job с `continue-on-error: true` — нарушение `security/high-severity-breaks-build`.
   - `suppressionFile` указан, но файла нет — silent failure при первом findings (suppression-парсер падает, инструмент пропускает).
   - `until=` в формате без timezone (`until="2026-08-01"` вместо `until="2026-08-01Z"`) — может работать локально и сломаться в CI.
   - В Dockerfile `:latest` или просто tag без digest на images, которые регулярно обновляются upstream.
   - В `application.yml` найдено `password: <значение>` или `apiKey: <значение>` без `${...}` — критика.

5. **Cross-check с auth-patterns:**
   - Если `security/token-validated-by-library` (manual JWT parsing) обнаружен — также сошлись на `auth-patterns/token-validated-by-library` («только oauth2ResourceServer().jwt()») для подкрепления.
   - PII в логах НЕ ревьюим здесь (это `R-OBS-PII-*` через `ucp-observability-review`) — но если видишь массовые findings FindSecBugs `INFORMATION_EXPOSURE_THROUGH_AN_ERROR_MESSAGE`, упомяни в финальной заметке.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`security/suppressions-are-files-with-deadline`, `security/image-pinned-and-nonroot`).

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — выключенный enforcement или утёкший секрет:
     - `security/high-severity-breaks-build` (failOnError выключен в любом инструменте) — превращает security в дашборд
     - `security/checks-layered-by-feedback-speed` (нет dependency-check вообще) — CVE копятся неучтёнными
     - `security/no-secret-values-in-config` (plain-секрет в `application.yml`) — утечка ждёт `git push`
     - `security/no-secret-values-in-config` (.env закоммичен)
     - `security/image-pinned-and-nonroot` (root в контейнере) — escape-priviledge
     - `security/no-hardcoded-keys` (hardcoded key)
     - `security/passwords-hashed-with-kdf` (MD5/SHA1 для пароля)
     - `security/authenticated-encryption-only` (AES-ECB)
   - **Предупреждение** — обход правил без явного риска:
     - `security/suppressions-are-files-with-deadline` (`@SuppressFBWarnings` без `justification`)
     - `security/suppressions-are-files-with-deadline` (suppression без `until=`)
     - `security/dependency-updates-automated` (SNAPSHOT в production-зависимостях)
     - `security/image-pinned-and-nonroot` (`:latest`-тег)
     - истёкший `until=` в suppressions
   - **Замечание** — стилистика и недокрытие:
     - отсутствие SARIF upload (`security/code-security-scanner-required`)
     - отсутствие healthcheck в Dockerfile (`security/image-pinned-and-nonroot`)
     - отсутствие Renovate/Dependabot (`security/dependency-updates-automated`)

## Что не входит

- Аутентификация/авторизация (JWT validation, RBAC, ABAC, mTLS) — `ucp-auth-review`.
- PII в логах / маскирование — `ucp-observability-review` (правила `R-OBS-PII-*`).
- Vault / Kubernetes secrets / KMS — infra, не code-ревью.
- DAST (ZAP, Burp) — отдельная инициатива безопасности, не покрывается этим скиллом.
- Threat modeling (STRIDE/LINDDUN) — спека-фаза (`ucp-spec-review`).
- jOOQ / SQL — частично покрыто `ucp-jooq-review` (SQL injection через jOOQ невозможен) и `ucp-pg-runtime-review`.

$ARGUMENTS
