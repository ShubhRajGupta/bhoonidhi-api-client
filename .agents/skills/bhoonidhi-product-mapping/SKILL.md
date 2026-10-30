---
name: bhoonidhi-product-mapping
description: Maps user-friendly satellite/sensor/product requests to verified Bhoonidhi STAC collection IDs and maintains product resolution logic such as resolve_product_types.
---

# Bhoonidhi Product and Collection Mapping

Use when a fetcher accepts product types or user-facing labels and must resolve them into actual Bhoonidhi collection IDs, or when debugging `resolve_product_types` and related code.

## Core rules

1. Inspect the actual `resolve_product_types` implementation and its callers before modifying it. Trace the expected input and exact output contract; preserve compatibility unless a justified change is needed.
2. Discover current IDs using `GET /data/collections` and metadata from `GET /data/collections/{collection_id}`. Treat hardcoded lists from old docs as examples, not the complete current catalogue.
3. Distinguish satellite/platform, sensor/instrument, processing level, product family, product type, and STAC collection ID. Do not treat these as interchangeable strings.
4. Normalize user inputs deliberately (case, whitespace, separators, known aliases), but avoid fuzzy matching that silently selects a wrong sensor or level.
5. Return both recognized and unresolved requests when that matches the existing contract, or propose a clear structured result if the current contract is ambiguous. Never silently drop an input.
6. Preserve deterministic ordering and deduplicate repeated IDs without losing provenance about which user terms mapped to them.
7. For ambiguous terms, present candidates with the evidence used; do not choose a collection solely because its name looks similar.
8. Keep the mapping maintainable: prefer one central mapping/metadata lookup over scattered conditional branches. If API lookups are cached, define cache lifetime and graceful fallback behavior.

## Function-level requirements

For `resolve_product_types` or equivalent:
- identify all supported input types and return shape;
- test empty input, string versus list input where applicable, aliases, case/spacing, duplicates, unknown labels, mixed valid/invalid entries, and invalid types;
- preserve the established API contract;
- produce helpful unresolved-item diagnostics without exposing credentials;
- ensure every returned collection ID exists in a verified catalogue fixture or live discovery result.

## Outcome

Report mappings added or changed, source for each mapping, unresolved aliases, compatibility impact, and tests run. Do not claim catalogue coverage is exhaustive unless checked against the current response.
