---
description: Review REST API contract or code for compliance with the team's REST API Style Guide. Use when reviewing OpenAPI specs, controllers, DTOs, or error handling code.
---

# REST API Contract Review

You are reviewing a REST API contract (OpenAPI spec, controller code, DTOs, or error handling) for compliance with the team's REST API Style Guide.

## Instructions

1. **Read the style guide** from `docs/rest-api-style-guide.md` in the project root. This is the single source of truth for all rules.

2. **Identify what to review.** If the user specified files — use those. Otherwise:
   - Check `git diff` for recently changed files
   - Look for OpenAPI specs (`*.yaml`, `*.yml` in resources/openapi or similar)
   - Look for REST controllers, DTOs, exception handlers

3. **Review against ALL sections** of the style guide. Check every applicable rule:
   - URL format: lowercase, kebab-case, no trailing slash, no extensions, no verbs
   - Resources: plural nouns, max 2 levels of nesting, `{id}` in path
   - HTTP methods: correct method for operation, correct status codes
   - Query params: camelCase, pagination (`page`/`size`), sorting, filtering
   - JSON fields: camelCase, dates ISO 8601, enums UPPER_SNAKE_CASE, collections plural
   - Response format: no envelope for single resources, `content` for collections, null handling
   - Error handling: RFC 9457 ProblemDetails, `application/problem+json`, `code` enum, `violations`
   - Headers: no `X-` prefix, `Idempotency-Key`, `traceparent`
   - Versioning: `/api/v1/...`, version bump only on breaking changes
   - OpenAPI metadata: `operationId`, `tags`, `summary`
   - Action endpoints: verb in infinitive, always POST
   - Batch, async, deprecation, file upload patterns

4. **Report findings** in this format:

   For each violation:
   - File and line (or endpoint path)
   - Which rule is violated (section number from style guide)
   - What's wrong
   - How to fix

   At the end — summary: total violations found, grouped by severity:
   - **Critical** — breaks the contract standard (wrong HTTP method, missing error format, wrong status code)
   - **Warning** — deviates from convention (naming, missing OpenAPI metadata)
   - **Info** — suggestion for improvement

5. If everything is compliant, say so explicitly.

$ARGUMENTS