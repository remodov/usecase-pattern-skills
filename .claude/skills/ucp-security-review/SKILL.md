---
name: ucp-security-review
description: Ревью Java/Spring-сервиса на соответствие security-style-guide — SAST-инструменты подключены и enforce-ятся в CI (Error Prone, SpotBugs+FindSecBugs, OWASP Dependency-Check, Gitleaks, Trivy), suppressions имеют срок и обоснование, severity-thresholds правильные, Dockerfile non-root + digest-pinned, секреты не в коде, криптография без MD5/SHA1/AES-ECB. Опирается на коды R-SEC-* и BS-SEC-*. Вызывается на ревью build.gradle, .github/workflows/*, Dockerfile, application.yml, suppression-файлов, любого Java-кода с криптографией.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью security/SAST-настройки сервиса

Ты ревьюишь Java/Spring-сервис на соответствие `security-style-guide.md` (`R-SEC-*`) и enforcement-уровню `spring-bootstrap-style-guide.md` (`BS-SEC-*`). Главные точки контроля: подключение всех mandatory-инструментов, severity-thresholds, suppressions с обоснованием и сроком, Dockerfile-гигиена, криптография в коде.

## Зависимости

- **`.claude/docs/security-style-guide.md`** — индекс всех правил (полный текст — соответствующий `*-style-guide.md`). Каждое нарушение цитируется кодом из подгрупп: `R-SEC-SAST-*` (SpotBugs/FindSecBugs/Error Prone), `R-SEC-DEP-*` (CVE в зависимостях), `R-SEC-SECRET-*` (секреты), `R-SEC-IMG-*` (контейнеры), `R-SEC-CRYPTO-*` (криптография), `R-SEC-FIND-*` (реакция на findings).
- **`.claude/docs/spring-bootstrap-style-guide.md`** — `BS-SEC-*` для enforcement (наличие плагинов в build.gradle, CI-степы).
- Парные документы: `auth-patterns-style-guide.md` (для контекста авторизации), `observability-rules.md` (PII в логах — отдельный гайд, не дублируем).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/security-style-guide.md` и `BS-SEC-*` секцию из `spring-bootstrap-style-guide.md`. Цитируй конкретные коды (`R-SEC-DEP-X1`, `BS-SEC-3`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе скоп по умолчанию:
   - `build.gradle` / `build.gradle.kts` / `settings.gradle*` — наличие плагинов и dependencies (`R-SEC-SAST-1/2`, `R-SEC-DEP-1`).
   - `.github/workflows/*.yml` или `.gitlab-ci.yml` — security-job, Trivy-job, fail-on-error (`R-SEC-1`/`R-SEC-2`).
   - `Dockerfile`, `infra/Dockerfile`, `docker/Dockerfile` — non-root, digest-pin, healthcheck (`R-SEC-IMG-*`).
   - `config/spotbugs-exclude.xml`, `config/dependency-check-suppressions.xml` — наличие, обоснования с `until=` (`R-SEC-SAST-4`, `R-SEC-DEP-4`).
   - `.gitleaks.toml`, `.pre-commit-config.yaml`, `.husky/` — gitleaks setup (`R-SEC-SECRET-*`).
   - `application*.yml` — отсутствие plain-секретов (`R-SEC-SECRET-X1`).
   - Любые `.java` файлы с импортами `MessageDigest`, `Cipher`, `SecureRandom`, `Random`, `Base64`, `BCrypt`, `KeyStore` — крипто-проверка (`R-SEC-CRYPTO-*`).
   - `git diff` на недавно изменённые файлы из перечисленных категорий.

3. **Прогон по подгруппам кодов.**

   ### `R-SEC-SAST-*` — SAST по коду
   - `build.gradle` содержит `net.ltgt.errorprone` plugin? `error_prone_core` в `errorprone` configuration? — `R-SEC-SAST-1`.
   - `build.gradle` содержит `com.github.spotbugs` plugin + `findsecbugs-plugin` в `spotbugsPlugins`? — `R-SEC-SAST-2`.
   - `spotbugs { effort = 'max', reportLevel = 'low', ignoreFailures = false }`? — `R-SEC-SAST-3`.
   - В CI `./gradlew spotbugsMain` запускается и failOnError? — `R-SEC-SAST-3`.
   - В `config/spotbugs-exclude.xml` каждое исключение содержит `<!-- justify: ... до: YYYY-MM-DD -->`? Без даты — нарушение `R-SEC-SAST-4`.
   - Поиск в Java-коде: `@SuppressFBWarnings(...)` без `justification` параметра — `R-SEC-SAST-X1`.

   ### `R-SEC-DEP-*` — CVE в зависимостях
   - `org.owasp.dependencycheck` plugin подключён? — `R-SEC-DEP-1`.
   - `failBuildOnCVSS = 7.0` (или ниже)? — `R-SEC-DEP-3`.
   - `nvd { apiKey = System.getenv('NVD_API_KEY') }`? Без ключа — rate-limit убьёт CI — `R-SEC-DEP-1`.
   - В CI `NVD_API_KEY` прокинут из secrets? — `R-SEC-DEP-1`.
   - `renovate.json` или `.github/dependabot.yml` существует? — `R-SEC-DEP-2`.
   - В `config/dependency-check-suppressions.xml` каждый `<suppress>` имеет `until="..."`? Без `until=` — нарушение `R-SEC-DEP-X1`.
   - В `<notes>` каждого suppression — реальное обоснование (не «false positive», а почему именно), длиной ≥ 30 символов? — `R-SEC-DEP-4`.
   - `git grep -E "[a-zA-Z0-9.-]+:[a-zA-Z0-9.-]+:[0-9]+\.[0-9]+\.[0-9]+-SNAPSHOT"` находит SNAPSHOT в зависимостях? — `R-SEC-DEP-X2`.

   ### `R-SEC-SECRET-*` — секреты
   - `.gitleaks.toml` существует? — `R-SEC-SECRET-1`.
   - В CI gitleaks-step с `fetch-depth: 0` (для history scan)? — `R-SEC-SECRET-1`.
   - `.pre-commit-config.yaml` или `.husky/pre-commit` с gitleaks? Если только в README — `R-SEC-SECRET-2` нарушено.
   - `git ls-files | xargs grep -lE "(api_key|secret|password)\s*[:=]"` в `application*.yml` находит plain-значения (не `${...}`)? — `R-SEC-SECRET-X1`.
   - `git ls-files | grep "\.env$"` находит `.env` файлы (не `.env.example`)? — `R-SEC-SECRET-X2`.

   ### `R-SEC-IMG-*` — контейнеры
   - В CI Trivy-step с `severity: HIGH,CRITICAL` и `exit-code: 1`? — `R-SEC-IMG-1`.
   - В `Dockerfile`: base image с digest (`@sha256:...`) или хотя бы с phaseable-tag (не `:latest`)? — `R-SEC-IMG-2`/`R-SEC-IMG-X2`.
   - Base image из allowlist: `eclipse-temurin:*`, `gcr.io/distroless/*`, `azul/zulu-openjdk:*`? — `R-SEC-IMG-2`.
   - `USER 1000:1000` (или другой не-root UID) в Dockerfile? Если нет / `USER root` — `R-SEC-IMG-X1`/`R-SEC-IMG-3`.
   - `HEALTHCHECK` или liveness/readiness в k8s-манифестах рядом? — `R-SEC-IMG-4`.

   ### `R-SEC-CRYPTO-*` — криптография в коде
   Поиск патернов:
   - `MessageDigest.getInstance("MD5")` или `"SHA-1"` или `"SHA1"` — `R-SEC-CRYPTO-1` (FindSecBugs тоже ловит, но проверь в коде явно).
   - `new Random()` в коде, который не тест и не для jitter — `R-SEC-CRYPTO-2`. Должен быть `SecureRandom`.
   - `Cipher.getInstance("AES")` без mode (default — ECB!), `Cipher.getInstance("AES/ECB/...")`, `Cipher.getInstance("AES/CBC/...")` без MAC — `R-SEC-CRYPTO-3`.
   - `Jwts.parser().setSigningKey(...).parse(...)` без явной проверки подписи — `R-SEC-CRYPTO-5`.
   - Hardcoded `byte[] key = {0x01, ...}` или `String SECRET = "..."` рядом с `Cipher` — `R-SEC-CRYPTO-X1`.
   - Хеширование пароля через что угодно кроме `BCryptPasswordEncoder` (или `Argon2PasswordEncoder` / `Pbkdf2PasswordEncoder`) — `R-SEC-CRYPTO-1`.

   ### `R-SEC-FIND-*` — реакция на findings
   - Suppressions с истёкшим `until=` — отдельная заметка для каждого.
   - В CI workflow `if: always()` на upload SARIF (иначе падение early-step не публикует отчёт) — `R-SEC-FIND-3`.

   ### `BS-SEC-*` (enforcement-уровень из bootstrap-guide)
   - Все mandatory-инструменты подключены — отсутствие любого = `BS-SEC-N` критическое (см. секцию в spring-bootstrap-style-guide).
   - `./gradlew check` запускает spotbugs + dependency-check как dependsOn — `BS-SEC-2`.

4. **При ревью кода ищи паттерны-нарушения:**
   - В `build.gradle`: `ignoreFailures = true` для spotbugs — превращает security в дашборд (`R-SEC-1`).
   - В `dependencyCheck`: `failBuildOnCVSS = 11` или `failBuildOnCVSS = 0` (фейк-thresholds).
   - В CI: security-job с `continue-on-error: true` — нарушение `R-SEC-1`.
   - `suppressionFile` указан, но файла нет — silent failure при первом findings (suppression-парсер падает, инструмент пропускает).
   - `until=` в формате без timezone (`until="2026-08-01"` вместо `until="2026-08-01Z"`) — может работать локально и сломаться в CI.
   - В Dockerfile `:latest` или просто tag без digest на images, которые регулярно обновляются upstream.
   - В `application.yml` найдено `password: <значение>` или `apiKey: <значение>` без `${...}` — критика.

5. **Cross-check с auth-patterns:**
   - Если `R-SEC-CRYPTO-5` (manual JWT parsing) обнаружен — также сошлись на `AUTH-4` («только oauth2ResourceServer().jwt()») для подкрепления.
   - PII в логах НЕ ревьюим здесь (это `R-OBS-PII-*` через `ucp-observability-review`) — но если видишь массовые findings FindSecBugs `INFORMATION_EXPOSURE_THROUGH_AN_ERROR_MESSAGE`, упомяни в финальной заметке.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-SEC-DEP-X1`, `R-SEC-IMG-X1`).

7. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — выключенный enforcement или утёкший секрет:
     - `R-SEC-1` (failOnError выключен в любом инструменте) — превращает security в дашборд
     - `R-SEC-DEP-1` (нет dependency-check вообще) — CVE копятся неучтёнными
     - `R-SEC-SECRET-X1` (plain-секрет в `application.yml`) — утечка ждёт `git push`
     - `R-SEC-SECRET-X2` (.env закоммичен)
     - `R-SEC-IMG-X1` (root в контейнере) — escape-priviledge
     - `R-SEC-CRYPTO-X1` (hardcoded key)
     - `R-SEC-CRYPTO-1` (MD5/SHA1 для пароля)
     - `R-SEC-CRYPTO-3` (AES-ECB)
   - **Предупреждение** — обход правил без явного риска:
     - `R-SEC-SAST-X1` (`@SuppressFBWarnings` без `justification`)
     - `R-SEC-DEP-X1` (suppression без `until=`)
     - `R-SEC-DEP-X2` (SNAPSHOT в production-зависимостях)
     - `R-SEC-IMG-X2` (`:latest`-тег)
     - истёкший `until=` в suppressions
   - **Замечание** — стилистика и недокрытие:
     - отсутствие SARIF upload (`R-SEC-FIND-3`)
     - отсутствие healthcheck в Dockerfile (`R-SEC-IMG-4`)
     - отсутствие Renovate/Dependabot (`R-SEC-DEP-2`)

## Что не входит

- Аутентификация/авторизация (JWT validation, RBAC, ABAC, mTLS) — `ucp-auth-review`.
- PII в логах / маскирование — `ucp-observability-review` (правила `R-OBS-PII-*`).
- Vault / Kubernetes secrets / KMS — infra, не code-ревью.
- DAST (ZAP, Burp) — отдельная инициатива безопасности, не покрывается этим скиллом.
- Threat modeling (STRIDE/LINDDUN) — спека-фаза (`ucp-spec-review`).
- jOOQ / SQL — частично покрыто `ucp-jooq-review` (SQL injection через jOOQ невозможен) и `ucp-pg-runtime-review`.

$ARGUMENTS
