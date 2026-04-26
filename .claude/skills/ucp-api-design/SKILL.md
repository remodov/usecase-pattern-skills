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

4. **Output as OpenAPI spec** (YAML). Include:
   - Paths with `operationId`, `tags`, `summary`, `description`
   - Request/response schemas under `components/schemas`
   - `ProblemDetails` and `Violation` schemas (copy from style guide section 13.7)
   - `ErrorCode` enum with all applicable business error codes
   - Error response examples for each endpoint (section 13.8)
   - Pagination structure if listing endpoints exist

5. **Validate your own output** against the style guide before presenting it. Check:
   - URLs: lowercase, kebab-case, plural nouns, `/api/v1/` prefix, max 2 nesting levels
   - Path params: `{id}` (not `{orderId}`), unique names in OpenAPI
   - Query params: camelCase, `page`/`size` for pagination, `sort` for sorting
   - JSON fields: camelCase, `Id` suffix for IDs, ISO 8601 dates, UPPER_SNAKE_CASE enums
   - Responses: no envelope, `content` array for collections, no null fields
   - Errors: RFC 9457, `application/problem+json`, `violations` for 400 validation

6. After the OpenAPI spec, provide a brief **implementation notes** section:
   - Spring controller method signatures
   - Key DTOs needed
   - Error codes to add to the project's ErrorCode enum

$ARGUMENTS