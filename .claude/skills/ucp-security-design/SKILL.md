---
name: ucp-security-design
description: Подключить SAST-обвязку к существующему Spring Boot-сервису (Java) по UCP (коды R-SEC-*, BS-SEC-*) — Error Prone, SpotBugs+FindSecBugs, OWASP Dependency-Check, Gitleaks, Trivy, suppression-файлы, CI со SARIF, severity-thresholds.
when_to_use: Триггеры — «подключи security к сервису X», «настрой SAST», «добавь dependency-check», «настрой gitleaks».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Подключение backend/security/SAST-инструментов к сервису

Ты добавляешь к существующему Spring Boot-сервису полный mandatory-набор security-инструментов согласно `backend/security/java/security-style-guide.md` (правила `R-SEC-*`) и `backend/java/spring-bootstrap/spring-bootstrap-rules.md` (правила `BS-SEC-*`). Цель — миграция от «scan вручную раз в квартал» или «вообще ничего» к enforcement в CI.

Не делает: настройку Vault/KMS (это infra), audit-логи admin-операций (`AUTH-15` через `ucp-auth-design`), маскирование PII в логах (`R-OBS-PII-*` через `ucp-observability-design`), threat modeling (это спека-фаза).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/security/security-rules.md` — правила `R-SEC-*`. Главный документ (полный текст с gradle/CI-сниппетами — `backend/security/java/security-style-guide.md`, открывай точечно по разделу).
   - `.claude/docs/backend/java/spring-bootstrap/spring-bootstrap-rules.md` — правила `BS-SEC-*` (enforcement-уровень).
   - `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` — для контекста, какие auth-правила пересекаются.

2. **Идентифицируй сервис.**
   - `git diff` или путь от пользователя.
   - Корень — `build.gradle` / `build.gradle.kts` верхнего уровня.
   - CI — `.github/workflows/*.yml` или `.gitlab-ci.yml`.
   - Dockerfile — `Dockerfile`, `infra/Dockerfile`, `docker/`.

3. **Аудит текущего состояния.** Заполни таблицу — что уже есть, что предстоит:

   | Инструмент | Mandatory код | Текущее состояние | План |
   |---|---|---|---|
   | Error Prone | `R-SEC-SAST-1` | нет / частично / есть | добавить / усилить |
   | SpotBugs + FindSecBugs | `R-SEC-SAST-2` | нет / есть без findsecbugs / полный | добавить findsecbugs / failOnError |
   | OWASP Dependency-Check | `R-SEC-DEP-1` | нет / есть без NVD ключа | добавить ключ |
   | Renovate / Dependabot | `R-SEC-DEP-2` | нет / Dependabot / Renovate | подключить |
   | Gitleaks | `R-SEC-SECRET-1` | нет / только pre-commit | добавить CI |
   | Trivy | `R-SEC-IMG-1` | нет / есть без exit-code | добавить exit-code 1 |
   | Non-root user в Dockerfile | `R-SEC-IMG-3` | нет / есть | добавить USER |

4. **Внеси изменения.** Lombok-defaults обязательны (`JS-6.1`–`JS-6.7`). Не цитируй коды правил в комментариях кода (`JS-7.3`).

   ### 4.1 `build.gradle` — плагины и dependencies

   Добавь блоки (если отсутствуют):

   ```gradle
   plugins {
       id 'net.ltgt.errorprone' version '4.1.0'
       id 'com.github.spotbugs' version '6.0.27'
       id 'org.owasp.dependencycheck' version '11.1.0'
   }

   dependencies {
       errorprone 'com.google.errorprone:error_prone_core:2.36.0'
       errorprone 'com.uber.nullaway:nullaway:0.12.1'
       spotbugsPlugins 'com.h3xstream.findsecbugs:findsecbugs-plugin:1.13.0'
   }

   tasks.withType(JavaCompile).configureEach {
       options.errorprone.error('NullAway')
       options.errorprone.option('NullAway:AnnotatedPackages', '<base-package>')
   }

   spotbugs {
       effort = 'max'
       reportLevel = 'low'
       excludeFilter = file('config/spotbugs-exclude.xml')
       ignoreFailures = false
   }
   tasks.named('spotbugsMain') {
       reports {
           xml.required = true
           sarif.required = true
       }
   }

   dependencyCheck {
       failBuildOnCVSS = 7.0
       formats = ['HTML', 'JSON', 'SARIF']
       suppressionFile = 'config/dependency-check-suppressions.xml'
       nvd {
           apiKey = System.getenv('NVD_API_KEY')
       }
       analyzers {
           nodeAuditEnabled = false
           retiredEnabled = true
       }
   }

   tasks.named('check') {
       dependsOn 'spotbugsMain', 'dependencyCheckAnalyze'
   }
   ```

   `<base-package>` — определи из `package` верхнего java-файла или из `group` в settings.gradle (типично `ru.vikulinva` или `ru.vikulinva`).

   ### 4.2 Конфиг-файлы (создаются пустыми, если нет)

   `config/spotbugs-exclude.xml`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <FindBugsFilter xmlns="https://github.com/spotbugs/filter/3.0.0">
       <!--
         Suppression-file для SpotBugs/FindSecBugs.
         Каждое исключение содержит <!- - justify: ... до: YYYY-MM-DD - -> комментарий (R-SEC-SAST-4).
       -->
   </FindBugsFilter>
   ```

   `config/dependency-check-suppressions.xml`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <suppressions xmlns="https://jeremylong.github.io/DependencyCheck/dependency-suppression.1.3.xsd">
       <!--
         Каждое подавление обязано иметь until="YYYY-MM-DDZ" (R-SEC-DEP-4).
         Без срока — не принимается ревьюером.
       -->
   </suppressions>
   ```

   `.gitleaks.toml` (минимум — extends + extra-rules при необходимости):
   ```toml
   title = "Gitleaks config — <service>"
   [extend]
   useDefault = true

   # Ниже — service-specific allowlist для известных false positives.
   # Каждая запись с комментарием «почему» (R-SEC-3).
   [[allowlist]]
   description = "Test-only fixtures"
   paths = [
     '''.*Test\.java$''',
     '''.*\.fixture\.json$''',
   ]
   ```

   ### 4.3 CI — `.github/workflows/*.yml`

   Добавь параллельный job `security`:

   ```yaml
   security:
     runs-on: ubuntu-latest
     permissions:
       contents: read
       security-events: write   # для SARIF в GitHub Code Scanning
     steps:
       - uses: actions/checkout@v4
         with: { fetch-depth: 0 }   # для gitleaks history scan

       - uses: actions/setup-java@v4
         with: { distribution: 'temurin', java-version: '21' }

       - name: Gradle cache
         uses: actions/cache@v4
         with:
           path: ~/.gradle/caches
           key: gradle-${{ hashFiles('**/*.gradle*') }}

       - name: Gitleaks
         uses: gitleaks/gitleaks-action@v2
         with:
           config-path: .gitleaks.toml

       - name: SpotBugs + FindSecBugs
         run: ./gradlew spotbugsMain
         env: { GRADLE_OPTS: '-Xmx2g' }

       - name: OWASP Dependency-Check
         run: ./gradlew dependencyCheckAnalyze
         env:
           NVD_API_KEY: ${{ secrets.NVD_API_KEY }}

       - name: Upload SARIF — SpotBugs
         if: always()
         uses: github/codeql-action/upload-sarif@v3
         with: { sarif_file: build/reports/spotbugs/main.sarif }

       - name: Upload SARIF — Dependency-Check
         if: always()
         uses: github/codeql-action/upload-sarif@v3
         with: { sarif_file: build/reports/dependency-check-report.sarif }
   ```

   И отдельный job для Docker (после build):

   ```yaml
   trivy:
     needs: docker-build
     runs-on: ubuntu-latest
     steps:
       - uses: aquasecurity/trivy-action@0.28.0
         with:
           image-ref: ${{ env.IMAGE_TAG }}
           severity: HIGH,CRITICAL
           exit-code: 1
           ignore-unfixed: true
           format: sarif
           output: trivy-results.sarif
       - if: always()
         uses: github/codeql-action/upload-sarif@v3
         with: { sarif_file: trivy-results.sarif }
   ```

   ### 4.4 Pre-commit hook (`R-SEC-SECRET-2`)

   Если `.husky/` или `.pre-commit-config.yaml` отсутствуют — создать `.pre-commit-config.yaml`:

   ```yaml
   repos:
     - repo: https://github.com/gitleaks/gitleaks
       rev: v8.21.2
       hooks:
         - id: gitleaks
   ```

   В README сервиса — секция «Setup → `pre-commit install`». Без этого hook не активируется автоматически.

   ### 4.5 Dockerfile (`R-SEC-IMG-2`/`R-SEC-IMG-3`)

   Если base image — `:latest` или без digest, или нет `USER`:

   ```dockerfile
   # было:  FROM openjdk:latest
   FROM eclipse-temurin:21-jre-alpine@sha256:<актуальный-digest>

   WORKDIR /app
   COPY build/libs/app.jar app.jar

   USER 1000:1000
   EXPOSE 8080

   HEALTHCHECK --interval=30s --timeout=3s \
     CMD wget --quiet --spider http://localhost:8080/actuator/health || exit 1

   ENTRYPOINT ["java","-jar","/app/app.jar"]
   ```

   Digest получи: `docker pull eclipse-temurin:21-jre-alpine && docker inspect --format='{{index .RepoDigests 0}}' eclipse-temurin:21-jre-alpine`.

   ### 4.6 Renovate (`R-SEC-DEP-2`)

   Если `renovate.json` отсутствует — создать минимальный:

   ```json
   {
     "$schema": "https://docs.renovatebot.com/renovate-schema.json",
     "extends": ["config:recommended", ":semanticCommits", ":automergeMinor"],
     "schedule": ["before 6am on monday"],
     "vulnerabilityAlerts": { "labels": ["security"], "schedule": ["at any time"] }
   }
   ```

5. **Самопроверка перед выдачей** — пройдись по чеклисту из `backend/security/java/security-style-guide.md` §«Чеклист подключения нового сервиса».

6. **Структура вывода:**
   1. **Audit таблица** (из шага 3).
   2. **План изменений** — какие файлы создаются/правятся, в каком порядке.
   3. **Изменения по файлам** — каждый файл отдельным code-block с пометкой «add» / «replace» / «patch».
   4. **Команды проверки локально:**
      - `./gradlew compileJava spotbugsMain dependencyCheckAnalyze`
      - `gitleaks detect --source=. --config=.gitleaks.toml`
      - `docker build -t <service>:test . && trivy image --severity HIGH,CRITICAL --exit-code 1 <service>:test`
   5. **Что **не** покрывается** (с пояснением, какой скилл это делает): Vault, audit log, PII-маскирование.
   6. **Финальный шаг:** «запусти `ucp-security-review` для верификации».

## Что НЕ делает

- Не настраивает Vault / Kubernetes secrets / KMS.
- Не пишет audit-логи (`ucp-auth-design`).
- Не настраивает маскирование PII в логах (`ucp-observability-design`).
- Не анализирует существующие suppressions на актуальность — это функция `ucp-security-review`.
- Не делает threat modeling — это `ucp-spec-design`.

После работы скилла — обязательно `ucp-security-review` для верификации, что enforcement настроен корректно.

$ARGUMENTS
