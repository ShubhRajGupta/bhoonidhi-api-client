---
name: bhoonidhi-download-pipeline
description: Implements reliable Bhoonidhi satellite-product downloads, including online eligibility, streaming, file naming, concurrency limits, retries, partial-file recovery, and download verification.
---

# Bhoonidhi Product Download Pipeline

Use this skill for download implementation, throughput, concurrency, output handling, retries, or file-integrity problems.

## Requirements

- Read `../bhoonidhi-api-engineer/references/api_reference.md` and inspect the existing pipeline.
- Only download products confirmed to have `Online = Y`; `Online = N` products require Browse & Order according to the supplied specification.
- Endpoint: `GET /download?id=<item-id>&collection=<collection-id>` with bearer authorization.
- Do not exceed five concurrent downloads per user/IP. Default lower (e.g. 1–3 workers) unless measured needs and current limits justify more. If HTTP 412 or 429 occurs, reduce concurrency and apply backoff. After daily quota, the API may allow only one concurrent download.
- Stream response chunks to disk; never buffer large satellite files fully in memory.
- Write to a unique `.part` or temporary file, and only rename to the final path after successful transfer and applicable validation. Do not silently overwrite existing files.
- Sanitize remote IDs before using them in filenames; keep output inside the configured output directory. Avoid path traversal and collisions.
- Use connect/read timeouts, bounded retries, exponential backoff with jitter, and `Retry-After` handling. Treat 404 and invalid parameters as non-retryable; handle 401 with at most one refresh/re-auth cycle; treat 412 as a concurrency signal; retry 504 cautiously.
- Preserve enough failure metadata to resume or retry deliberately, but never present a partial file as complete.
- Verify content length when trustworthy headers are provided. Do not assume every product is ZIP based on the endpoint alone; determine format from metadata or response headers.
- Record item ID, collection ID, final path, byte count, elapsed time, and outcome without logging credentials or tokens.

## Concurrency design

Use a bounded worker pool and a centralized rate/concurrency policy. Handle a mixture of per-user and per-IP constraints. Do not spawn an unbounded task per product. If several requests return 412/429, reduce concurrency dynamically and let existing work finish cleanly.

## Acceptance cases

Test successful transfer, pre-existing output, interruption mid-stream, timeout, 401 token expiry, 404 offline product, 412 concurrency, 429 rate limit, 504 gateway timeout, malformed headers, unsafe item ID, and cleanup of temporary files. Verify that failure never creates a misleading complete output file.
