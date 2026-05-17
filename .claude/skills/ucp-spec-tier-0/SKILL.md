---
name: ucp-spec-tier-0
description: Сгенерировать Tier 0 (as-is) Use Case спецификацию для существующего сервиса из его кода — без бизнес-брифа, без интервью. На входе только репо (Java-исходники, миграции Liquibase/Flyway, application.yml, OpenAPI, README, интеграционные тесты), на выходе — то же дерево `docs/spec/` из 16 разделов, что у `ucp-spec-design`, но содержимое снимает факт «как сейчас» и помечает отсутствующие данные литералом `not-declared`. Применяется при онбординге существующего сервиса, не построенного по UCP, и как точка отсчёта для последующего рефакторинга в Tier A/B/C.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Skill(superpowers:*)
---

# Use Case спецификация — Tier 0 (as-is реверс из кода)

Ты пишешь **Tier 0 спецификацию** для существующего сервиса. Это снимок «как сейчас»: 16 разделов того же универсального шаблона, что и в `ucp-spec-design`, но содержимое каждой секции — факт, извлечённый из кодовой базы. Никакого бизнес-брифа, никакого интервью с командой; то, чего нет в репо, помечается литералом `not-declared`.

Tier 0 нужен для двух сценариев:
1. **Онбординг.** Новый инженер получает структурированное описание сервиса в одной форме с UCP-спеками, а не россыпь README и Confluence-страниц.
2. **База для миграции.** Документ читается downstream-скиллами (`ucp-ddd-tactical-review`, `ucp-cqrs-review` и т.п.) — `not-declared`-поля прямо подсвечивают, где сервис не следует UCP и куда метить рефакторинг.

Скилл **не классифицирует** существующий код как правильный или неправильный, **не предлагает рефакторинг**, **не пытается восстановить агрегаты с инвариантами там, где модель anemic**. Он фиксирует факт и пишет `not-declared`, когда факт в репо не выражен.

## Зависимости

- **Плагин `superpowers`** — для TodoWrite-планирования при крупных сервисах. Если плагина нет, скилл всё равно отработает.
- **Шаблон `.claude/docs/usecase-spec-template.md`** — обязательный источник правды по структуре 16 разделов, frontmatter, литералу `not-declared` и per-item card schemas. Если файл недоступен — остановись и сообщи.
- Скилл **не использует** `context7` (документация фреймворков не нужна — описываем код, а не лучшие практики) и **не ходит** в живую БД (источник — только репо).

Если зависимость отсутствует — скилл сообщает об этом в начале ответа, не падает молча.

## Инструкции

1. **Прочитай шаблон** из `.claude/docs/usecase-spec-template.md`. Структура 16 разделов, frontmatter и per-item card schemas — оттуда. Не выдумывай свои.

2. **Установи имя сервиса** (`<service>`) из `build.gradle`/`pom.xml` (`artifactId` / `rootProject.name`), README или директории проекта. Если неоднозначно — спроси у пользователя.

3. **Зафиксируй Tier-маркер.** В заголовке спеки и во frontmatter каждого файла указывается `tier: 0`. Не путать с UCP-уровнями (Level 1-4) — это два независимых измерения. Tier 0 = ingest из кода; Levels — про зрелость кода.

