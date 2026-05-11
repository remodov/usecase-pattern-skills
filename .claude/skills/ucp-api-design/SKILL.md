---
name: ucp-api-design
description: Спроектировать новый REST API-эндпоинт или ресурс по командному REST API Style Guide. Применяется при создании новых эндпоинтов, планировании структуры API или написании OpenAPI-спек с нуля.
allowed-tools: Read Glob Grep Write Edit
---

# Проектирование REST API-эндпоинта

Ты проектируешь новый REST API-эндпоинт (или набор эндпоинтов) по командному REST API Style Guide.

## Инструкции

1. **Прочитай индекс правил** `.claude/docs/rest-api-rules.md` — компактный список всех кодов (`R-URL-*`, `R-MTH-*`, `R-RSP-*`, `R-ERR-*`, …) с формулировками; следуй каждому строго. Полную версию `.claude/docs/rest-api-style-guide.md` (примеры, code-блоки, обоснование) читай **точечно по нужному разделу**, когда индекса не хватает — не целиком.

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
   - Paths с `operationId`, `tags`, `summary`, `description` (`R-OAS-1`, `R-OAS-2`, `R-OAS-4`) — `operationId` станет именем метода в `*Api`, `tags` определят имя интерфейса (`<Tag>Api`).
   - Параметры пути в OpenAPI — уникальные имена (`{orderId}`, `{itemId}`), хотя в дизайне URL используется `{id}` (`R-OAS-3`, `R-NEST-4`).
   - Request / response schemas под `components/schemas`. Имена схем — это имена сгенерированных Java-классов (`ProductDto`, `CreateProductRequest`, `ProductPageDto`).
   - Schemas `ProblemDetails` и `Violation` (см. правило `R-ERR-7`).
   - Enum `ErrorCode` со всеми применимыми business error codes (`R-ERR-4`).
   - Примеры error response для каждого эндпоинта (`R-ERR-8`, секция 13.3 в гайде — готовые YAML).
   - Структуру пагинации, если есть list-эндпоинты (`R-QRY-4` или `R-QRY-5`).

5. **Самопроверка перед выдачей.** Проверь по style guide и в комментарии к выдаче укажи коды правил, которые применил:
   - URL — `R-URL-1`..`R-URL-3`, `R-RES-1`..`R-RES-3`, `R-NEST-1`..`R-NEST-2`, `R-VER-3`
   - Path-параметры — `R-NEST-4` (дизайн `{id}`), `R-OAS-3` (уникальные в OpenAPI)
   - Query-параметры — `R-QRY-1`..`R-QRY-9` (camelCase, пагинация `R-QRY-4`/`R-QRY-5`, сортировка `R-QRY-6`, фильтры `R-QRY-2`/`R-QRY-3`)
   - JSON-поля — `R-FLD-1`..`R-FLD-5` (camelCase, `Id`-суффикс, ISO 8601, UPPER_SNAKE_CASE для enum)
   - Ответы — `R-RSP-1`..`R-RSP-8` (без обёртки, `content` для коллекций, без `null`)
   - Ошибки — `R-ERR-1`..`R-ERR-9` (RFC 9457, `application/problem+json`, URN в `type`, `violations` для 400)
   - Action-эндпоинты — `R-ACT-1`..`R-ACT-4`
   - Заголовки — `R-HDR-1`..`R-HDR-4` (без `X-`-префикса по `R-HDR-X1`)

6. После OpenAPI-спеки добавь короткий блок **заметок по реализации**:
   - **Подключение генератора**: плагин `org.openapi.generator` должен быть в `build.gradle.kts` (если нет — флаг для `ucp-bootstrap-design`). Output: `build/generated/openapi/src/main/java`. Сгенерированные артефакты — `<package>.generated.api.<Tag>Api` (интерфейс контроллера) + `<package>.generated.api.model.<Schema>` (DTO).
   - **Контракт контроллера**: `<X>Controller implements <Tag>Api` — НЕ ручной класс с `@RequestMapping` и handcrafted DTO. См. `ucp-pattern-design`.
   - Какие error codes добавить в Java-enum `ErrorCode` (если он отдельный) или в маппинг `@ExceptionHandler`.
   - Что **не пишем руками**: request DTO, response DTO, page DTO, интерфейс `<Tag>Api` — всё генерируется. Ручные DTO в пакете `jsonbean/` — нарушение `BS-20` (это касается DB-Pojo) **и** REST API style guide (это касается API-DTO — схемы определены в OpenAPI, см. `R-OAS-1`).

$ARGUMENTS
