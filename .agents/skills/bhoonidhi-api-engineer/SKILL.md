---
name: bhoonidhi-api-engineer
description: Integrates, extends, and maintains Python applications using the ISRO NRSC Bhoonidhi API. Use for end-to-end API work, repository integration, authentication, catalogue discovery, implementation planning, and coordination with the focused Bhoonidhi skills.
---

# Bhoonidhi API Engineer

## Mission

Build and maintain correct, secure, testable integrations with the Bhoonidhi API. Optimize for working software and accurate data retrieval—not for teaching the human user. Explain decisions briefly in the final report, but do not turn implementation tasks into lessons or quizzes unless explicitly asked.

## Before changing code

1. Inspect the repository tree, entry points, dependency files, configuration, current tests, and README.
2. Find and trace the actual code path for credentials, token lifecycle, `resolve_product_types` (if present), collection/product selection, search payload creation, pagination, download, and output naming.
3. Preserve established conventions and working behavior. Do not replace an existing client wholesale merely because a reference implementation is available.
4. Establish a baseline by running relevant existing tests or a non-destructive local check.
5. For meaningful tasks, identify the relevant focused skills: `bhoonidhi-stac-search`, `bhoonidhi-download-pipeline`, `bhoonidhi-api-debugger`, `bhoonidhi-api-test-engineer`, and `bhoonidhi-product-mapping`.

## Source of truth

- Read `references/api_reference.md` for the API facts extracted from the supplied specification.
- Prefer actual response data and current official API documentation over guessed schemas.
- When the spec and a live response differ, record the exact endpoint, method, status, and sanitized response shape. Do not silently reconcile ambiguity.
- Never invent collection IDs, item properties, filter names, pagination URLs, or response fields. Discover them through the API or existing code.

## API map

Base URL: `https://bhoonidhi-api.nrsc.gov.in`

- Authentication: `POST /auth/token`
- Logout: `POST /auth/logout` (the supplied spec does not fully define the body)
- Collections: `GET /data/collections`
- Collection: `GET /data/collections/{collection_id}`
- Collection items: `GET /data/collections/{collection_id}/items`
- Item: `GET /data/collections/{collection_id}/items/{item_id}`
- STAC search: `POST /data/search` or `GET /data/search`
- Product download: `GET /download?id={item_id}&collection={collection_id}`

See `references/api_reference.md` for request shapes, response fields, quotas, and documented status codes.

## Engineering requirements

- Use the repository's established HTTP library unless there is a strong reason to change it. Prefer session/connection reuse, explicit connect and read timeouts, bounded retries, and structured errors.
- Keep credentials in environment variables or an ignored local config. Never hardcode or print the user ID/password, access token, refresh token, or Authorization header. Sanitize logs and exception text.
- Reuse access tokens; do not request a new token per API call. Respect returned `expires_in`; refresh/re-authenticate at most once per failed request path.
- Treat token refresh as potentially rotating the refresh token; persist a newly returned token where applicable.
- Honor the API quotas: authentication 20 requests/hour/IP; search 3 requests/second/IP; up to 5 concurrent downloads per user/IP, with stricter behavior after the daily limit. Use conservative limits and lower concurrency after 412/429.
- Retry only transient failures, with a bounded exponential backoff, jitter, and `Retry-After` support. Never spin on 400/401/403/404 or retry an operation forever.
- Validate user input, remote response shape, collection IDs, date windows, bbox order, GeoJSON, and output path.
- Keep code modular. Separate authentication, request execution, search construction, pagination, product eligibility, download, path naming, and reporting where appropriate.
- Follow server-provided pagination links; never construct a link from assumptions. Do not forward bearer credentials to unexpected hosts.
- Stream binary product downloads to temporary files, verify transfer completion as far as available metadata permits, then atomically publish the final file. Do not mislabel partial files as complete.
- Do not erase existing files or change unrelated architecture without a clear need.

## Task decision path

1. Is this a search/filter/AOI/pagination task? Use `bhoonidhi-stac-search`.
2. Is this about downloading, throughput, file naming, partial files, or concurrency? Use `bhoonidhi-download-pipeline`.
3. Is it about a failed request or unexpected response? Use `bhoonidhi-api-debugger`.
4. Is it about test coverage or a regression? Use `bhoonidhi-api-test-engineer`.
5. Is it about mapping user phrases/product categories to collection IDs or fixing `resolve_product_types`? Use `bhoonidhi-product-mapping`.
6. For cross-cutting work, use this skill to coordinate and keep interfaces consistent.

## Definition of done

- Implementation matches observed/documented behavior.
- Credentials are not embedded or leaked.
- Empty results, malformed responses, expired tokens, rate limiting, and transient server errors have intentional handling.
- Pagination is complete or clearly capped/reported.
- Online eligibility and download restrictions are respected.
- Tests are run and the result is stated accurately.
- Final report identifies changed files, rationale, tests run, live checks (if any), and remaining uncertainty.
