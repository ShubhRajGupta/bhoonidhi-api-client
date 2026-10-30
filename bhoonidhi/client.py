"""
Unified Bhoonidhi API Client.
Orchestrates authentication, collection discovery, product resolution,
STAC search, and resilient download pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
import requests

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.download import BhoonidhiDownloader, DownloadResult
from bhoonidhi.exceptions import (
    BhoonidhiError,
    BhoonidhiNotFoundError,
    parse_bhoonidhi_error_response,
)
from bhoonidhi.product_mapping import (
    ResolutionResult,
    resolve_product_types,
)
from bhoonidhi.search import BhoonidhiSearch, STACSearchResult

logger = logging.getLogger(__name__)


class BhoonidhiClient:
    """High-level client for ISRO NRSC Bhoonidhi API."""

    def __init__(
        self,
        credentials: Optional[BhoonidhiCredentials] = None,
        config: Optional[BhoonidhiConfig] = None,
    ):
        self.config = config or BhoonidhiConfig.from_env()
        self.session = requests.Session()
        self.credentials = credentials or BhoonidhiCredentials.load()
        self.auth = BhoonidhiAuth(credentials=self.credentials, config=self.config, session=self.session)
        self.search_engine = BhoonidhiSearch(auth=self.auth, config=self.config, session=self.session)
        self.downloader = BhoonidhiDownloader(auth=self.auth, config=self.config, session=self.session)

    def authenticate(self) -> str:
        """Authenticate or return current valid token."""
        return self.auth.get_valid_token()

    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Fetch available STAC collections from GET /data/collections.
        """
        url = f"{self.config.base_url}/data/collections"
        headers = self.auth.get_auth_header()

        resp = self.session.get(
            url,
            headers=headers,
            timeout=(self.config.connect_timeout, self.config.request_timeout),
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("collections", []) if isinstance(data, dict) else data

        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        raise BhoonidhiError(f"Failed to fetch collections: {parsed.get('description')}", status_code=resp.status_code)

    def get_collection(self, collection_id: str) -> Dict[str, Any]:
        """
        Fetch details for a specific collection from GET /data/collections/{collection_id}.
        """
        url = f"{self.config.base_url}/data/collections/{collection_id}"
        headers = self.auth.get_auth_header()

        resp = self.session.get(
            url,
            headers=headers,
            timeout=(self.config.connect_timeout, self.config.request_timeout),
        )
        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 404:
            raise BhoonidhiNotFoundError(f"Collection '{collection_id}' not found.")

        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        raise BhoonidhiError(f"Failed to fetch collection {collection_id}: {parsed.get('description')}")

    def get_collection_items(
        self,
        collection_id: str,
        limit: int = 10,
        bbox: Optional[List[float]] = None,
        datetime_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch items directly from a collection endpoint: GET /data/collections/{collection_id}/items
        """
        url = f"{self.config.base_url}/data/collections/{collection_id}/items"
        headers = self.auth.get_auth_header()
        params: Dict[str, Any] = {"limit": limit}
        if bbox:
            params["bbox"] = ",".join(map(str, bbox))
        if datetime_range:
            params["datetime"] = datetime_range

        resp = self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=(self.config.connect_timeout, self.config.request_timeout),
        )
        if resp.status_code == 200:
            return resp.json()

        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        raise BhoonidhiError(f"Failed to fetch items for {collection_id}: {parsed.get('description')}")

    def get_item(self, collection_id: str, item_id: str) -> Dict[str, Any]:
        """
        Fetch a single item: GET /data/collections/{collection_id}/items/{item_id}
        """
        url = f"{self.config.base_url}/data/collections/{collection_id}/items/{item_id}"
        headers = self.auth.get_auth_header()

        resp = self.session.get(
            url,
            headers=headers,
            timeout=(self.config.connect_timeout, self.config.request_timeout),
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            raise BhoonidhiNotFoundError(f"Item '{item_id}' not found in collection '{collection_id}'.")

        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        raise BhoonidhiError(f"Failed to fetch item {item_id}: {parsed.get('description')}")

    def resolve_product_types(
        self,
        inputs: Union[str, Iterable[str]],
        query_live_collections: bool = False,
    ) -> ResolutionResult:
        """
        Resolve user-friendly product labels, sensor names, or platforms into Bhoonidhi STAC collection IDs.
        """
        available = None
        if query_live_collections:
            try:
                colls = self.get_collections()
                available = [c.get("id") for c in colls if isinstance(c, dict) and "id" in c]
            except Exception as e:
                logger.warning("Could not query live collections for resolution: %s", type(e).__name__)

        return resolve_product_types(inputs, available_collections=available)

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
        Search Bhoonidhi STAC catalogue.
        """
        return self.search_engine.search(
            collections=collections,
            ids=ids,
            bbox=bbox,
            intersects=intersects,
            datetime_range=datetime_range,
            limit=limit,
            online_only=online_only,
            extra_filter=extra_filter,
            max_pages=max_pages,
        )

    def download_product(
        self,
        item_id: str,
        collection_id: str,
        output_dir: Optional[Path | str] = None,
        overwrite: bool = False,
    ) -> DownloadResult:
        """Download product by ID and collection ID."""
        return self.downloader.download_product(
            item_id=item_id,
            collection_id=collection_id,
            output_dir=output_dir,
            overwrite=overwrite,
        )

    def download_feature(
        self,
        feature: Dict[str, Any],
        output_dir: Optional[Path | str] = None,
        overwrite: bool = False,
    ) -> DownloadResult:
        """Download product from a STAC Feature dictionary, validating Online == 'Y'."""
        return self.downloader.download_feature(
            feature=feature,
            output_dir=output_dir,
            overwrite=overwrite,
        )

    def download_batch(
        self,
        features: List[Dict[str, Any]],
        output_dir: Optional[Path | str] = None,
        overwrite: bool = False,
        concurrency: Optional[int] = None,
    ) -> List[DownloadResult]:
        """Download a batch of STAC features concurrently within safe limits."""
        return self.downloader.download_batch(
            features=features,
            output_dir=output_dir,
            overwrite=overwrite,
            concurrency=concurrency,
        )

