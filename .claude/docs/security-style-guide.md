# Security Style Guide

Правила безопасности кода и зависимостей для Java/Spring-сервисов по Use Case Pattern. SAST по коду, CVE в зависимостях, секреты в коммитах, контейнерные уязвимости, криптография. Каждое правило имеет код `R-SEC-*` — скилл `ucp-security-review` цитирует их в findings.

Гайд намеренно узкий — он диктует **минимальный mandatory-набор инструментов** и реакцию на findings. Не покрывает auth-флоу (это `auth-patterns-style-guide.md`), не покрывает PII в логах (это `observability-style-guide.md`).

Базовый принцип (`R-SEC-1`): **сборка падает на security-finding**. Любой инструмент из списка ниже включается в CI с `failOnError: true` для уровней `HIGH`/`CRITICAL`. Без этого скан превращается в дашборд, который никто не смотрит.

`R-SEC-2` Скан-фаза в CI идёт **параллельно тестам**, не последовательно. Иначе разработчик ждёт security 5 минут после прохождения тестов и начинает раздражаться. Падение security-стадии → fail PR check.

`R-SEC-3` Все исключения (suppressions, baselines) живут в репо как файлы (`spotbugs-exclude.xml`, `dependency-check-suppressions.xml`, `gitleaks.toml`), не в комментариях кода. Каждое исключение содержит **причину и срок** — иначе через год набор исключений превращается в свалку «когда-то отключили, не помню почему».

---

## 1. SAST по коду — `R-SEC-SAST-*`

`R-SEC-SAST-1` **Error Prone** обязателен на всех Java-сервисах. Подключается через `net.ltgt.errorprone` gradle-plugin. Ловит на этапе компиляции: `EqualsHashCode`, `MissingOverride`, `NullableDereference`, `MutableConstantField`, мисьюз `CompletableFuture`, утечки ресурсов в try-with-resources. Дешёво — те же javac-pass'ы.

```gradle
plugins {
    id 'net.ltgt.errorprone' version '4.1.0'
}
dependencies {
    errorprone 'com.google.errorprone:error_prone_core:2.36.0'
    errorprone 'com.uber.nullaway:nullaway:0.12.1'
}
tasks.withType(JavaCompile).configureEach {
    options.errorprone.error('NullAway')
    options.errorprone.option('NullAway:AnnotatedPackages', 'ru.vikulinva')
}
```

`R-SEC-SAST-2` **SpotBugs + FindSecBugs** обязательны для всего production-кода. SpotBugs ловит общие баги (`NP_NULL_*`, `RC_REF_COMPARISON`, `EI_EXPOSE_REP`), FindSecBugs — security-specific: SQLi (`SQL_INJECTION_JDBC`/`SQL_INJECTION_JPA`), XSS (`XSS_REQUEST_PARAMETER_TO_*`), path traversal (`PATH_TRAVERSAL_IN`), weak crypto (`WEAK_MESSAGE_DIGEST_*`), XXE (`XXE_*`), XML deserialization, hardcoded passwords (`HARD_CODE_PASSWORD`). Один gradle-plugin покрывает оба.

```gradle
plugins {
    id 'com.github.spotbugs' version '6.0.27'
}
dependencies {
    spotbugsPlugins 'com.h3xstream.findsecbugs:findsecbugs-plugin:1.13.0'
}
spotbugs {
    effort = 'max'
    reportLevel = 'low'
    excludeFilter = file('config/spotbugs-exclude.xml')
}
tasks.named('spotbugsMain') {
    reports {
        xml.required = true
        sarif.required = true   // для GitHub code scanning
    }
}
```

`R-SEC-SAST-3` **Severity-ответ**: `HIGH`/`CRITICAL` SpotBugs/FindSecBugs или любой Error Prone error → `failOnError: true` в CI. `MEDIUM` — пишутся в отчёт, ревьюер обязан прокомментировать в PR. `LOW` — игнорим.

`R-SEC-SAST-4` Suppressions выносятся в `config/spotbugs-exclude.xml` с обязательным `<!-- justify: ... до: 2026-MM-DD -->`. Без даты — не принимается. Раз в квартал кто-то проходит по списку и удаляет просроченные.

`R-SEC-SAST-X1` ❌ **`@SuppressFBWarnings` на класс/метод без justification** в коде. Можно только на поле/методе с явным `justification` ≥ 30 символов. Проверяется review-скиллом.

---

## 2. CVE в зависимостях — `R-SEC-DEP-*`

`R-SEC-DEP-1` **OWASP Dependency-Check** обязателен. Сканирует все runtime/test-зависимости против NIST NVD. Запускается на каждом PR и nightly (для подхвата новых CVE без изменений в коде).

