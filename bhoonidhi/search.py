"""
Bhoonidhi STAC Search and Pagination Module.
Constructs valid STAC search payloads, validates BBox / GeoJSON / CQL2 filters,
follows STAC pagination links safely, and enforces safety caps and rate limits.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import requests

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.exceptions import (
    BhoonidhiAuthError,
    BhoonidhiRateLimitError,
    BhoonidhiServerError,
    STACSearchError,
    parse_bhoonidhi_error_response,
)

logger = logging.getLogger(__name__)


@dataclass
class STACSearchResult:
    """Holds accumulated results and metadata from STAC search queries."""
    features: List[Dict[str, Any]] = field(default_factory=list)
    total_returned: int = 0
    pages_retrieved: int = 0
    pagination_capped: bool = False
    next_link: Optional[str] = None


class BhoonidhiSearch:
    """Handles STAC catalogue search, filter composition, and pagination."""

    def __init__(
        self,
        auth: BhoonidhiAuth,
        config: Optional[BhoonidhiConfig] = None,
        session: Optional[requests.Session] = None,
    ):
        self.auth = auth
        self.config = config or auth.config
        self.session = session or auth.session

    def validate_bbox(self, bbox: List[float]) -> None:
        """Validate bbox format [west, south, east, north]."""
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise ValueError(f"bbox must be a list/tuple of 4 numbers [west, south, east, north], got: {bbox}")
        west, south, east, north = bbox
        if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
            raise ValueError(f"Longitude values in bbox must be between -180 and 180: got west={west}, east={east}")
        if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
            raise ValueError(f"Latitude values in bbox must be between -90 and 90: got south={south}, north={north}")
        if west > east:
            raise ValueError(f"Invalid bbox: west ({west}) cannot be greater than east ({east})")
        if south > north:
            raise ValueError(f"Invalid bbox: south ({south}) cannot be greater than north ({north})")

    def validate_geometry(self, geometry: Dict[str, Any]) -> None:
        """Validate GeoJSON geometry [lon, lat] coordinates and closed rings."""
        if not isinstance(geometry, dict) or "type" not in geometry or "coordinates" not in geometry:
            raise ValueError("geometry must be a valid GeoJSON object with 'type' and 'coordinates'")

        geom_type = geometry["type"]
        coords = geometry["coordinates"]

        if geom_type == "Polygon":
            if not coords or not isinstance(coords, list):
                raise ValueError("Polygon coordinates must be a non-empty list of rings")
            for ring in coords:
                if len(ring) < 4:
                    raise ValueError(f"Polygon ring must contain at least 4 coordinate pairs, got: {len(ring)}")
                if ring[0] != ring[-1]:
                    raise ValueError(f"Polygon ring must be closed (start equals end): first={ring[0]}, last={ring[-1]}")
                for pt in ring:
                    if len(pt) < 2 or not (-180.0 <= pt[0] <= 180.0 and -90.0 <= pt[1] <= 90.0):
                        raise ValueError(f"Coordinate pair must be [longitude, latitude] in valid bounds: got {pt}")

    def build_search_payload(
        self,
        collections: Optional[List[str]] = None,
        ids: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        intersects: Optional[Dict[str, Any]] = None,
        datetime_range: Optional[str] = None,
        limit: int = 100,
        online_only: bool = True,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Construct a valid STAC search POST payload.

        Args:
            collections: List of STAC collection IDs.
            ids: Optional list of specific item IDs.
            bbox: Optional bounding box [west, south, east, north].
            intersects: Optional GeoJSON geometry.
            datetime_range: Optional ISO 8601 interval 'start/end'.
            limit: Page size limit (1 to 500).
            online_only: Whether to inject CQL2 filter for Online = 'Y'.
            extra_filter: Optional additional CQL2 filter condition.
        """
        payload: Dict[str, Any] = {}

        if collections:
            payload["collections"] = list(collections)

        if ids:
            payload["ids"] = list(ids)

        if bbox:
            self.validate_bbox(bbox)
            payload["bbox"] = bbox

        if intersects:
            self.validate_geometry(intersects)
            payload["intersects"] = intersects

        if datetime_range:
            payload["datetime"] = datetime_range

        # Enforce documented limit ceiling
        if limit < 1:
            limit = 1
        elif limit > 500:
            limit = 500
        payload["limit"] = limit

        # Filter construction (CQL2-JSON)
        conditions = []
        if online_only:
            conditions.append({"op": "eq", "args": [{"property": "Online"}, "Y"]})

        if extra_filter:
            conditions.append(extra_filter)

        if conditions:
            if len(conditions) == 1:
                payload["filter"] = conditions[0]
            else:
                payload["filter"] = {"op": "and", "args": conditions}
            payload["filter-lang"] = "cql2-json"

        return payload

    def search(
        self,
        collections: Optional[List[str]] = None,
        ids: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        intersects: Optional[Dict[str, Any]] = None,
        datetime_range: Optional[str] = None,
        limit: int = 100,
        online_only: bool = True,
        extra_filter: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> STACSearchResult:
        """
        Execute STAC search against Bhoonidhi API and follow pagination links up to max_pages.
        """
        initial_payload = self.build_search_payload(
            collections=collections,
            ids=ids,
            bbox=bbox,
            intersects=intersects,
            datetime_range=datetime_range,
            limit=limit,
            online_only=online_only,
            extra_filter=extra_filter,
        )

        effective_max_pages = max_pages or self.config.max_pagination_pages
        endpoint_url = f"{self.config.base_url}/data/search"

        all_features: List[Dict[str, Any]] = []
        pages_count = 0
        capped = False
        next_request = {
            "method": "POST",
            "url": endpoint_url,
            "json": initial_payload,
        }

        while next_request and pages_count < effective_max_pages:
            pages_count += 1
            response_json = self._execute_search_request(next_request)

            features = response_json.get("features", [])
            all_features.extend(features)

            # Look for next link
            links = response_json.get("links", [])
            next_link_obj = next((lnk for lnk in links if lnk.get("rel") == "next"), None)

            if not next_link_obj:
                next_request = None
                break

            href = next_link_obj.get("href")
            if not href:
                next_request = None
                break

            # Anti-SSRF check: do not send credentials to an unexpected host
            self._validate_next_link_host(href)

            # Determine method and body for pagination
            link_method = next_link_obj.get("method", "GET").upper()
            if link_method == "POST":
                body = next_link_obj.get("body") or initial_payload
                # Bhoonidhi API quirk: Upstream search backend (/Bhoonidhi-DataSearch-1.0)
                # crashes with HTTP 500 when replaying the 'fields' filter it injected into the next body.
                # Stripping 'fields' prevents upstream 500 crash and enables smooth pagination.
                if isinstance(body, dict) and "fields" in body:
                    body = {k: v for k, v in body.items() if k != "fields"}
                next_request = {"method": "POST", "url": href, "json": body}
            else:
                next_request = {"method": "GET", "url": href}

            # Search rate limit pacing (max 3 req/sec per IP)
            if self.config.search_rate_delay > 0:
                time.sleep(self.config.search_rate_delay)

        if next_request is not None and pages_count >= effective_max_pages:
            capped = True
            logger.info("Search pagination reached maximum page cap (%d pages).", effective_max_pages)

        last_next = next_request["url"] if next_request else None

        return STACSearchResult(
            features=all_features,
            total_returned=len(all_features),
            pages_retrieved=pages_count,
            pagination_capped=capped,
            next_link=last_next,
        )

    def _validate_next_link_host(self, href: str) -> None:
        """Ensure pagination URL does not redirect credentials to an untrusted domain."""
        parsed_target = urlparse(href)
        if not parsed_target.netloc:
            # Relative link is safe
            return

        base_host = urlparse(self.config.base_url).netloc
        if parsed_target.netloc.lower() != base_host.lower():
            raise STACSearchError(
                f"Security violation: Pagination next link points to unexpected host '{parsed_target.netloc}'. "
                f"Refusing to forward credentials."
            )

    def _execute_search_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request with 401 token refresh retry and 429 backoff."""
        method = req["method"]
        url = req["url"]
        json_body = req.get("json")

        max_attempts = self.config.max_retries
        attempt = 0
        reauth_tried = False

        while attempt < max_attempts:
            attempt += 1
            headers = self.auth.get_auth_header()

            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    json=json_body if method == "POST" else None,
                    headers=headers,
                    timeout=(self.config.connect_timeout, self.config.request_timeout),
                )
            except requests.RequestException as e:
                if attempt >= max_attempts:
                    raise STACSearchError(f"Network error executing search: {type(e).__name__}") from e
                time.sleep(self.config.retry_backoff_factor ** attempt)
                continue

            # Successful response
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as e:
                    raise STACSearchError("Search endpoint returned invalid JSON.") from e

            # Handle 401 Session Expired - retry once after re-authenticating
            if resp.status_code == 401 and not reauth_tried:
                reauth_tried = True
                logger.info("Received 401 Unauthorized during search; refreshing token.")
                self.auth.invalidate()
                self.auth.authenticate()
                continue

            # Handle 429 Rate Limit
            if resp.status_code == 429:
                retry_after = 2
                if "Retry-After" in resp.headers:
                    try:
                        retry_after = int(resp.headers["Retry-After"])
                    except ValueError:
                        pass
                logger.warning("Received 429 Rate Limit; waiting %d seconds.", retry_after)
                time.sleep(retry_after)
                continue

            # Handle 5xx Transient Server Errors
            if resp.status_code in (500, 502, 503, 504) and attempt < max_attempts:
                time.sleep(self.config.retry_backoff_factor ** attempt)
                continue

            # Handle Bhoonidhi's specific 404 "NO RESULTS FOUND" as a valid empty STAC FeatureCollection
            if resp.status_code == 404:
                err = parse_bhoonidhi_error_response(resp.status_code, resp.text)
                desc = (err.get("description") or "").upper()
                act = (err.get("action") or "").lower()
                if "NO RESULTS FOUND" in desc or "no results found" in act:
                    logger.info("Search returned 0 items (Bhoonidhi 404 NO RESULTS FOUND).")
                    return {
                        "type": "FeatureCollection",
                        "features": [],
                        "context": {"returned": 0, "limit": 0},
                        "links": [],
                    }

            # Non-retryable error
            err = parse_bhoonidhi_error_response(resp.status_code, resp.text)
            desc = err.get("description") or f"HTTP {resp.status_code}"
            raise STACSearchError(
                f"STAC search request failed: {desc}",
                status_code=resp.status_code,
                error_code=err.get("error_code"),
                action=err.get("action"),
            )

        raise STACSearchError("STAC search failed after maximum retry attempts.")
