# Bhoonidhi API Client & Satellite Data Harvester

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 50 Passed](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)]()

A robust, production-grade Python integration and data harvesting engine for the **ISRO National Remote Sensing Centre (NRSC) Bhoonidhi Open Data API** ([`bhoonidhi-api.nrsc.gov.in`](https://bhoonidhi-api.nrsc.gov.in)).

Engineered to manage authentication lifecycles, safely navigate STAC catalogue search and pagination, stream large products atomically within strict concurrency quotas ($\le 5$ workers), and harvest daily browse/preview images alongside structured metadata.

---

## Repository Structure

All core library modules, executable runners, and unit tests are organized inside the `bhoonidhi/` package folder:

```text
├── bhoonidhi/                # Core package folder
│   ├── __init__.py           # Package exports & public API
│   ├── __main__.py           # Package CLI entrypoint (python -m bhoonidhi)
│   ├── client.py             # High-level BhoonidhiClient facade
│   ├── auth.py               # Token acquisition, caching, rotation, and lifecycle
│   ├── search.py             # STAC search, BBox/CQL2 validation, anti-SSRF pagination
│   ├── download.py           # Atomic streamed product downloads & concurrency pool
│   ├── preview_fetcher.py    # JPEG browse harvester, IST windowing & image validation
│   ├── product_mapping.py    # Alias normalization & canonical collection mapping
│   ├── credentials.py        # Secure .env credential loader, string masking & CLI check
│   ├── config.py             # Concurrency ceilings, timeouts, and rate limits
│   ├── exceptions.py         # Dual error-schema parser and domain exception tree
│   ├── fetch_previews.py     # Daily preview & metadata harvester runner
│   ├── verify_live_api.py    # Non-destructive live verification against Bhoonidhi API
│   └── tests/                # 50 unit and regression tests (100% mocked offline)
├── requirements.txt          # Minimal dependencies (requests, Pillow)
├── README.md                 # Complete documentation
├── LICENSE                   # MIT License
├── .env.example              # Configuration template
└── .gitignore                # Excludes credentials, data, downloads & logs
```

---

## Key Features

- **Robust Authentication & Token Lifecycle**
  - Caches access tokens and respects returned `expires_in` with a 60-second safety window to eliminate redundant auth calls.
  - Handles refresh token rotation dynamically.
  - Implements bounded single-retry re-authentication on 401 Unauthorized to prevent infinite loops.
  - Redacts passwords, tokens, and Authorization headers in logs, exceptions, and string representations.

- **STAC Search & Filter Engine**
  - Supports ISO 8601 / RFC 3339 datetime intervals and spatial filters (BBox `[west, south, east, north]` and GeoJSON Polygons).
  - CQL2-JSON filter support (e.g. `Online = 'Y'`, and filtering by Bhoonidhi catalogue upload date `updated`).
  - **Upstream Crash Prevention**: Workaround for Bhoonidhi APISIX/Java upstream 500 bugs by stripping server-injected `fields` filters when replaying `rel=next` pagination links.
  - **Anti-SSRF Protection**: Validates all pagination URLs against trusted host boundaries before forwarding bearer credentials.
  - Gracefully interprets Bhoonidhi's specific `404 NO RESULTS FOUND` responses as valid empty STAC feature collections.

- **Intelligent Product Resolution**
  - Maps common sensor and satellite aliases (e.g. `awifs`, `liss3`, `eos-04`, `cartodem`, `sentinel-1a`) into verified canonical Bhoonidhi collection IDs.
  - Deterministic deduplication preserving user query order.
  - Returns structured diagnostics and candidate suggestions for unrecognized inputs without crashing.

- **Safe Streaming Download Pipeline**
  - Enforces `Online == 'Y'` eligibility, advising when Bhoonidhi Web Browse & Order is required.
  - Streams binary payloads in 1 MB chunks to temporary `.part` files, validating `Content-Length` before atomic publishing.
  - Cleans up incomplete or corrupted files immediately upon network interruption or integrity mismatch.
  - Restricts worker pool concurrency to $\le 5$ per user/IP, honoring HTTP 412/429 concurrency and rate-limit backoffs.

- **Daily Preview & Metadata Harvester**
  - Converts calendar days in `Asia/Kolkata` (IST, UTC+05:30) to RFC 3339 UTC intervals.
  - Discovers and downloads genuine JPEG/PNG browse/thumbnail assets (rejecting heavy scientific `.zip` or `.tif` files).
  - Validates image raster bytes via magic bytes and PIL before saving.
  - Automatically exports `metadata.json`, `metadata.csv`, and `manifest.json`.

---

## Verified Catalogue Inventory (61 Collections)

Discovered live from ISRO NRSC Bhoonidhi (`/data/collections`):

| Satellite / Platform | Collections | Notable Sensors & Processing Levels |
| :--- | :--- | :--- |
| **EOS-06** (Oceansat-3) | 27 | OCM-LAC (500m) & OCM-GAC (4km): L1C, Chlorophyll, TSM, AOD, RRS, DA, NDVI; SCAT wind vectors (1B, 2B, 3WW, 3SH, 3SV) |
| **ResourceSat-2 & 2A** | 12 | AWIFS (56m), LISS-3 (23.5m), LISS-4 (5.8m High-Res): L2 standard, BOA reflectance, 15-day 100m NDVI mosaics |
| **NISAR** (NASA-ISRO SAR) | 11 | S-band SAR & Beta products: GSLC, RSLC, GCOV, GUNW, RUNW, GOFF, ROFF, RIFG |
| **EOS-04** (RISAT-1A SAR) | 7 | Fine Resolution Stripmap (FRS1, FRS2 L2A), Medium Resolution (MRS L2B, Soil Moisture, mosaics), Coarse (CRS L2B) |
| **Sentinel-1A** (Copernicus) | 2 | SAR-IW_GRD (Ground Range Detected), SAR-IW_SLC (*indexed through 2026-06-30*) |
| **CartoSat-1** | 1 | CartoDEM 30m Digital Elevation Model |
| **Novasar-1** | 1 | AIS (Automatic Identification System vessel tracking) |

---

## Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/ShubhRajGupta/bhoonidhi-api-client.git
cd bhoonidhi-api-client
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure credentials
Copy `.env.example` to `.env` and enter your registered Bhoonidhi account details:
```bash
cp .env.example .env
```
Edit `.env`:
```env
BHOONIDHI_USER_ID=your_registered_username
BHOONIDHI_PASSWORD=your_registered_password

# Optional overrides
BHOONIDHI_BASE_URL=https://bhoonidhi-api.nrsc.gov.in
BHOONIDHI_DOWNLOAD_DIR=./downloads
BHOONIDHI_MAX_CONCURRENT_DOWNLOADS=2
BHOONIDHI_REQUEST_TIMEOUT=60
```
> **Security Notice**: `.env` is strictly excluded in `.gitignore`. Credentials and bearer tokens are never logged or committed.

Verify credentials locally without leaking:
```bash
python bhoonidhi/credentials.py
```

---

## Usage Guide

### 1. Python SDK

```python
from bhoonidhi.client import BhoonidhiClient

# Initialize client (loads credentials from .env)
client = BhoonidhiClient()

# 1. Resolve human-friendly aliases to Bhoonidhi collection IDs
res = client.resolve_product_types(["awifs", "eos-04", "cartodem"])
print("Resolved collections:", res.resolved)
# Output: ['ResourceSat-2_AWIFS_L2', 'EOS-04_SAR-MRS_L2A', 'CartoSat-1_PAN_CartoDEM_30m']

# 2. Search STAC catalogue with bounding box and date range
search_result = client.search(
    collections=["EOS-04_SAR-FRS2_L2A"],
    bbox=[75.0, 15.0, 80.0, 20.0],  # [west, south, east, north]
    datetime_range="2026-10-01T00:00:00Z/2026-10-29T23:59:59Z",
    limit=10,
    online_only=True,
    max_pages=2,
)
print(f"Found {search_result.total_returned} features across {search_result.pages_retrieved} pages.")

# 3. Stream product download (atomic .part staging, integrity check, max 5 concurrency)
if search_result.features:
    item = search_result.features[0]
    dl_res = client.download_feature(item, output_dir="./downloads")
    print(f"Download status: {dl_res.status}, path: {dl_res.file_path}")
```

### 2. Daily Preview Harvester CLI

Fetches all scenes for a given local calendar day in India (`Asia/Kolkata`), downloads validated small JPEG thumbnails, and generates metadata files:

```bash
# Run via python module (recommended)
python -m bhoonidhi --date 2026-10-29 --collection ResourceSat-2_AWIFS_L2

# Or directly through fetch_previews script
python bhoonidhi/fetch_previews.py --date 2026-10-29 --collection EOS-04_SAR-FRS2_L2A

# Querying Sentinel-1A SAR for an indexed historical date (e.g. 29 June 2026)
python -m bhoonidhi --date 2026-06-29 --collection Sentinel-1A_SAR-IW_GRD
```

Output directory layout:
```text
data/YYYY-MM-DD/<collection_id>/
├── previews/
│   ├── <item_id_1>.jpg
│   └── <item_id_2>.jpg
├── metadata.json       # Complete raw STAC item records
├── metadata.csv        # Tabular index of acquisition times, bounding boxes & sizes
└── manifest.json       # Job statistics, timestamps, and data volume summary
```

### 3. Non-Destructive Live API Verification

Performs a live end-to-end check of authentication, collection discovery, and a non-destructive search:
```bash
python bhoonidhi/verify_live_api.py
```

---

## Running the Automated Test Suite

All core functionality is covered by 50 offline unit tests using mocks and sanitized JSON fixtures (no live credentials or network connection required):

```bash
python -m unittest discover -s bhoonidhi/tests -p "test_*.py" -v
```

```text
Ran 50 tests in 0.144s
OK
```

Test coverage includes:
- Token caching, refresh token rotation, and single-retry 401 re-authentication.
- Dual Bhoonidhi error schemas (`errorCode/description` and `ErrorCode/Description/Action`).
- STAC BBox order validation `[west, south, east, north]` and closed GeoJSON polygon rings.
- Anti-SSRF next-link domain enforcement.
- Pagination field-stripping workaround for upstream 500 error mitigation.
- Streamed chunk downloading, `.part` recovery, and integrity size validation.
- Concurrency cap throttling ($\le 5$ workers) and HTTP 412/429 backoff.
- Image byte validation via magic bytes and PIL raster dimension checks.

---

## Contributing & License

Contributions, issue reports, and feature requests are welcome!

Distributed under the **MIT License**.
All satellite data accessed via Bhoonidhi is subject to ISRO / NRSC Data Distribution Policies.