4. **Собери источники из репо** (только репо, без выходов наружу):

   | Источник | Что извлекать | Куда кладёт |
   |---|---|---|
   | `README.md`, корневой и модульные | Назначение сервиса, ограничения, ссылки | §1, §16 |
   | `build.gradle*` / `pom.xml` | Spring Boot версия, jOOQ / JPA, Spring Kafka, Flyway/Liquibase, security-стек | §17 (stack), §14 |
   | `application.yml` / `application-*.yml` | DataSource, Kafka brokers, REST-клиенты, security, server config | §14, §16 |
   | Liquibase / Flyway миграции (`src/main/resources/db/**`) | Таблицы, колонки, FK, индексы, CHECK-constraints | §3, §6 |
   | `@Entity` / `@Table` / JPA-annotations | Маппинг таблиц на классы, связи | §3 |
   | `@RestController` / `@RequestMapping` | HTTP entry-points, метод (GET → §9, POST/PUT/PATCH/DELETE → §7) | §7, §9 |
   | OpenAPI / Swagger YAML (если есть) | Контракт API целиком, форматы запросов и ответов | §11, §7, §9 |
   | `@KafkaListener` | Inbound-команды через Kafka | §7 |
   | `KafkaTemplate.send`, `@SendTo` | Publish событий | §8 |
   | `enum`-ы статусов + поля `status` в БД | Жизненный цикл и переходы | §4 |
   | `SecurityConfig`, `@PreAuthorize`, JWT claims | Роли и права | §5 |
   | `@Valid`, `@NotNull`, `@Pattern`, БД-constraints (`CHECK`, `UNIQUE`, `NOT NULL`) | Бизнес-правила и инварианты | §6 |
   | `@ExceptionHandler`, `@ControllerAdvice`, наследники `RuntimeException` | Каталог ошибок | §13 |
   | Интеграционные тесты `*IT.java`, `@SpringBootTest` | Критерии приёмки, scenarios | §10, §15 |
   | `@Transactional` поверх нескольких ресурсов, outbox-таблицы (`*_outbox`, `event_log`) | Saga / process manager | §12 |

5. **Сгенерируй то же дерево `docs/spec/`**, что и `ucp-spec-design`. Раскладка папок, имена файлов, frontmatter-схемы — идентичны (см. шаблон §«Per-item cards»). Это обязательно: downstream-скиллы не должны знать, кто сгенерил спеку.

   ```
   docs/spec/
     00-<service>/<service>.md
     01-<service>-context/01-<service>-context.md
     02-<service>-language/02-<service>-language.md
     03-<service>-model/
       03-<service>-model.md                          — landing (ER + таблицы)
       <Entity>.md                                    — карточка на сущность БД (НЕ на агрегат)
     04-<service>-lifecycle/04-<service>-lifecycle.md
     05-<service>-roles/05-<service>-roles.md
     06-<service>-rules/06-<service>-rules.md
     07-<service>-commands/
       07-<service>-commands.md
       <Command>.md                                   — на каждый POST/PUT/DELETE-endpoint + @KafkaListener
     08-<service>-events/
       08-<service>-events.md
       <Event>.md                                     — на каждый KafkaTemplate.send-целевой топик
     09-<service>-queries/
       09-<service>-queries.md
       <Query>.md                                     — на каждый GET-endpoint
     10-<service>-use-cases/10-<service>-use-cases.md
     11-<service>-ui/11-<service>-ui.md
     12-<service>-sagas/12-<service>-sagas.md
     13-<service>-errors/
       13-<service>-errors.md
       <ERROR_CODE>.md                                — на каждый @ExceptionHandler-кейс
     14-<service>-integrations/
       14-<service>-integrations.md
       <service>-{from|to}-<other>.md
     15-<service>-acceptance/15-<service>-acceptance.md
     16-<service>-nfr/16-<service>-nfr.md
     17-<service>-stack/17-<service>-stack.md
   ```

   **Все 16 разделов создаются всегда.** Даже если в репо нет ни одного `KafkaTemplate.send`, папка `08-<service>-events/` создаётся с landing-файлом, в котором написано «Сервис не публикует доменных событий (KafkaTemplate.send / @SendTo в коде не найдены)» — это явный факт, а не молчаливое опущение.

