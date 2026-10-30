# The Bhoonidhi API Masterclass: Engineering & Architecture Guide

A complete, in-depth guide to understanding, reverse-engineering, and integrating with the **ISRO National Remote Sensing Centre (NRSC) Bhoonidhi Open Data API** ([`bhoonidhi-api.nrsc.gov.in`](https://bhoonidhi-api.nrsc.gov.in)).

---

## Table of Contents

1. [API Fundamentals in Context of Bhoonidhi](#1-api-fundamentals-in-context-of-bhoonidhi)
2. [Bhoonidhi Infrastructure & How We Discovered It](#2-bhoonidhi-infrastructure--how-we-discovered-it)
3. [Authentication & The Token Lifecycle](#3-authentication--the-token-lifecycle)
4. [Catalogue Discovery: 61 Collections Across 8 Platforms](#4-catalogue-discovery-61-collections-across-8-platforms)
5. [STAC Search: Spatiotemporal Queries & Upstream Bugs](#5-stac-search-spatiotemporal-queries--upstream-bugs)
6. [The Three Timestamps: Acquisition vs Upload vs Processing](#6-the-three-timestamps-acquisition-vs-upload-vs-processing)
7. [Product Downloads vs Preview Harvesting](#7-product-downloads-vs-preview-harvesting)
8. [Defensive Error Parsing & Dual Schemas](#8-defensive-error-parsing--dual-schemas)
9. [Codebase Map: Every File and Its Responsibility](#9-codebase-map-every-file-and-its-responsibility)
10. [Step-by-Step Commands & Verification](#10-step-by-step-commands--verification)

---

## 1. API Fundamentals in Context of Bhoonidhi

An **API** (Application Programming Interface) is a formal contract allowing our Python application to speak directly to ISRO's database servers over HTTP.

### How an HTTP Call Works
Every interaction consists of:
- **Endpoint**: The URL destination (e.g. `https://bhoonidhi-api.nrsc.gov.in/data/search`).
- **HTTP Method**:
  - `GET`: Read-only queries (retrieving collection lists, single items, or binary downloads).
  - `POST`: Submitting structured data (login credentials, complex search filters).
- **Headers**: Metadata sent with the call (e.g. `Authorization: Bearer <token>`, `Content-Type: application/json`).
- **Body**: The payload (typically a JSON document with search filters).
- **Status Codes**: 
  - `200 OK`: Request succeeded.
  - `401 Unauthorized`: Bad credentials or expired session.
  - `402 Payment Required`: Product requires account quota clearance.
  - `404 Not Found`: No resource or no matching scenes.
  - `412 Precondition Failed`: Concurrency quota exceeded ($\ge 5$).
  - `429 Too Many Requests`: Rate limit exceeded.
  - `500 Internal Server Error`: Backend service failure.

### What is STAC?
Bhoonidhi is built on the **SpatioTemporal Asset Catalog (STAC)** specification (v1.0.0). STAC is an open standard designed specifically for geospatial and satellite imagery:
- **Collection**: A grouping of products sharing the same platform, sensor, and processing level (e.g., `ResourceSat-2_AWIFS_L2`).
- **Item / Feature**: A single scene captured by the satellite at a specific timestamp, represented as a GeoJSON Feature.
- **Assets**: Links to actual data files associated with the scene (thumbnails, XML metadata, raw rasters).

---

## 2. Bhoonidhi Infrastructure & How We Discovered It

When interfacing with an enterprise government API, published documentation is often incomplete or outdated. Here is how we uncovered Bhoonidhi's true technical architecture by probing live responses.

### Discovery 1: The Gateway Layer
By inspecting response headers on raw requests:
```text
Server: APISIX/3.9.1
Date: Thu, 29 Oct 2026 21:41:49 GMT
X-RateLimit-Limit: 3
X-RateLimit-Remaining: 1
```
- **Finding**: Bhoonidhi sits behind **Apache APISIX (v3.9.1)**, a high-performance open-source API gateway.
- **Consequence**: APISIX enforces strict rate limiting and token validation before requests ever reach ISRO's database. If the gateway doesn't like a header or rate, it rejects the request instantly.

### Discovery 2: The Upstream Backend
When requests trigger errors (such as during multi-page pagination or unthrottled searches), the raw error JSON reveals the upstream service:
```json
{
  "timestamp": "2026-10-29T21:46:03.620+00:00",
  "status": 500,
  "error": "Internal Server Error",
  "path": "/Bhoonidhi-DataSearch-1.0/v1/search"
}
```
- **Finding**: The backend is a Java Spring Boot application named `Bhoonidhi-DataSearch-1.0`.
- **Consequence**: The upstream Java backend has distinct parsing bugs (such as crashing on nested `fields` parameter replay) that require defensive workarounds in our client.

### Discovery 3: Gateway Rate Limit Rules
Live probing established the three operational quotas enforced by APISIX:
1. **Authentication**: Capped at 20 requests/hour per IP (with a 200-bucket burst reset).
2. **STAC Search**: Capped at 3 requests/second per IP (`X-RateLimit-Limit: 3`).
3. **Downloads**: Hard limit of 5 concurrent active connections per user/IP.

---

## 3. Authentication & The Token Lifecycle

**Code Files**: [`bhoonidhi/auth.py`](file:///x:/Projects/NRSC/bhoonidhi/auth.py), [`bhoonidhi/credentials.py`](file:///x:/Projects/NRSC/bhoonidhi/credentials.py)

### How Authentication Works
Bhoonidhi uses OAuth 2.0 password and refresh token grants:
- **Login Request**:
  - `POST /auth/token`
  - Body: `{"userId": "username", "password": "password", "grant_type": "password"}`
- **Success Response**:
  - Returns `access_token`, `token_type: "Bearer"`, `expires_in: 1200` (20 minutes), and `refresh_token`.

### Critical Engineering Decisions
1. **Token Caching & Safety Buffer**:
   Never request a token per API call. If a script calls `/auth/token` 20 times in an hour, APISIX returns `429 Too Many Requests` and locks you out. Our [`BhoonidhiAuth`](file:///x:/Projects/NRSC/bhoonidhi/auth.py) caches the token and subtracts a 60-second safety buffer from `expires_in`.
2. **Refresh Token Rotation**:
   When calling `grant_type: refresh_token`, Bhoonidhi issues a new access token and can also issue a rotated refresh token. The client persists this new refresh token dynamically.
3. **Where Tokens Belong (and Where They Don't)**:
   - Probed: `GET /download?token=<token>` $\rightarrow$ **HTTP 401 Unauthorized**.
   - Probed: `GET /download` with `Authorization: <token>` $\rightarrow$ **HTTP 401 Unauthorized**.
   - Probed: `GET /download` with `Authorization: Bearer <token>` $\rightarrow$ **HTTP 200 OK**.
   - **Rule**: Tokens must strictly live in the `Authorization: Bearer` header. Putting them in URLs is insecure and rejected by the APISIX gateway.
4. **Single-Retry 401 Recovery**:
   If an access token expires mid-session, the client invalidates the token, re-authenticates once, and retries the request. If it fails a second time, it halts to avoid an infinite re-auth loop.

---

## 4. Catalogue Discovery: 61 Collections Across 8 Platforms

**Code Files**: [`bhoonidhi/product_mapping.py`](file:///x:/Projects/NRSC/bhoonidhi/product_mapping.py), [`bhoonidhi/client.py`](file:///x:/Projects/NRSC/bhoonidhi/client.py)

Querying `GET /data/collections` revealed 61 available datasets grouped across 8 satellite platforms:

```text
|-- EOS-06 (Oceansat-3) [27 collections]
|   |-- OCM-LAC (500m Local Area Coverage): L1C, Chlorophyll, TSM, AOD, RRS, DA, NDVI, 8-day composites
|   |-- OCM-GAC (4km Global Area Coverage): L1C, Chlorophyll, TSM, AOD, RRS, DA, NDVI
|   \-- SCAT (Scatterometer): Ocean surface wind vectors (1B, 2B, 3WW, 3SH, 3SV)
|-- ResourceSat-2 & ResourceSat-2A [12 collections]
|   |-- AWIFS (56m Wide Field): L2 standard, BOA reflectance, 15-day 100m NDVI mosaics
|   |-- LISS-3 (23.5m Multispectral): L2 standard, BOA surface reflectance
|   \-- LISS-4 (5.8m High Resolution): LISS4-MX70_L2
|-- NISAR (NASA-ISRO SAR) [11 collections]
|   \-- S-band & Beta products: GSLC, RSLC, GCOV, GUNW, RUNW, GOFF, ROFF, RIFG
|-- EOS-04 (RISAT-1A SAR) [7 collections]
|   |-- Fine Resolution Stripmap: FRS1_L2A, FRS2_L2A
|   |-- Medium Resolution: MRS_L2B, Soil Moisture (MRS_SM), 1-deg mosaics
|   \-- Coarse Resolution Stripmap: CRS_L2B
|-- Sentinel-1A (Copernicus Mirror) [2 collections]
|   \-- SAR-IW_GRD (Ground Range Detected), SAR-IW_SLC
|-- CartoSat-1 [1 collection]
|   \-- CartoSat-1_PAN_CartoDEM_30m (30-meter Digital Elevation Model)
\-- Novasar-1 [1 collection]
    \-- Novasar-1_AIS (Vessel tracking)
```

### The Sentinel-1A Cutoff Mystery Solved
When querying `Sentinel-1A_SAR-IW_GRD` for recent dates (e.g. October 2026), it returned 0 items. By querying the collection metadata endpoint `GET /data/collections/Sentinel-1A_SAR-IW_GRD`, we inspected the raw `extent` field:
```json
"temporal": {
  "interval": [["2019-10-09T00:00:00Z", "2026-06-30T00:00:00Z"]]
}
```
**Conclusion**: Sentinel-1A is an ESA satellite mirrored by ISRO. The Bhoonidhi mirror index currently terminates at **30 June 2026**. Testing for `2026-06-29` retrieved **40 scenes** instantly, while testing for `2026-07-01` confirmed 0 scenes.

---

## 5. STAC Search: Spatiotemporal Queries & Upstream Bugs

**Code File**: [`bhoonidhi/search.py`](file:///x:/Projects/NRSC/bhoonidhi/search.py)

### The Search Payload
Structured queries are submitted via `POST /data/search`:
```json
{
  "collections": ["EOS-04_SAR-FRS2_L2A"],
  "datetime": "2026-10-28T18:30:00Z/2026-10-29T18:29:59Z",
  "bbox": [75.0, 15.0, 80.0, 20.0],
  "limit": 100,
  "filter": {
    "op": "eq",
    "args": [{"property": "Online"}, "Y"]
  },
  "filter-lang": "cql2-json"
}
```

### Crucial Bug Discoveries & Solutions

#### Bug 1: The `404 NO RESULTS FOUND` Anomaly
Standard STAC APIs return `HTTP 200` with `{"features": [], "context": {"returned": 0}}` when a search matches zero items.  
Bhoonidhi instead returns `HTTP 404 Not Found` with:
```json
{"ErrorCode": "404", "Description": "NO RESULTS FOUND", "Action": "No results found. Please modify the inputs and try again."}
```
If an HTTP client treats all 404s as errors, every query that finds zero items crashes the pipeline.  
**Solution**: [`BhoonidhiSearch`](file:///x:/Projects/NRSC/bhoonidhi/search.py) intercepts this specific 404 and safely translates it into an empty `STACSearchResult(total_returned=0, features=[])`.

#### Bug 2: The Upstream 500 Crash on Next-Page Replay
When a search returns multi-page results, Bhoonidhi provides a `rel=next` link with a POST body for page 2:
```json
{
  "collections": ["EOS-04_SAR-FRS2_L2A"],
  "token": "next:EOS-04_SAR-FRS2_L2A:E04_SAR_...",
  "limit": 1,
  "fields": {"exclude": ["assets.data", "properties.MetaData", "properties.IsDeleted"]}
}
```
When our client submitted this server-provided body to fetch page 2, the server crashed with `HTTP 500 Internal Server Error`.  
**How We Diagnosed It**: We isolated each key in the JSON body. Testing without `fields` returned **HTTP 200 OK** and retrieved Page 2 cleanly! The Java backend `/Bhoonidhi-DataSearch-1.0` crashes when attempting to parse the nested `fields.exclude` block.  
**Solution**: In [`bhoonidhi/search.py`](file:///x:/Projects/NRSC/bhoonidhi/search.py#L215-L225), the client automatically strips the `fields` key from the next-link body before replay.

#### Bug 3: Anti-SSRF Protection
In distributed STAC catalogs, malicious or misconfigured next-links could point to an attacker's domain (e.g. `https://attacker.com/data/search?page=2`). If the client blindly forwards `Authorization: Bearer <token>`, your credentials are stolen.  
**Solution**: [`_validate_next_link_host`](file:///x:/Projects/NRSC/bhoonidhi/search.py#L240-L253) parses the netloc of the next link and refuses to forward bearer credentials to any domain other than `bhoonidhi-api.nrsc.gov.in`.

---

## 6. The Three Timestamps: Acquisition vs Upload vs Processing

**Code File**: [`bhoonidhi/preview_fetcher.py`](file:///x:/Projects/NRSC/bhoonidhi/preview_fetcher.py)

A common point of confusion is whether "data uploaded yesterday" can be retrieved. In satellite systems, there are three distinct dates for every single scene:

1. **Acquisition Time (`properties.datetime`)**: The moment the sensor physically exposed the detector from orbit.
2. **Product Generation Time (`properties.GenerationTime`)**: The moment the ground station at Shadnagar / Antarctica downlinked and processed the telemetry into Level-2 terrain-corrected data.
3. **Catalogue Publication Time (`properties.updated`)**: The moment the metadata was written into the Bhoonidhi STAC database.

### Evidence from a Live Scene
Inspecting scene `E04_SAR_FR2_29OCT2026_...`:
- `datetime`: `2026-10-29T20:31:02Z` (Acquired at night)
- `GenerationTime`: `2026-10-30T05:51:29` (Processed 9 hours later)
- `updated`: `2026-10-30 06:01:07` (Catalogued 10 minutes after generation)

### How to Query Both Ways
- **To find images taken on a date**: Use the standard `datetime` range:
  ```python
  client.search(collections=["EOS-04_SAR-FRS2_L2A"], datetime_range="2026-10-28T18:30:00Z/2026-10-29T18:29:59Z")
  ```
- **To find items uploaded to Bhoonidhi on a date**: Use a CQL2 filter on `updated`:
  ```python
  client.search(collections=["EOS-04_SAR-FRS2_L2A"], extra_filter={"op": "like", "args": [{"property": "updated"}, "2026-10-29%"]})
  ```
  *(Proved live: returned 13 EOS-04 products uploaded to Bhoonidhi on 29 October 2026!)*

---

## 7. Product Downloads vs Preview Harvesting

**Code Files**: [`bhoonidhi/download.py`](file:///x:/Projects/NRSC/bhoonidhi/download.py), [`bhoonidhi/preview_fetcher.py`](file:///x:/Projects/NRSC/bhoonidhi/preview_fetcher.py)

### The Full Product Download Endpoint (`GET /download`)
Used for retrieving raw satellite archives:
- URL: `GET https://bhoonidhi-api.nrsc.gov.in/download?id=<item-id>&collection=<collection-id>`
- Header: `Authorization: Bearer <token>`
- **Online vs Offline Products**: Only items with `Online == 'Y'` are directly downloadable. Products with `Online == 'N'` require placing an order on the Bhoonidhi web portal.
- **Open vs Restricted Products**:
  - Open datasets (Sentinel-1A) return `HTTP 200 OK` with a direct 1.73 GB zip stream.
  - High-resolution or restricted domestic datasets (EOS-04 FRS2) return `HTTP 402` until the account receives quota clearance from NRSC.
- **Concurrency & Stream Protection**:
  - Streams in 1 MB chunks to temporary `<id>.zip.part` files.
  - Verifies `Content-Length` upon stream completion before atomically renaming to `.zip`.
  - Cleans up `.part` files on failure so partial transfers are never mistaken for complete data.
  - Bounded concurrency pool capped at $\le 5$ workers to avoid triggering `HTTP 412`.

### The Preview Harvester (`bhoonidhi/preview_fetcher.py`)
**Why We Never Use `/download` for Previews**: The `/download` endpoint delivers multi-gigabyte scientific zip packages. Previews must be extracted from the STAC asset links:
1. **Asset Discovery**: Inspects `assets.thumbnail.href` or `assets.browse.href`.
   - Example URL: `https://bhoonidhi.nrsc.gov.in/stac/PRODUCTJPGS/E04/SAR-FRS2/2026/OCT/29/E04_SAR_...jpg`
2. **URL Safety Inspection**: Rejects any URL ending in `.zip`, `.tar`, `.tif`, or containing `/download`.
3. **Byte Validation**: Inspects magic bytes (`\xff\xd8\xff` for JPEG, `\x89PNG\r\n\x1a\n` for PNG) and opens the stream in PIL to verify width and height before saving.
4. **Size Cap**: Enforces a strict default ceiling of 10 MB per preview.
5. **Metadata Archival**: Automatically compiles `metadata.json`, `metadata.csv`, and `manifest.json`.

---

## 8. Defensive Error Parsing & Dual Schemas

**Code File**: [`bhoonidhi/exceptions.py`](file:///x:/Projects/NRSC/bhoonidhi/exceptions.py)

Bhoonidhi returns error payloads in two different casing conventions across its microservices:

#### Format A (CamelCase keys)
```json
{
  "errorCode": "AUTH001",
  "description": "Invalid user credentials"
}
```

#### Format B (PascalCase keys)
```json
{
  "ErrorCode": "DOW412",
  "Description": "Maximum sessions reached",
  "Action": "Please retry after 60 seconds"
}
```

### The Solution: [`parse_bhoonidhi_error_response`](file:///x:/Projects/NRSC/bhoonidhi/exceptions.py#L75-L105)
Our defensive parser checks `errorCode` or `ErrorCode`, `description` or `Description`, and extracts optional `Action` guidance. It maps status codes to explicit domain exceptions:
- `401` $\rightarrow$ `BhoonidhiAuthError`
- `403` $\rightarrow$ `BhoonidhiSessionLimitError`
- `404` $\rightarrow$ `BhoonidhiNotFoundError`
- `412` $\rightarrow$ `BhoonidhiConcurrencyError`
- `429` $\rightarrow$ `BhoonidhiRateLimitError`
- `500-504` $\rightarrow$ `BhoonidhiServerError`

---

## 9. Codebase Map: Every File and Its Responsibility

All core code lives inside the `bhoonidhi/` package folder:

| File | Primary Responsibility |
| :--- | :--- |
| [`bhoonidhi/__init__.py`](file:///x:/Projects/NRSC/bhoonidhi/__init__.py) | Package initialization and public API symbol exports. |
| [`bhoonidhi/__main__.py`](file:///x:/Projects/NRSC/bhoonidhi/__main__.py) | Enables top-level command-line execution (`python -m bhoonidhi`). |
| [`bhoonidhi/client.py`](file:///x:/Projects/NRSC/bhoonidhi/client.py) | High-level `BhoonidhiClient` facade connecting authentication, search, and download. |
| [`bhoonidhi/auth.py`](file:///x:/Projects/NRSC/bhoonidhi/auth.py) | OAuth2 token acquisition, caching with 60s buffer, refresh rotation, and 401 retry. |
| [`bhoonidhi/search.py`](file:///x:/Projects/NRSC/bhoonidhi/search.py) | STAC payload builder, BBox/CQL2 validation, anti-SSRF checks, pagination fields-stripping workaround. |
| [`bhoonidhi/download.py`](file:///x:/Projects/NRSC/bhoonidhi/download.py) | Chunked streaming downloads, `.part` staging, `Content-Length` verification, and $\le 5$ concurrency pool. |
| [`bhoonidhi/preview_fetcher.py`](file:///x:/Projects/NRSC/bhoonidhi/preview_fetcher.py) | Daily JPEG preview harvester, IST-to-UTC day converter, raster validation via PIL, CSV/JSON metadata export. |
| [`bhoonidhi/product_mapping.py`](file:///x:/Projects/NRSC/bhoonidhi/product_mapping.py) | Normalizes aliases (`awifs`, `eos-04`, `cartodem`) to canonical collection IDs with candidate suggestions. |
| [`bhoonidhi/credentials.py`](file:///x:/Projects/NRSC/bhoonidhi/credentials.py) | Loads credentials from `.env`, masks passwords in strings/logs, and provides CLI verification. |
| [`bhoonidhi/config.py`](file:///x:/Projects/NRSC/bhoonidhi/config.py) | Enforces hard concurrency limits, timeouts, backoff multipliers, and base URLs. |
| [`bhoonidhi/exceptions.py`](file:///x:/Projects/NRSC/bhoonidhi/exceptions.py) | Domain exception hierarchy and defensive parser for dual Bhoonidhi error schemas. |
| [`bhoonidhi/fetch_previews.py`](file:///x:/Projects/NRSC/bhoonidhi/fetch_previews.py) | CLI runner script for harvesting previews for a given date and collection. |
| [`bhoonidhi/verify_live_api.py`](file:///x:/Projects/NRSC/bhoonidhi/verify_live_api.py) | Non-destructive live verification script testing auth, catalogue listing, and live search. |
| [`bhoonidhi/tests/`](file:///x:/Projects/NRSC/bhoonidhi/tests/) | Complete suite of 50 offline unit tests (100% mocked, requiring no credentials or internet). |

---

## 10. Step-by-Step Commands & Verification

### 1. Test Credentials (Zero Secret Leakage)
```powershell
python bhoonidhi/credentials.py
```
Output:
```text
============================================================
Bhoonidhi Credentials Reader & Verification
============================================================
[SUCCESS] Credentials loaded successfully.
  User ID : Sh****a
  Password: [CONFIGURED - HIDDEN]
Ready for Bhoonidhi API authentication.
```

### 2. Run the Full Offline Test Suite (50 Tests)
```powershell
python -m unittest discover -s bhoonidhi/tests -p "test_*.py" -v
```
Output:
```text
Ran 50 tests in 0.144s
OK
```

### 3. Run Live Non-Destructive Server Check
```powershell
python bhoonidhi/verify_live_api.py
```
Output:
```text
[1/4] Credentials loaded from .env: Sh****a (Password configured: YES)
[2/4] Testing live authentication (POST /auth/token)...
      [OK] Successfully authenticated. Token length: 220 chars.
[3/4] Testing catalogue discovery (GET /data/collections)...
      [OK] Retrieved 61 collections from live catalogue.
[4/4] Testing non-destructive STAC search (POST /data/search)...
      [OK] Search completed. Returned 2 features (limit 2).
```

### 4. Harvest Daily Previews & Metadata
```powershell
# Harvest ResourceSat-2 AWIFS for 29 October 2026
python -m bhoonidhi --date 2026-10-29 --collection ResourceSat-2_AWIFS_L2

# Harvest EOS-04 SAR FRS2 for 29 October 2026
python -m bhoonidhi --date 2026-10-29 --collection EOS-04_SAR-FRS2_L2A

# Harvest Sentinel-1A SAR for an indexed historical date (29 June 2026)
python -m bhoonidhi --date 2026-06-29 --collection Sentinel-1A_SAR-IW_GRD
```

Output directory layout created:
```text
data/2026-10-29/ResourceSat-2_AWIFS_L2/
|-- previews/
|   |-- R2W29OCT2026080577007900061PSANSTLC00GTDD.jpg
|   \-- ... (56 validated JPEG images)
|-- metadata.json       # Complete raw STAC item records
|-- metadata.csv        # Tabular index of acquisition times, bounding boxes & sizes
\-- manifest.json       # Job statistics, timestamps, and data volume summary
```
