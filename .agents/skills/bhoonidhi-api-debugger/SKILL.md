---
name: bhoonidhi-api-debugger
description: Diagnoses Bhoonidhi API failures using request methods, payloads, status codes, sanitized response bodies, token state, STAC response shape, rate limits, and download state.
---

# Bhoonidhi API Debugger

Use when a request fails, a response is unexpected, items are missing, downloads stall, or behavior differs between code and API docs.

## Evidence-first diagnosis

1. Reproduce with the smallest safe request. Record endpoint path, method, elapsed time, HTTP status, retry count, and sanitized body shape.
2. Never print credentials, access tokens, refresh tokens, Authorization headers, or full request objects containing secrets.
3. Compare the request against `../bhoonidhi-api-engineer/references/api_reference.md` and the existing code path.
4. Separate transport failures, HTTP failures, API error JSON, malformed JSON, valid empty results, STAC pagination problems, and file-transfer failures.
5. Do not alter several subsystems at once. Form a hypothesis, add a focused test or diagnostic, then make the smallest useful fix.

## Status-oriented decision tree

- **400**: inspect JSON keys/types, grant type, date syntax, CQL2 operator nesting, bbox order and GeoJSON validity. Do not retry unchanged payloads.
- **401**: determine whether this is bad credentials, expired access token, or invalid refresh token. Refresh/re-authenticate at most once for a request path; avoid loops.
- **403**: check maximum active session behavior; prefer reusing an active session. Do not log out a session without confirming it is safe.
- **404 on download**: product may not be available in online storage. Check `Online`, then report/skip; do not retry indefinitely.
- **412**: concurrent-download constraint; wait and reduce concurrency.
- **429**: apply backoff, honor `Retry-After`, reduce traffic, and check the relevant endpoint quota.
- **500/503**: inspect API/STAC availability and retry boundedly. Escalate persistent failures.
- **504**: request/download interrupted; ensure partial files are not mistaken for completed products.
- **200 with zero features**: valid empty search; validate collection, date interval, area, and filters one at a time.
- **200 with malformed or unexpected JSON**: capture a sanitized fixture and add a regression test before changing parsers.

## Escalation

The supplied spec lists `bhoonidhi@nrsc.gov.in`. Include endpoint, method, sanitized payload/response, status, approximate time, and concise reproduction steps. Do not send credentials, tokens, or Authorization headers. The spec mentions user ID and IP address; share these only as needed through an appropriate support channel.

## Finish

State the demonstrated cause separately from hypotheses. Include what was changed, which tests reproduced the failure and verify the fix, and what remains unconfirmed by live testing.
