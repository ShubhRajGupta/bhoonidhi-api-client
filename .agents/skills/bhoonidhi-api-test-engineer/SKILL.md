---
name: bhoonidhi-api-test-engineer
description: Creates and maintains automated tests for Bhoonidhi API clients and fetchers, including mocked authentication, STAC search, pagination, rate limiting, retries, and streamed downloads.
---

# Bhoonidhi API Test Engineer

Use this skill when adding API features, modifying the fetcher, fixing bugs, or improving reliability.

## Principles

- Inspect the existing framework and conventions first (pytest/unittest, fixtures, mocks, project layout). Do not introduce a new test framework unnecessarily.
- Ordinary tests must not call the live API, require user credentials, or depend on a live network.
- Use sanitized JSON fixtures based on the supplied schema and observed responses. Do not commit actual tokens or personal data.
- Test public behavior and failure modes, not only internal implementation details.
- Add regression coverage for every fixed bug where feasible.

## Required coverage where relevant

### Authentication
- valid access-token response;
- missing/malformed token fields;
- token reuse without repeated authentication;
- refresh success including refresh-token rotation;
- refresh failure and bounded re-authentication;
- 401 is not retried indefinitely;
- secrets are absent from logs/errors.

### Search and STAC
- valid `FeatureCollection`;
- zero returned items;
- malformed response/features;
- date/bbox/GeoJSON/filter serialization;
- multiple pages and no next link;
- malformed next link, unexpected pagination host, and page safety cap;
- CQL2 filters use actual expected property names.

### Rate limit and errors
- 429 with and without `Retry-After`;
- 5xx bounded retries;
- 400/403/404/412 not blindly retried;
- timeouts and connection exceptions;
- sanitized diagnostic output.

### Downloads
- chunked successful transfer;
- interrupted transfer / stream error;
- 401 refresh once;
- 404, 412, 429, 504 behavior;
- pre-existing destination handling;
- unsafe item IDs and filename collisions;
- temporary files are not published as complete output after failure;
- no unbounded concurrency.

## Validation

Run focused tests first, then the relevant suite. Report exact commands and outcomes. If tests cannot run, say why. Separate mocked-test evidence from any optional live integration test. Do not claim a live download was verified based only on a mock.
