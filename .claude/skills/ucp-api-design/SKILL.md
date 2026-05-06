---
name: ucp-api-design
description: Спроектировать новый REST API-эндпоинт или ресурс по командному REST API Style Guide. Применяется при создании новых эндпоинтов, планировании структуры API или написании OpenAPI-спек с нуля.
allowed-tools: Read Glob Grep Write Edit
---

# Проектирование REST API-эндпоинта

Ты проектируешь новый REST API-эндпоинт (или набор эндпоинтов) по командному REST API Style Guide.

## Инструкции

1. **Прочитай style guide** из `.claude/docs/rest-api-style-guide.md` в корне проекта. Следуй каждому правилу строго.

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

4. **Выход — OpenAPI-спека** (YAML). **Файл — `<module>/src/main/resources/openapi/<service>.openapi.yaml`** (style guide §12.2 — OpenAPI-first). НЕ `docs/api/`, НЕ рядом с markdown-спекой.

   Включи:
   - Paths с `operationId`, `tags`, `summary`, `description` — `operationId` станет именем метода в `*Api`, `tags` определят имя интерфейса (`<Tag>Api`).
   - Request / response schemas под `components/schemas`. Имена схем — это имена сгенерированных Java-классов (`ProductDto`, `CreateProductRequest`, `ProductPageDto`).
   - Schemas `ProblemDetails` и `Violation` (скопировать из раздела 13.7 style guide).
   - Enum `ErrorCode` со всеми применимыми business error codes.
   - Примеры error response для каждого эндпоинта (раздел 13.8).
   - Структуру пагинации, если есть list-эндпоинты.

5. **Самопроверка перед выдачей.** Проверь по style guide:
   - URL: lowercase, kebab-case, множественное число существительных, префикс `/api/v1/`, до 2 уровней вложенности
   - Path-параметры: `{id}` (не `{orderId}`), уникальные имена в OpenAPI
   - Query-параметры: camelCase, `page` / `size` для пагинации, `sort` для сортировки
   - JSON-поля: camelCase, суффикс `Id` для идентификаторов, даты ISO 8601, enum'ы UPPER_SNAKE_CASE
   - Ответы: без обёртки, массив `content` для коллекций, без null-полей
   - Ошибки: RFC 9457, `application/problem+json`, `violations` для 400 validation

6. После OpenAPI-спеки добавь короткий блок **заметок по реализации**:
   - **Подключение генератора**: плагин `org.openapi.generator` должен быть в `build.gradle.kts` (если нет — флаг для `ucp-bootstrap-design`). Output: `build/generated/openapi/src/main/java`. Сгенерированные артефакты — `<package>.generated.api.<Tag>Api` (интерфейс контроллера) + `<package>.generated.api.model.<Schema>` (DTO).
   - **Контракт контроллера**: `<X>Controller implements <Tag>Api` — НЕ ручной класс с `@RequestMapping` и handcrafted DTO. См. `ucp-pattern-design`.
   - Какие error codes добавить в Java-enum `ErrorCode` (если он отдельный) или в маппинг `@ExceptionHandler`.
   - Что **не пишем руками**: request DTO, response DTO, page DTO, интерфейс `<Tag>Api` — всё генерируется. Ручные DTO в пакете `jsonbean/` — нарушение `BS-20` (это касается DB-Pojo) **и** §12.2 (это касается API-DTO).

$ARGUMENTS