6. **Заполни разделы по маппингу из шага 4.** Контент каждого раздела:

   1. **Bounded Context.** Из README + списка контроллеров: что сервис делает (1-2 фразы) + границы (что НЕ делает — выводится по отсутствию endpoint-ов). Если README пустой / отсутствует — `not-declared` в `intent` поля frontmatter, тело: «Назначение сервиса в репо не описано; восстановлено из entry-points: <список>».

   2. **Ubiquitous Language.** Таблица из имён таблиц + имён `@Entity` + имён Kafka-топиков. Колонки: «Имя в коде» | «Имя в БД» | «Имя в Kafka» | «Определение». Определение = `not-declared`, если в JavaDoc / README соответствия нет. Это нормальный случай для Tier 0.

   3. **Domain Model.** Список таблиц из миграций. На каждую таблицу — карточка `<Entity>.md` с frontmatter `type: entity` (НЕ `type: aggregate` — агрегаты в Tier 0 не объявляются):
      ```yaml
      ---
      type: entity
      entity: orders
      pk: id
      fields:
        - id: bigint
        - customer_id: bigint (FK → customers)
        - amount: numeric(10,2) CHECK(amount > 0)
        - status: text (enum: PENDING, PAID, CANCELLED)
        - created_at: timestamptz
      fk:
        - customer_id → customers.id
      indexes:
        - idx_orders_status (status, created_at)
      aggregate: not-declared
      invariants: not-declared
      ---
      ```
      Поле `aggregate: not-declared` — явный сигнал, что границы агрегата в коде не выделены.

   4. **Жизненный цикл.** Из enum-ов статусов + поля `status` в таблицах. Если переходы в коде не структурированы (нет state-machine, есть только `if (status == X) status = Y`), таблица переходов восстанавливается из этих `if`-ов с пометкой `(reconstructed-from-code: <ClassName>.java:NN)`. Если статусов нет — landing: «У сущностей сервиса нет полей `status` / enum-статусов в коде».

   5. **Роли и права.** Из `SecurityConfig` + `@PreAuthorize`. Если ничего — `not-declared` в матрице, landing: «`SecurityConfig` использует `permitAll()` / в коде нет `@PreAuthorize` — авторизация делается на уровне gateway / не делается».

   6. **Бизнес-правила и инварианты.** Извлекаются из:
      - `@Valid` + JSR-303 annotations (`@NotNull`, `@Pattern`, `@Min`, `@Size`) — каждый = одно правило, код `BR-V-NNN`.
      - БД-constraints (`CHECK`, `UNIQUE`, `NOT NULL`, FK) — каждый = одно правило, код `BR-DB-NNN`.
      - `if (...) throw new ...Exception(...)` в сервисах — код `BR-CODE-NNN`, ссылка на файл:строку.
      - Утверждения в интеграционных тестах — код `BR-TEST-NNN`.

      Каждое правило — таблица: `Код | Правило | Источник | Тип | Затрагивает | Ошибка`. Если правило очевидно бизнесово (например, `CHECK(amount > 0)`), формулировка пишется по-русски. Если не очевидно (`@Pattern("^[A-Z0-9]+$")` на каком-то поле без контекста) — формулировка = код регулярки, поле определения = `not-declared`.

   7. **Commands.** Каждый POST/PUT/PATCH/DELETE-endpoint и каждый `@KafkaListener` = одна карточка `<Command>.md`. Имя карточки = имя метода контроллера в PascalCase (например, `placeOrder` → `PlaceOrder.md`). Frontmatter:
      ```yaml
      ---
      type: command
      command: PlaceOrder
      actor: not-declared
      intent: "POST /orders (controller: OrderController.placeOrder)"
      idempotent: not-declared
      side-effects:
        - "[[OrderCreated]]"           # если в методе видно KafkaTemplate.send("orders.created", ...)
      br:
        - "[[06-<svc>-rules#BR-V-001]]"  # из @Valid
        - "[[06-<svc>-rules#BR-DB-002]]" # из FK / CHECK
      errors:
        - "[[VALIDATION_FAILED]]"
        - "[[ORDER_CONFLICT]]"
      returns: OrderResponse
      ---
      ```
      Поля `actor` и `idempotent` = `not-declared`, если из `@PreAuthorize` не выводятся / `Idempotency-Key` в контроллере не обрабатывается.

   8. **Domain Events.** Каждый таргет-топик в `KafkaTemplate.send("topic.name", payload)` или `@SendTo("topic.name")` = одна карточка `<Event>.md`. Имя события — PascalCase из имени топика (`orders.created` → `OrderCreated.md`). Если payload — конкретный DTO-класс, поля события берутся из класса. Если payload — `Map<String, Object>` или generic — `payload-version: not-declared`. Если в репо нет `KafkaTemplate.send` — landing файл с пометкой об отсутствии.

   9. **Queries / Read Model.** Каждый GET-endpoint = одна карточка `<Query>.md`. Read Model отдельно описывается только если в коде есть `*View`-сущности или materialized views в миграциях — иначе `read-model: not-declared`.

   10. **Use Cases.** Реконструкция из интеграционных тестов (`@SpringBootTest`, `*IT.java`). Каждый тест-сценарий, проходящий через несколько endpoint-ов или Kafka-листенеров = один use case. Если интеграционных тестов нет — landing: «Use Case-сценарии не восстанавливаются: интеграционных тестов в репо нет».

   11. **UI.** Если есть OpenAPI-файл — ссылка на него, реестр endpoint-ов берётся из openapi.yaml. Если фронта/Figma нет — landing: «UI-сервиса в репо не описан; контракт API — OpenAPI / контроллер-сигнатуры». Поля типа «макеты», «дизайн-система» = `not-declared`.

   12. **Saga / Process Manager.** Ищется по сигнатурам:
       - `@Transactional` поверх нескольких ресурсов (БД + Kafka в одном методе) → saga-candidate.
       - Таблицы вида `*_outbox`, `event_log`, `transaction_log` в миграциях → outbox-pattern.
       - `@Scheduled`-методы, оперирующие over multiple aggregates → process manager.

       Если ни одна сигнатура не найдена — landing: «Sagas / Process Manager в коде не обнаружены; межсервисные процессы либо отсутствуют, либо реализованы на стороне другого сервиса».

   13. **Каталог ошибок.** Каждый `@ExceptionHandler`-кейс или наследник `RuntimeException` (`*Exception.java`) с явным HTTP-кодом = одна карточка `<ERROR_CODE>.md`. Код = UPPER_SNAKE_CASE из имени исключения (`OrderNotFoundException` → `ORDER_NOT_FOUND.md`).

   14. **Интеграции (Context Mapping).** Карта зависимостей из `application.yml`:
       - DataSource → карточка `<service>-to-postgres.md` (тип = БД).
       - Kafka brokers + consumers/producers → карточка на каждое направление.
       - `@FeignClient`, `RestTemplate`, `WebClient`-bean'ы → карточка на каждый внешний REST.
       - S3 / MinIO клиенты → карточка.
       Поле `ddd-pattern` (Conformist / ACL / OHS) **не заполняется** на Tier 0 — пишется `[not-declared]`, потому что классификация контекстных отношений требует домена, которого у нас нет.

   15. **Критерии приёмки.** Извлекаются из существующих интеграционных тестов: каждый тест-метод → одна строка чек-листа (Given/When/Then извлекается из имени метода / `@DisplayName`). Если тестов нет — landing: «Acceptance criteria в репо не зафиксированы (тестов нет)».

   16. **НФТ.** Из `application.yml`:
       - `server.shutdown`, `spring.lifecycle.timeout-per-shutdown-phase` → graceful shutdown.
       - `spring.datasource.hikari.*` → DB pool.
       - `spring.kafka.listener.*` → Kafka NFR.
       - `management.metrics.*`, alert-rules в репо (если есть) → observability.
       Поля «SLA», «p95 latency», «availability» = `not-declared`, если в репо нет alert-rules / SLO-документа.

   17. **Stack.** Сборка из `build.gradle*` / `pom.xml` — Java version, Spring Boot, jOOQ/JPA, Postgres driver, Kafka client, тестовые библиотеки. Это раздел №17 шаблона; на Tier 0 заполняется автоматически и обычно полностью.

