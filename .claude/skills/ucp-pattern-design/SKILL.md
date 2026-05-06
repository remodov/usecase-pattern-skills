---
name: ucp-pattern-design
description: Спроектировать или зашаблонить новую бизнес-операцию как UseCase + UseCaseHandler с библиотекой usecase-pattern, по командному Use Case Pattern Style Guide. Применяется при добавлении нового эндпоинта, команды или запроса в Spring Boot-сервис.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Use Case Pattern — проектирование

Ты проектируешь или генерируешь шаблон новой бизнес-операции: одну или несколько пар `UseCase` + `UseCaseHandler` (и путь контроллера, который их диспатчит) с использованием библиотеки `usecase-pattern`.

## Инструкции

1. **Прочитай style guide** из `.claude/docs/usecase-pattern-style-guide.md` и считай каждое правило `R-*` обязательным. На Уровне 3+ дополнительно прочитай `.claude/docs/ddd-tactical-style-guide.md`.

2. **Подтверди наличие библиотеки.** Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:usecase-pattern-starter`. Если нет — попроси пользователя добавить (и предложи сниппет зависимости) — не выдумывай локальные копии `UseCase` / `UseCaseHandler` / `UseCaseDispatcher`.

3. **Определи уровень внедрения** проекта (style guide §2):
   - Hexagonal (`core/` + `adapter/`) → Уровень 4
   - Доменный слой (`Entity`, `AggregateRoot`) → Уровень 3
   - Маркеры `UseCaseCommand` / `UseCaseQuery` → Уровень 2
   - Иначе → Уровень 1

   Назови уровень явно. Подбирай дизайн под него: не вводить DDD-агрегаты на Уровне 1, не отбрасывать CQRS-маркеры, если проект на Уровне 2+.

4. **Уточни операцию из описания пользователя.** Определи:
   - Это **команда** (меняет состояние) или **запрос** (только чтение).
   - Входные данные (REST-тело, path-параметры, заголовки — переводятся в JsonBean и ID-ы).
   - Выход: JsonBean / read-DTO / `UseCaseEmptyResult`.
   - Сквозные потребности: идемпотентность, контекст авторизации, асинхронность vs синхронность, batch.
   - На Уровне 3+: какой агрегат затрагивается, какие инварианты держатся, какие события публикуются.

5. **Произведи код.** Пиши полные Java-файлы (Java 21+). **Lombok-defaults обязательны** (`JS-6.1`–`JS-6.7` в `java-style-guide.md`): `@RequiredArgsConstructor` на каждом Spring-бине с DI, `@Slf4j` вместо ручного `Logger`, `@Getter` на доменных исключениях с payload-полями. Lombok **не** навешиваем на records.

   **Не цитируй коды правил в комментариях кода** (`JS-7.3`). Никаких `// R-UC-3`, `// R-LAY-2`, `// R-DSP-X2`, `// R-CQRS-1` в исходниках. Соответствие правилу выражается именами (`CreateProductUseCase`, `*Query*Handler`) и структурой (record + marker interface + `@Component` + `@Transactional`). Комментарий уместен только если WHY неочевиден из кода — и тогда без кода правила.

   - **`<Operation>UseCase`** — `record`, реализует `UseCase<R>` (Уровень 1) или `UseCaseCommand<R>` / `UseCaseQuery<R>` (Уровень 2+). Иммутабельный, без логики.
   - **`<Operation>UseCaseHandler`** — `@Component` + `@RequiredArgsConstructor`, реализует `UseCaseHandler<MyUseCase, R>`, возвращает `MyUseCase.class` из `useCaseType()`, имеет `@Transactional` (или `readOnly = true`). Поля — `private final`, без явного конструктора. Логика живёт здесь.
   - **Controller** — `@RestController class XController implements <Tag>Api` (style guide §12.2 — интерфейс генерируется openapi-generator-ом из `src/main/resources/openapi/<service>.openapi.yaml`). Методы — `@Override` интерфейсных, дополнительно навешиваются `@PreAuthorize`. Тело метода: маппинг request DTO → UseCase, `dispatcher.dispatch(...)`, обёртка в `ResponseEntity`. Никакого `@RequestMapping` на классе, никаких ручных request/response DTO в `jsonbean/`. Если openapi-generator не подключён — это повод вызвать `ucp-bootstrap-design`, а не писать ручной контроллер.
   - **Mapper** (если нужен новый маппинг) — **MapStruct-интерфейс обязателен** (`R-LAY-3`): `@Mapper(componentModel = "spring")` + `default`-методы внутри интерфейса для нетривиальных конверсий. Ручной `@Component`-маппер — только при stateful / DI-зависимом маппинге, что не покрывается MapStruct.
   - **(Уровень 3+)** **Доменные части** — только если операция реально требует нового состояния агрегата, value object'а или события. Следуй `ddd-tactical-style-guide.md`. Если операция чисто read — предпочитай Read Model и пропускай агрегат.
   - **(Уровень 4)** Раскладка файлов: `core/<bc>/usecase/...`, `core/<bc>/port/...`, `adapter/in/rest/...`, `adapter/out/<storage>/...`. Домен живёт в `core/<bc>/domain/...`.

6. **Самопроверка перед выдачей.** Пройди эти проверки (style guide §12):
   - UseCase — record/final, без логики, имя = бизнес-операция.
   - Handler — `@Component` + `@RequiredArgsConstructor`, возвращает useCaseType, транзакционный.
   - Controller вызывает только `UseCaseDispatcher`.
   - На Уровне 2+ использован правильный CQRS-маркер, query handler имеет `readOnly = true`.
   - Модели слоёв не смешаны (JsonBean ≠ Pojo ≠ Domain).
   - На Уровне 4 `core/` не импортирует Spring / jOOQ / REST / Kafka.
   - Lombok: `@RequiredArgsConstructor` на каждом бине; `@Slf4j` если нужны логи; явных multi-arg-конструкторов нет (`JS-6.1`).

7. **Структура вывода:**
   1. Определённый уровень + краткий (один абзац) обзор дизайна (операция, команда / запрос, побочные эффекты, события).
   2. Дерево новых файлов.
   3. Каждый файл — отдельный code block с путём в заголовке.
   4. **Заметки по реализации**: сниппет зависимости (если отсутствует), предлагаемые unit-тесты (положительный сценарий + каждый инвариант + каждый путь ошибки) и маленький пример того, как контроллер-тест задиспатчит операцию.

$ARGUMENTS
