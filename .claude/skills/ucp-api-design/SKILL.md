---
name: ucp-api-design
description: Design a new REST API endpoint or resource following the team's REST API Style Guide. Use when creating new endpoints, planning API structure, or writing OpenAPI specs from scratch.
allowed-tools: Read Glob Grep Write Edit
---

# REST API Endpoint Design

You are designing a new REST API endpoint (or set of endpoints) following the team's REST API Style Guide.

## Instructions

1. **Read the style guide** from `docs/rest-api-style-guide.md` in the project root. Follow every rule strictly.

2. **Clarify the requirements.** From the user's description, determine:
   - What resource(s) are involved
   - What operations are needed (CRUD, actions, search, batch)
   - Relationships between resources (nesting vs. flat with filters)
   - Whether auth, pagination, file upload, async operations are needed

3. **Design the endpoints.** For each endpoint, specify:
   - HTTP method and URL path (following all naming rules)
   - Request: path params, query params, request body (with field names in camelCase)
   - Response: status code, response body structure, headers
   - Error responses: applicable HTTP codes with `code` enum values and `detail` examples

4. **Output as OpenAPI spec** (YAML). **Файл — `<module>/src/main/resources/openapi/<service>.openapi.yaml`** (style-guide §12.2 — OpenAPI-first). НЕ `docs/api/`, НЕ рядом с маркдаун-спекой.

   Include:
   - Paths with `operationId`, `tags`, `summary`, `description` — `operationId` станет именем метода в `*Api`, `tags` определят имя интерфейса (`<Tag>Api`).
   - Request/response schemas под `components/schemas`. Имена схем — это имена сгенерированных Java-классов (`ProductDto`, `CreateProductRequest`, `ProductPageDto`).
   - `ProblemDetails` и `Violation` schemas (copy from style guide section 13.7).
   - `ErrorCode` enum со всеми применимыми business error codes.
   - Error response examples for each endpoint (section 13.8).
   - Pagination structure if listing endpoints exist.

5. **Validate your own output** against the style guide before presenting it. Check:
   - URLs: lowercase, kebab-case, plural nouns, `/api/v1/` prefix, max 2 nesting levels
   - Path params: `{id}` (not `{orderId}`), unique names in OpenAPI
   - Query params: camelCase, `page`/`size` for pagination, `sort` for sorting
   - JSON fields: camelCase, `Id` suffix for IDs, ISO 8601 dates, UPPER_SNAKE_CASE enums
   - Responses: no envelope, `content` array for collections, no null fields
   - Errors: RFC 9457, `application/problem+json`, `violations` for 400 validation

6. After the OpenAPI spec, provide a brief **implementation notes** section:
   - **Generator wiring**: `org.openapi.generator` plugin должен быть в `build.gradle.kts` (если нет — флагнуть для `ucp-bootstrap-design`). Output: `build/generated/openapi/src/main/java`. Generated artifacts — `<package>.generated.api.<Tag>Api` (controller interface) + `<package>.generated.api.model.<Schema>` (DTO).
   - **Controller контракт**: `<X>Controller implements <Tag>Api` — НЕ ручной `@RequestMapping`-класс с handcrafted DTO. См. `ucp-pattern-design`.
   - Какие error codes добавить в Java `ErrorCode` enum (если он отдельный) или в `@ExceptionHandler` mapping.
   - Что **не пишем руками**: request DTO, response DTO, page DTO, `<Tag>Api` интерфейс — всё генерируется. Hand-written DTO в `jsonbean/` пакете — нарушение `BS-20` (это касается DB-Pojo) **и** §12.2 (это касается API-DTO).

$ARGUMENTS