7. **Литерал `not-declared` — обязательный.** Где в источнике нет данных для обязательного поля frontmatter (`actor`, `idempotent`, `partition-key`, `retention`, `ddd-pattern`, `sla`, и т.п.) — ставится буквально `not-declared`. Не пустая строка, не `null`, не пропуск ключа, не TODO-комментарий. Это инвариант spec-as-code: downstream-парсеры распознают `not-declared` как явный gap.

   В нарративных разделах (Bounded Context, Use Cases-описание, NFR-комментарии) допустимо пояснение в теле: «Назначение сервиса в репо не описано (README отсутствует); восстановлено из entry-points».

8. **Реконструированные данные помечай источником.** Везде, где факт извлечён из конкретного места в коде, ставь ссылку в виде `(reconstructed-from: <path>:<line>)`. Это даёт читателю возможность проверить.

   ```markdown
   - BR-CODE-007: при отмене заказа количество в `orders.amount` обнуляется (reconstructed-from: OrderService.java:142)
   ```

9. **Код не пиши.** Этот скилл производит только markdown-спеку. Никаких рефакторингов, никаких рекомендаций «как должно быть», никаких `// TODO migrate to UCP` в исходниках сервиса.

10. **Frontmatter сервис-landing.** На `00-<service>/<service>.md` обязательны:
    ```yaml
    ---
    type: service
    owner: not-declared            # если CODEOWNERS / README не указывает
    status: active                 # презумпция, можно переопределить вручную
    criticality: not-declared
    since: not-declared
    repo: <git remote-url из .git/config>
    runbook: not-declared
    tier: 0
    spec-source: code+migrations+openapi
    tags:
      - service
      - tech/java                  # выводится из build.gradle
      - tech/spring-boot           # если в зависимостях
      - tech/postgres              # если в application.yml
    ---
    ```

