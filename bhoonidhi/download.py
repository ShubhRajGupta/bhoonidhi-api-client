"""
Bhoonidhi Download Pipeline.
Implements robust satellite product downloads with Online='Y' eligibility verification,
chunked streaming to temporary files (.part), atomic destination publishing,
cleanup on interruption, and strict concurrency control (max 5 per user/IP).
"""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.exceptions import (
    BhoonidhiConcurrencyError,
    BhoonidhiNotFoundError,
    BhoonidhiRateLimitError,
    BhoonidhiServerError,
    DownloadIntegrityError,
    ProductNotOnlineError,
    parse_bhoonidhi_error_response,
)

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Outcome and metadata for a single product download."""
    item_id: str
    collection_id: str
    file_path: Optional[Path] = None
    bytes_downloaded: int = 0
    elapsed_seconds: float = 0.0
    status: str = "success"  # 'success', 'skipped_offline', 'failed', 'already_exists'
    error_message: Optional[str] = None


def sanitize_filename(name: str) -> str:
    """Sanitize item ID to prevent path traversal and invalid characters."""
    sanitized = re.sub(r"[^\w\-.]", "_", name)
    sanitized = re.sub(r"\.\.+", "_", sanitized)
    return sanitized.strip("._") or "unnamed_product"


class BhoonidhiDownloader:
    """Manages secure, bounded, chunked satellite product downloads."""

    def __init__(
        self,
        auth: BhoonidhiAuth,
        config: Optional[BhoonidhiConfig] = None,
        session: Optional[requests.Session] = None,
    ):
        self.auth = auth
        self.config = config or auth.config
        self.session = session or auth.session

    def verify_online_status(self, feature: Dict[str, Any]) -> bool:
        """
        Verify that a STAC feature has Online == 'Y'.
        Returns True if online, False otherwise.
        """
        properties = feature.get("properties", {})
        online_val = properties.get("Online") or properties.get("online")
        return str(online_val).strip().upper() == "Y"

    def download_product(
        self,
        item_id: str,
        collection_id: str,
        output_dir: Optional[Path | str] = None,
        overwrite: bool = False,
        chunk_size: int = 1024 * 1024,  # 1MB chunk
    ) -> DownloadResult:
        """
        Download a single product directly from GET /download?id={item_id}&collection={collection_id}.
        Streams chunks into a temporary .part file and atomically renames on completion.
        """
        out_dir = Path(output_dir or self.config.download_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(item_id)
        # Final file path (e.g. item_id.zip)
        dest_path = out_dir / f"{safe_name}.zip"
        part_path = out_dir / f"{safe_name}.zip.part"

        # Check if already downloaded
        if dest_path.is_file() and not overwrite:
            logger.info("File already exists at %s; skipping.", dest_path)
            return DownloadResult(
                item_id=item_id,
                collection_id=collection_id,
                file_path=dest_path,
                bytes_downloaded=dest_path.stat().st_size,
                status="already_exists",
            )

        url = f"{self.config.base_url}/download"
        params = {"id": item_id, "collection": collection_id}

        start_time = time.time()
        max_retries = self.config.max_retries
        attempt = 0
        reauth_tried = False

        while attempt < max_retries:
            attempt += 1
            headers = self.auth.get_auth_header()

            try:
                with self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    stream=True,
                    timeout=(self.config.connect_timeout, self.config.request_timeout),
                ) as resp:

                    # 200 OK: Stream download
                    if resp.status_code == 200:
                        total_bytes = 0
                        expected_length = None
                        if "Content-Length" in resp.headers:
                            try:
                                expected_length = int(resp.headers["Content-Length"])
                            except ValueError:
                                pass

                        try:
                            with open(part_path, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=chunk_size):
                                    if chunk:
                                        f.write(chunk)
                                        total_bytes += len(chunk)

                            # Validate length if header was present and non-zero
                            if expected_length and total_bytes != expected_length:
                                if part_path.exists():
                                    part_path.unlink()
                                raise DownloadIntegrityError(
                                    f"File transfer truncated: received {total_bytes} bytes, expected {expected_length} bytes."
                                )

                            # Atomically replace final file
                            if dest_path.exists() and overwrite:
                                dest_path.unlink()
                            part_path.replace(dest_path)

                            elapsed = time.time() - start_time
                            return DownloadResult(
                                item_id=item_id,
                                collection_id=collection_id,
                                file_path=dest_path,
                                bytes_downloaded=total_bytes,
                                elapsed_seconds=elapsed,
                                status="success",
                            )
                        except DownloadIntegrityError as e:
                            if part_path.exists():
                                try:
                                    part_path.unlink()
                                except OSError:
                                    pass
                            return DownloadResult(
                                item_id=item_id,
                                collection_id=collection_id,
                                status="failed",
                                error_message=str(e),
                            )
                        except Exception as e:
                            # Clean up partial file on stream/write failure
                            if part_path.exists():
                                try:
                                    part_path.unlink()
                                except OSError:
                                    pass
                            raise e

                    # 401 Unauthorized: Refresh and retry once
                    if resp.status_code == 401 and not reauth_tried:
                        reauth_tried = True
                        logger.info("Received 401 during download; re-authenticating.")
                        self.auth.invalidate()
                        self.auth.authenticate()
                        continue

                    # 404 Not Found on online storage
                    if resp.status_code == 404:
                        parsed = parse_bhoonidhi_error_response(404, resp.text)
                        desc = parsed.get("description") or "Product not available in online storage."
                        return DownloadResult(
                            item_id=item_id,
                            collection_id=collection_id,
                            status="failed",
                            error_message=f"404 Not Found: {desc}",
                        )

                    # 412 Concurrency limit exceeded
                    if resp.status_code == 412:
                        logger.warning("Received 412 Concurrency limit exceeded. Waiting before retry.")
                        time.sleep(3.0 * attempt)
                        continue

                    # 429 Rate limit exceeded
                    if resp.status_code == 429:
                        wait_sec = 5
                        if "Retry-After" in resp.headers:
                            try:
                                wait_sec = int(resp.headers["Retry-After"])
                            except ValueError:
                                pass
                        logger.warning("Received 429 Rate limit. Waiting %d seconds.", wait_sec)
                        time.sleep(wait_sec)
                        continue

                    # 504 Gateway timeout / 5xx
                    if resp.status_code in (500, 502, 503, 504) and attempt < max_retries:
                        time.sleep(self.config.retry_backoff_factor ** attempt)
                        continue

                    # Other error codes
                    parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
                    return DownloadResult(
                        item_id=item_id,
                        collection_id=collection_id,
                        status="failed",
                        error_message=f"HTTP {resp.status_code}: {parsed.get('description') or 'Unknown error'}",
                    )

            except requests.RequestException as e:
                # Clean up partial file on request exception
                if part_path.exists():
                    try:
                        part_path.unlink()
                    except OSError:
                        pass
                if attempt >= max_retries:
                    return DownloadResult(
                        item_id=item_id,
                        collection_id=collection_id,
                        status="failed",
                        error_message=f"Network error: {type(e).__name__}",
                    )
                time.sleep(self.config.retry_backoff_factor ** attempt)

        return DownloadResult(
            item_id=item_id,
            collection_id=collection_id,
            status="failed",
            error_message="Exceeded maximum download retries.",
        )

    def download_feature(
        self,
        feature: Dict[str, Any],
        output_dir: Optional[Path | str] = None,
        overwrite: bool = False,
    ) -> DownloadResult:
        """Download product from a STAC Feature dictionary, enforcing Online == 'Y'."""
        item_id = feature.get("id")
        collection_id = feature.get("collection")

        if not item_id or not collection_id:
            return DownloadResult(
                item_id=str(item_id),
                collection_id=str(collection_id),
                status="failed",
                error_message="STAC feature is missing 'id' or 'collection'.",
            )

        if not self.verify_online_status(feature):
            logger.info("Item %s has Online != 'Y'; skipping download (Browse & Order required).", item_id)
            return DownloadResult(
                item_id=item_id,
                collection_id=collection_id,
                status="skipped_offline",
                error_message="Product is offline (Online != 'Y'). Browse & Order required.",
            )

        return self.download_product(
            item_id=item_id,
            collection_id=collection_id,
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
        """
        Download multiple products concurrently using a bounded thread pool.
        Strictly limits concurrency to <= 5 per user/IP.
        """
        # Determine concurrency bounded by hard limit 5
        max_workers = concurrency or self.config.max_concurrent_downloads
        max_workers = min(max(1, max_workers), 5)

        results: List[DownloadResult] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_feature = {
                executor.submit(self.download_feature, f, output_dir, overwrite): f
                for f in features
            }

            for future in as_completed(future_to_feature):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    feat = future_to_feature[future]
                    results.append(
                        DownloadResult(
                            item_id=str(feat.get("id")),
                            collection_id=str(feat.get("collection")),
                            status="failed",
                            error_message=f"Unhandled worker error: {str(e)}",
                        )
                    )

        return results
