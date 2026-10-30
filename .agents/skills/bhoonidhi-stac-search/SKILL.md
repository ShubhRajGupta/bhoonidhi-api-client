---
name: bhoonidhi-stac-search
description: Builds and debugs STAC catalogue searches against Bhoonidhi, including collection discovery, date windows, IDs, bbox/AOI geometry, CQL2 JSON filters, item metadata, and pagination.
---

# Bhoonidhi STAC Search

Use this skill for catalogue discovery, item selection, metadata inspection, spatial/temporal filtering, filter logic, or search pagination.

## Procedure

1. Read the shared contract at `../bhoonidhi-api-engineer/references/api_reference.md`.
2. Inspect current repository search code and response fixtures before redesigning it.
3. Query live collection metadata or inspect saved response JSON when collection IDs or item property names are uncertain.
4. Build small, explainable payloads first; add filters one at a time when diagnosing empty results.
5. Validate datetime strings, bbox order `[west, south, east, north]`, GeoJSON coordinate order `[longitude, latitude]`, and closed polygon rings.
6. Use POST for structured search requests. Apply `filter-lang: cql2-json` when using CQL2 filters.
7. Inspect the returned STAC `FeatureCollection`, especially `context.returned`, feature IDs, `collection`, `properties`, `assets`, and `links`.
8. Follow returned `rel=next` links rather than fabricating URLs. Honor link method/body metadata if present; do not blindly assume POST search pagination uses GET.
9. Use a configurable page cap; clearly report when the cap stops a search.
10. Never declare a search complete after only the first page unless the response has no next link.

## Filter strategy

- Verify that a property exists for the target collection before filtering on it.
- Build combined conditions incrementally. If an `and` filter returns zero items, test each condition independently to identify the restrictive clause.
- Filter for `Online = Y` when the next operation is API download. Do not assume missing `Online` means online.
- Distinguish collection IDs from item IDs and human-friendly sensor/product labels.
- Preserve metadata needed downstream; avoid a restrictive `fields` include list until required fields are known.
- Treat empty search results as valid outcomes; suggest query changes grounded in what was tested.

## Verification

Test success, empty results, invalid query shape, missing fields, multi-page results, missing/malformed next links, a next link to an unexpected host, and the pagination safety cap. Mock HTTP responses for ordinary tests; do not require real credentials.