11. **Бутстрап Obsidian-vault.** Если в `docs/spec/` ещё нет `.obsidian/`:
    ```bash
    cp -R .claude/docs/obsidian-vault-bootstrap/.obsidian docs/spec/.obsidian
    ```
    Если уже есть — не перезаписывай.

12. **Самопроверка перед выдачей:**
    - В каждом файле frontmatter содержит `tier: 0` и (для service-landing) `spec-source: code+migrations+openapi`.
    - Все 16 + 1 (stack) разделов созданы, даже пустые — с явной landing-пометкой об отсутствии содержимого.
    - Все обязательные поля frontmatter заполнены — отсутствующие данные = литерал `not-declared`.
    - Поле `aggregate:` в карточках сущностей §3 = `not-declared`, если границы агрегата в коде не выделены (это норма для Tier 0).
    - Reconstructed-факты несут пометку `(reconstructed-from: file:line)`.
    - Имена per-item карточек уникальны на уровне vault'а: команды PascalCase, события PascalCase, ошибки UPPER_SNAKE.
    - В `docs/spec/` нет консолидированного `<service>.md`.
    - Никаких бизнес-фактов, которых нет в коде: не выдумывай имена акторов, цели команд, типы Context Mapping.

13. **Структура вывода:**
    1. Один абзац **резюме**: имя сервиса, краткая статистика (N таблиц, M команд, K событий, L ошибок, P интеграций), Tier-маркер `tier: 0`, источники.
    2. **Дерево созданных файлов и папок** в `docs/spec/` — точные пути.
    3. **Список явных gap-ов** — список frontmatter-полей со значением `not-declared` сгруппированный по разделу. Это первая точка для архитектора: что в коде не выражено и требует уточнения у команды / решения при миграции в Tier A/B/C.
    4. **Следующие шаги:** упомянуть, что Tier 0 спека читается downstream-скиллами (`ucp-ddd-tactical-review`, `ucp-cqrs-review`, `ucp-shutdown-review` и т.п.) — они выдадут findings вида `Tier-0-blocked: правило X невозможно проверить без объявленного агрегата`. При миграции в Tier A → команда садится с этой спекой и постепенно заменяет `not-declared` на реальные значения, пока не получит Tier A целиком.

$ARGUMENTS