```gradle
plugins {
    id 'org.owasp.dependencycheck' version '11.1.0'
}
dependencyCheck {
    failBuildOnCVSS = 7.0      // HIGH+ ломает сборку
    formats = ['HTML', 'JSON', 'SARIF']
    suppressionFile = 'config/dependency-check-suppressions.xml'
    nvd {
        apiKey = System.getenv('NVD_API_KEY')   // обязательно — без ключа NVD-rate-limit убьёт CI
    }
    analyzers {
        nodeAuditEnabled = false   // мы не Node
        retiredEnabled = true
    }
}
```

`R-SEC-DEP-2` **Renovate** или **Dependabot** обязателен на GitHub-репо. Авто-PR на minor/patch обновлений зависимостей. Major — manual review. Без этого зависимости устаревают и CVE накапливаются.

`R-SEC-DEP-3` **Severity-ответ**: CVSS ≥ 7.0 (HIGH/CRITICAL) → `failBuildOnCVSS = 7.0` ломает сборку. CVSS 4.0–6.9 (MEDIUM) — отчёт + срок 30 дней на патч. Ниже — игнорим.

`R-SEC-DEP-4` Suppressions в `config/dependency-check-suppressions.xml` — каждая запись с обязательным `<notes>` (почему false positive / когда патч / срок переоценки). Pattern:

```xml
<suppress until="2026-08-01Z">
    <notes>CVE-2024-XXXX: библиотека не используется в runtime, только в test scope</notes>
    <packageUrl regex="true">^pkg:maven/com\.example/.*$</packageUrl>
    <cve>CVE-2024-XXXX</cve>
</suppress>
```

`R-SEC-DEP-X1` ❌ **Подавление CVE без `until=`** (бессрочное подавление) — запрещено. Пересмотр обязателен.

`R-SEC-DEP-X2` ❌ **Snapshot-зависимости** (`...-SNAPSHOT`) в production-сборке. Невозможно гарантировать неизменяемость артефакта.

---

## 3. Секреты в коде и истории — `R-SEC-SECRET-*`

`R-SEC-SECRET-1` **Gitleaks** в pre-commit hook + CI. Pre-commit ловит до push, CI — страховочно. Сканирует не только diff, но и full history раз в неделю (CVE может появиться в старом коммите задним числом — найти и rotate).

```gradle
// build.gradle — gradle wrapper для gitleaks (если не хочешь установки локально)
task gitleaks(type: Exec) {
    commandLine 'docker', 'run', '--rm', '-v', "${rootDir}:/repo",
        'zricethezav/gitleaks:latest', 'detect', '--source=/repo',
        '--config=/repo/.gitleaks.toml', '--verbose'
}
check.dependsOn gitleaks
```

И `.gitleaks.toml` в корне репо. CI-step:

```yaml
- uses: gitleaks/gitleaks-action@v2
  with:
    config-path: .gitleaks.toml
```

`R-SEC-SECRET-2` **Pre-commit hook** установлен через `husky` или `pre-commit`-framework — не как ручная инструкция в README. Нет hook = разработчик забудет. Hook коммитится в репо и устанавливается одной командой.

`R-SEC-SECRET-3` Если секрет утёк — **rotate сначала, удаляй из истории потом**. Гитхаб уже проиндексировал — `git rebase`/`bfg-repo-cleaner` не помогает. Rotation выполняется в течение часа от обнаружения, удаление из истории — опционально.

`R-SEC-SECRET-X1` ❌ Секреты в `application.yml` / `application-*.yml`. Только через `${ENV_VAR}`-плейсхолдеры. Локально — `.env` (в `.gitignore`), production — Vault/Kubernetes secrets.

`R-SEC-SECRET-X2` ❌ **Закоммиченный `.env` файл**, даже с пометкой «example». Используй `.env.example` без значений.

---

## 4. Container/image-уязвимости — `R-SEC-IMG-*`

`R-SEC-IMG-1` **Trivy** обязателен для всех Docker-образов. Сканирует base image, OS-пакеты, библиотеки. Запускается в CI после сборки образа, до push в registry.

```yaml
- uses: aquasecurity/trivy-action@0.28.0
  with:
    image-ref: ${{ env.IMAGE_TAG }}
    severity: HIGH,CRITICAL
    exit-code: 1
    ignore-unfixed: true   # CVE без патча от upstream — отдельная задача, не блокирует
```

`R-SEC-IMG-2` **Base image**: `eclipse-temurin:21-jre-alpine` или `gcr.io/distroless/java21-debian12:nonroot`. Никогда не `openjdk:latest`, `ubuntu:latest`, `:latest` без digest-pin. Версия закреплена либо тегом + digest, либо просто digest (`@sha256:...`).

`R-SEC-IMG-3` **Non-root user** в Dockerfile обязательно: `USER 1000:1000` в конце. Иначе CVE → escape → root в контейнере → reach к metadata-service.

`R-SEC-IMG-4` **HEALTHCHECK** в Dockerfile или liveness/readiness probes в Kubernetes — обязательно. Trivy с этим не связан, но без healthcheck не отлавливаются runtime-проблемы (зависший JVM с утечкой нативной памяти).

