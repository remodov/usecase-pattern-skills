---
name: ucp-api-design
description: Спроектировать новый REST API-эндпоинт или ресурс по требованиям `rest-api/*` для Java/Spring — OpenAPI-first, нейминг URL, статусы, ошибки ProblemDetails.
when_to_use: Создание новых эндпоинтов, проектирование структуры API, написание OpenAPI-спеки с нуля.
allowed-tools: Read Glob Grep Write Edit
---

# Проектирование REST API-эндпоинта

Ты проектируешь новый REST API-эндпоинт (или набор эндпоинтов) по требованиям `rest-api/*`.

## Инструкции

1. **Прочитай индекс правил** `.claude/docs/backend/rest-api/spec.md` — компактный список всех кодов (`R-URL-*`, `R-MTH-*`, `R-RSP-*`, `R-ERR-*`, …) с формулировками; следуй каждому строго. Полную версию `.claude/docs/backend/rest-api/references/java/implementation.md` (примеры, code-блоки, обоснование) читай **точечно по нужному разделу**, когда индекса не хватает — не целиком.

2. **Уточни требования.** По описанию пользователя определи:
   - Какие ресурсы вовлечены
   - Какие операции нужны (CRUD, action'ы, поиск, batch)
   - Отношения между ресурсами (вложенность vs плоско с фильтрами)
   - Нужны ли auth, пагинация, загрузка файлов, асинхронные операции

3. **Спроектируй эндпоинты.** Для каждого укажи:
   - HTTP-метод и путь URL (по всем правилам нейминга)
   - Запрос: path-параметры, query-параметры, тело запроса (с полями в camelCase)
   - Ответ: статус-код, структура тела, заголовки
   - Ошибки: применимые HTTP-коды со значениями `code`-enum и примерами `detail`

4. **Выход — OpenAPI-спека** (YAML). **Файл — `<module>/src/main/resources/openapi/<service>.openapi.yaml`** (OpenAPI-first). НЕ `docs/api/`, НЕ рядом с markdown-спекой.

   Включи:
   - Paths с `operationId`, `tags`, `summary`, `description` (`rest-api/operation-id-and-tags`, `rest-api/operation-id-and-tags`, `rest-api/operation-has-summary`) — `operationId` станет именем метода в `*Api`, `tags` определят имя интерфейса (`<Tag>Api`).
   - Параметры пути в OpenAPI — уникальные имена (`{orderId}`, `{itemId}`), хотя в дизайне URL используется `{id}` (`rest-api/unique-path-parameter-names`, `rest-api/path-parameter-naming`).
   - Request / response schemas под `components/schemas`. Имена схем — это имена сгенерированных Java-классов (`ProductDto`, `CreateProductRequest`, `ProductPageDto`).
   - Schemas `ProblemDetails` и `Violation` (см. правило `rest-api/error-codes-enumerated`).
   - Enum `ErrorCode` со всеми применимыми business error codes (`rest-api/error-codes-enumerated`).
   - Примеры error response для каждого эндпоинта (`rest-api/error-examples-in-operations`, секция 13.3 в гайде — готовые YAML).
   - Структуру пагинации, если есть list-эндпоинты (`rest-api/pagination-forms` или `rest-api/pagination-forms`).

5. **Самопроверка перед выдачей.** Проверь по требованиям и в комментарии к выдаче укажи коды правил, которые применил:
   - URL — `rest-api/path-lowercase-kebab-case`..`rest-api/operational-endpoints-outside-api`, `rest-api/collections-plural-singletons-singular`..`rest-api/resource-name-is-domain-term`, `rest-api/nesting-max-two-levels`..`rest-api/nesting-max-two-levels`, `rest-api/version-in-path`
   - Path-параметры — `rest-api/path-parameter-naming` (дизайн `{id}`), `rest-api/unique-path-parameter-names` (уникальные в OpenAPI)
   - Query-параметры — `rest-api/query-parameter-naming`..`rest-api/filters-ranges-and-search` (camelCase, пагинация `rest-api/pagination-forms`/`rest-api/pagination-forms`, сортировка `rest-api/sorting-parameter`, фильтры `rest-api/filters-ranges-and-search`/`rest-api/filters-ranges-and-search`)
   - JSON-поля — `rest-api/json-field-naming`..`rest-api/json-field-naming` (camelCase, `Id`-суффикс, ISO 8601, UPPER_SNAKE_CASE для enum)
   - Ответы — `rest-api/single-resource-is-flat`..`rest-api/no-nulls-in-successful-response` (без обёртки, `content` для коллекций, без `null`)
   - Ошибки — `error-handling/exceptions-are-part-of-contract`..`rest-api/error-status-codes-limited` (RFC 9457, `application/problem+json`, URN в `type`, `violations` для 400)
   - Action-эндпоинты — `rest-api/action-endpoints-shape`..`rest-api/action-endpoints-shape`
   - Заголовки — `rest-api/headers-standard-and-prefixed`..`rest-api/trace-context-header` (без `X-`-префикса по `rest-api/headers-standard-and-prefixed`)

6. После OpenAPI-спеки добавь короткий блок **заметок по реализации**:
   - **Подключение генератора**: плагин `org.openapi.generator` должен быть в `build.gradle.kts` (если нет — флаг для `ucp-bootstrap-design`). Output: `build/generated/openapi/src/main/java`. Сгенерированные артефакты — `<package>.generated.api.<Tag>Api` (интерфейс контроллера) + `<package>.generated.api.model.<Schema>` (DTO).
   - **Контракт контроллера**: `<X>Controller implements <Tag>Api` — НЕ ручной класс с `@RequestMapping` и handcrafted DTO. См. `ucp-pattern-design`.
   - Какие error codes добавить в Java-enum `ErrorCode` (если он отдельный) или в маппинг `@ExceptionHandler`.
   - Что **не пишем руками**: request DTO, response DTO, page DTO, интерфейс `<Tag>Api` — всё генерируется. Ручные DTO в пакете `jsonbean/` — нарушение `spring-bootstrap/external-dtos-are-handcrafted` (это касается DB-Pojo) **и** требования `rest-api/*` (это касается API-DTO — схемы определены в OpenAPI, см. `rest-api/operation-id-and-tags`).

$ARGUMENTS
