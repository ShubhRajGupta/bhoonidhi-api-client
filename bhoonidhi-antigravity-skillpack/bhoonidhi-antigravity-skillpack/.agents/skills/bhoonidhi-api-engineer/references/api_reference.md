# Bhoonidhi API reference

This reference summarizes the API specification supplied with this task. It deliberately identifies details that the supplied specification does not fully define.

## Base and authentication

Base URL: `https://bhoonidhi-api.nrsc.gov.in`. Python 3+ and a registered Bhoonidhi account are required. Login: `https://bhoonidhi.nrsc.gov.in/bhoonidhi/login.html`.

### Access token
`POST /auth/token` JSON:
```json
{"userId":"<user id>","password":"<password>","grant_type":"password"}
```
The response example includes `access_token`, `refresh_token`, `token_type`, and `expires_in` (example: 1200 seconds). Use `Authorization: Bearer <access_token>` for catalogue and download calls. Reuse the token; do not fetch one for every request.

### Refresh token
`POST /auth/token` JSON:
```json
{"userId":"<user id>","refresh_token":"<refresh token>","grant_type":"refresh_token"}
```
Handle refreshed token fields as returned; the refresh token may rotate.

### Logout
`POST /auth/logout`. The spec says the refresh token belongs in the Authorization header as `Bearer <refresh_token>` but does not fully define the request body. Verify before implementing.

## STAC discovery

- `GET /data/collections`
- `GET /data/collections/{collection_id}`
- `GET /data/collections/{collection_id}/items`
- `GET /data/collections/{collection_id}/items/{item_id}`

Example IDs in the supplied specification include `ResourceSat-2_AWIFS_L2`, `EOS-04_SAR-MRS_L2A`, `EOS-06_OCM-LAC_L1C`, `Sentinel-1A_SAR-IW_GRD`, `CartoSat-1_PAN_CartoDEM_30m`, and `NISAR_SSAR_GSLC`. This is not guaranteed to be exhaustive or current; query the live collections endpoint.

## Search

Endpoint: `POST /data/search` or `GET /data/search`. Prefer POST for structured queries.

Common POST fields: `collections`, `ids`, `bbox`, `intersects`, `datetime`, `limit` (maximum documented value 500), `sortby`, `fields`, `filter`, and `filter-lang` (`cql2-json`). The schema also shows a `token` field, while the same spec says to use the Authorization header. Prefer Authorization; do not place credentials or tokens in URLs. Use a body `token` only if the current API contract explicitly requires it.

Date range form:
`2023-11-02T00:00:00Z/2023-11-03T23:59:59Z`

BBox order: `[west, south, east, north]`.

GeoJSON spatial coordinates: longitude then latitude. Polygon coordinate rings must be closed.

Online filter example:
```json
{
  "collections": ["EOS-04_SAR-MRS_L2A"],
  "datetime": "2023-01-01T00:00:00Z/2023-01-31T23:59:59Z",
  "filter": {"args": [{"property": "Online"}, "Y"], "op": "eq"},
  "filter-lang": "cql2-json",
  "limit": 500
}
```

Multi-property CQL2 filters can compose conditions using `and`; verify every property against actual item properties for the selected collection.

A typical response is a STAC `FeatureCollection` containing `context.limit`, `context.returned`, `features`, and `links`. A feature includes an `id`, geometry, collection and links, with additional properties/assets potentially available. If `context.returned` is zero, that is an empty result, not automatically an API failure.

Follow the response link whose `rel` is `next` until it is absent. POST pagination replay details are not fully specified; inspect the link's method/body metadata and actual behavior rather than assuming every next link should be a GET. Enforce a configurable safety cap and report it if reached.

## Downloads

`GET /download?id=<item-id>&collection=<collection-id>` with bearer authorization.

Only products whose `Online` property is `Y` are downloadable through the API. `Online = N` products are delayed and must use Bhoonidhi Browse & Order according to the supplied spec.

Documented download statuses: 401 session expired; 404 not available on online storage; 412 too many concurrent downloads; 500 server error; 504 interrupted download. Stream large files and use temporary paths; retry 504 cautiously and validate the final file.

## Rate limits

- Authentication: 20 requests/hour/IP.
- Search: 3 requests/second/IP.
- Downloads: 5 concurrent per user/IP; if daily download quota is reached, one concurrent download and bandwidth throttling may apply.
- HTTP 429 means back off, increase retry intervals, and reduce traffic.
- The spec recommends checking Bhoonidhi notifications for downtime/data issues.

## Error responses

The spec shows both `errorCode`/`description` and `ErrorCode`/`Description`/`Action`. Parse defensively and preserve the raw sanitized shape for diagnosis; do not assume capitalization is consistent.

| HTTP | Likely meaning from the supplied specification | Default handling |
|---|---|---|
| 400 | Invalid request keys/payload | Inspect input and schema; do not blindly retry |
| 401 | Bad credentials or expired session | Correct credentials or refresh/re-authenticate once |
| 403 | Maximum active sessions | Reuse a session or safely close an obsolete one |
| 404 | Download product absent from online storage | Report/skip; no retry loop |
| 412 | Download concurrency exceeded | Wait; reduce concurrency |
| 429 | Rate limit exceeded | Back off; honor `Retry-After` if present |
| 500/503 | Server or STAC connection problem | Bounded retry then surface failure |
| 504 | Interrupted download/request | Retry cautiously and verify output |

Support email in the supplied spec: `bhoonidhi@nrsc.gov.in`. It asks for endpoint, user ID, IP address, request/response contents and error snapshot. Never send passwords, access tokens, refresh tokens, or Authorization headers.