`R-SEC-IMG-X1` ❌ Запуск контейнера от root (`USER root` или отсутствие `USER`).
`R-SEC-IMG-X2` ❌ `:latest`-тег base image. Сборка не воспроизводима.

---

## 5. Криптография в коде — `R-SEC-CRYPTO-*`

`R-SEC-CRYPTO-1` **Хеширование паролей** — только `BCryptPasswordEncoder` (Spring Security default) с factor ≥ 12. Никогда `MD5`/`SHA1`/`SHA256` без salt. SpotBugs/FindSecBugs ловят `WEAK_MESSAGE_DIGEST_*` — настройка `R-SEC-SAST-3` это enforce-ит.

`R-SEC-CRYPTO-2` **Random для security-целей** — только `java.security.SecureRandom`. `java.util.Random` использовать только для тестов и не-security кода (jitter в retry, shuffle).

`R-SEC-CRYPTO-3` **Симметричное шифрование** — `AES-GCM` (`AES/GCM/NoPadding`) с 12-байтным IV (рандомным на каждый encrypt). Не `AES/ECB`, не `AES/CBC` без MAC.

`R-SEC-CRYPTO-4` **TLS** — минимум TLS 1.2 на стороне клиента и сервера (Spring Boot default). TLS 1.0/1.1 явно отключаются на уровне reverse-proxy (Nginx/Envoy) — Java-код это не проверяет.

`R-SEC-CRYPTO-5` **JWT verification** — через `oauth2ResourceServer().jwt()` (см. `AUTH-4`). Вручную парсить JWT (`Jwts.parser()` без проверки подписи) — критическая ошибка. SpotBugs ловит часть случаев, остальное — review-скиллом.

`R-SEC-CRYPTO-X1` ❌ Hardcoded ключи/IV в коде. Хранятся в Vault/KMS, инжектятся через ENV.

---

## 6. Реакция на findings — `R-SEC-FIND-*`

`R-SEC-FIND-1` **Severity → SLA**:

| Severity | Где | SLA на исправление |
|---|---|---|
| `CRITICAL` | любой инструмент | сборка падает, hotfix в течение 24 часов |
| `HIGH` | SpotBugs/FindSecBugs/Trivy/DepCheck | сборка падает, патч в текущем спринте (≤ 2 недели) |
| `MEDIUM` | SpotBugs/FindSecBugs/Trivy | отчёт, патч ≤ 30 дней |
| `LOW` | любой | игнорим, не отображаем в дашборде |

`R-SEC-FIND-2` **Suppressions** имеют срок (`until=...`). Без срока — finding не считается suppressed, считается невыполненной задачей. Раз в квартал автоматический отчёт «просроченные suppressions».

`R-SEC-FIND-3` **GitHub Code Scanning / SARIF** — отчёты SpotBugs, Trivy, DepCheck публикуются в GitHub Security tab через SARIF. Это даёт единый dashboard через интерфейс GitHub без отдельной инфры.

`R-SEC-FIND-X1` ❌ Игнорирование security-финдинга «потому что не уверен, эксплуатируется ли это». Если не эксплуатируется — добавляй suppression с обоснованием. Молчание = долг.

---

## 7. Что **не** покрывает этот гайд

- **Auth-флоу** (JWT validation, RBAC, ABAC, mTLS) — см. [`auth-patterns-style-guide.md`](auth-patterns-style-guide.md). Здесь только enforcement-уровень: SpotBugs/FindSecBugs ловят неправильное использование Spring Security API.
- **PII в логах / маскирование** — см. [`observability-style-guide.md`](observability-style-guide.md), правила `R-OBS-PII-*`.
- **Secrets management** (Vault, sealed-secrets, KMS-rotation) — это infra-тема, не code-тема.
- **DAST / pentest** — наш inhouse-список ограничен SAST-инструментами. DAST (ZAP, Burp) — отдельная инициатива безопасности.
- **Threat modeling** — STRIDE/LINDDUN не автоматизируется, делается на спека-фазе (`ucp-spec-design`).

---

## Чеклист подключения нового сервиса

- [ ] `net.ltgt.errorprone` plugin в `build.gradle`, `failOnError: true` на errors
- [ ] `com.github.spotbugs` + `findsecbugs-plugin` в `build.gradle`, `effort: max`
- [ ] `org.owasp.dependencycheck` plugin, `failBuildOnCVSS = 7.0`
- [ ] `NVD_API_KEY` в CI secrets
- [ ] `.gitleaks.toml` в корне, gitleaks step в CI + pre-commit hook
- [ ] Trivy step в CI после `docker build`, `severity: HIGH,CRITICAL exit-code: 1`
- [ ] Dockerfile: non-root user, base image с digest-pin
- [ ] Renovate/Dependabot config
- [ ] `config/spotbugs-exclude.xml` и `config/dependency-check-suppressions.xml` существуют (могут быть пустыми)
- [ ] CI публикует SARIF в GitHub Code Scanning
