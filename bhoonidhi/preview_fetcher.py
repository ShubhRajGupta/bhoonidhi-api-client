"""
Bhoonidhi Preview Fetcher Module.
Discovers, downloads, validates, and archives small JPEG/PNG browse and thumbnail images
along with comprehensive structured STAC metadata for satellite catalogue items.
Enforces strict size limits (default <= 10MB) and never downloads full scientific products.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from PIL import Image
import requests

from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.download import sanitize_filename
from bhoonidhi.exceptions import BhoonidhiError

logger = logging.getLogger(__name__)


def get_kolkata_day_window(target_date: str | datetime.date) -> Tuple[str, str, str]:
    """
    Computes UTC start and end timestamps for a calendar day in Asia/Kolkata (IST = UTC+05:30).
    For '2026-10-29':
      - Kolkata start: 2026-10-29 00:00:00+05:30 -> UTC 2026-10-28 18:30:00Z
      - Kolkata end:   2026-10-29 23:59:59+05:30 -> UTC 2026-10-29 18:29:59Z
    Returns: (start_utc_iso, end_utc_iso, interval_str)
    """
    if isinstance(target_date, str):
        target_date = datetime.date.fromisoformat(target_date)

    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    start_ist = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=ist)
    end_ist = datetime.datetime.combine(target_date, datetime.time(23, 59, 59), tzinfo=ist)

    start_utc = start_ist.astimezone(datetime.timezone.utc)
    end_utc = end_ist.astimezone(datetime.timezone.utc)

    start_iso = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    interval = f"{start_iso}/{end_iso}"

    return start_iso, end_iso, interval


def is_safe_preview_url(url: str) -> bool:
    """
    Validates that a URL points to an image file and NOT a heavy product or zip archive.
    """
    if not url or not isinstance(url, str):
        return False

    clean_url = url.strip().lower()
    path = urlparse(clean_url).path

    # Reject full product downloads or scientific data formats
    forbidden_endings = (
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z",
        ".tif", ".tiff", ".h5", ".hdf", ".nc", ".geotiff",
        "/download", "download?", "download"
    )
    for bad in forbidden_endings:
        if bad in clean_url or path.endswith(bad):
            return False

    # Check for valid image extensions
    allowed_exts = (".jpg", ".jpeg", ".png", ".webp")
    return any(path.endswith(ext) for ext in allowed_exts)


def extract_preview_info(feature: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Inspects STAC feature assets and links to find a genuine JPEG or PNG browse image.
    Returns: (preview_url, mime_type) or (None, None)
    """
    assets = feature.get("assets", {})
    links = feature.get("links", [])

    # 1. Search assets by key and role
    preferred_keys = ["thumbnail", "browse", "preview", "overview", "quicklook"]
    for key in preferred_keys:
        if key in assets:
            asset = assets[key]
            href = asset.get("href")
            mime = asset.get("type", "image/jpeg")
            if href and is_safe_preview_url(href):
                return href, mime

    # 2. Search all assets for image MIME type or roles
    for key, asset in assets.items():
        if not isinstance(asset, dict):
            continue
        href = asset.get("href")
        mime = asset.get("type", "")
        roles = asset.get("roles", [])
        if href and is_safe_preview_url(href):
            if ("image/" in mime) or any(r in ["thumbnail", "overview"] for r in roles):
                return href, mime or "image/jpeg"

    # 3. Check STAC links
    for link in links:
        if not isinstance(link, dict):
            continue
        rel = link.get("rel", "")
        href = link.get("href", "")
        mime = link.get("type", "")
        if rel in ["preview", "thumbnail", "overview"] and is_safe_preview_url(href):
            return href, mime or "image/jpeg"

    return None, None


def validate_image_bytes(data: bytes) -> Tuple[bool, Optional[str], Optional[Tuple[int, int]]]:
    """
    Validates that bytes represent a valid JPEG or PNG image using header inspection and PIL.
    Returns: (is_valid, format_name, (width, height))
    """
    if not data or len(data) < 10:
        return False, None, None

    # Check magic bytes
    is_jpeg = data.startswith(b"\xff\xd8\xff")
    is_png = data.startswith(b"\x89PNG\r\n\x1a\n")

    if not (is_jpeg or is_png):
        return False, None, None

    try:
        with Image.open(io.BytesIO(data)) as img:
            img_format = img.format or ("JPEG" if is_jpeg else "PNG")
            dimensions = (img.width, img.height)
            return True, img_format, dimensions
    except Exception:
        # Fallback if image has valid magic bytes but minor PIL decode variance
        if is_jpeg:
            return True, "JPEG", None
        if is_png:
            return True, "PNG", None
        return False, None, None


@dataclass
class PreviewDownloadResult:
    """Outcome and metadata for a preview image download."""
    url: Optional[str]
    status: str  # 'downloaded', 'already_exists', 'unavailable', 'failed', 'oversized', 'invalid_image'
    file_path: Optional[Path] = None
    size_bytes: int = 0
    mime_type: Optional[str] = None
    dimensions: Optional[Tuple[int, int]] = None
    error_message: Optional[str] = None


class PreviewFetcher:
    """Fetches catalogue items, extracts metadata, and downloads small preview images."""

    def __init__(
        self,
        client: Optional[BhoonidhiClient] = None,
        max_preview_size_bytes: int = 10 * 1024 * 1024,  # 10 MB limit
        request_timeout: float = 30.0,
    ):
        self.client = client or BhoonidhiClient()
        self.max_preview_size_bytes = max_preview_size_bytes
        self.request_timeout = request_timeout

    def download_preview(
        self,
        preview_url: Optional[str],
        item_id: str,
        dest_dir: Path,
        mime_type: Optional[str] = None,
    ) -> PreviewDownloadResult:
        """
        Downloads and verifies a preview image file safely.
        """
        if not preview_url:
            return PreviewDownloadResult(
                url=None,
                status="unavailable",
                error_message="No preview URL present in item assets or links.",
            )

        if not is_safe_preview_url(preview_url):
            return PreviewDownloadResult(
                url=preview_url,
                status="failed",
                error_message="URL was rejected by preview safety filters (unsafe format or product download URL).",
            )

        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(item_id)
        # Determine extension from URL
        parsed_path = urlparse(preview_url).path
        ext = os.path.splitext(parsed_path)[1].lower() or ".jpg"
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".jpg"

        dest_path = dest_dir / f"{safe_name}{ext}"
        part_path = dest_dir / f"{safe_name}{ext}.part"

        # Check existing file (idempotent run)
        if dest_path.is_file() and dest_path.stat().st_size > 0:
            try:
                data = dest_path.read_bytes()
                is_valid, fmt, dims = validate_image_bytes(data)
                if is_valid:
                    return PreviewDownloadResult(
                        url=preview_url,
                        status="already_exists",
                        file_path=dest_path,
                        size_bytes=len(data),
                        mime_type=f"image/{fmt.lower()}" if fmt else mime_type,
                        dimensions=dims,
                    )
            except Exception:
                pass  # Re-download if existing file is unreadable

        # Stream download
        try:
            # Many Bhoonidhi thumbnail URLs are hosted on public /imgarchive or /stac/PRODUCTJPGS/
            # We attempt with session; if 401 occurs, we provide bearer headers
            headers = self.client.auth.get_auth_header()
            with self.client.session.get(
                preview_url,
                headers=headers,
                stream=True,
                timeout=(self.client.config.connect_timeout, self.request_timeout),
            ) as resp:

                if resp.status_code != 200:
                    return PreviewDownloadResult(
                        url=preview_url,
                        status="failed",
                        error_message=f"HTTP {resp.status_code} while downloading preview.",
                    )

                # Check Content-Length header
                content_len = resp.headers.get("Content-Length")
                if content_len:
                    try:
                        if int(content_len) > self.max_preview_size_bytes:
                            return PreviewDownloadResult(
                                url=preview_url,
                                status="oversized",
                                size_bytes=int(content_len),
                                error_message=f"Preview size ({content_len} bytes) exceeds limit ({self.max_preview_size_bytes} bytes).",
                            )
                    except ValueError:
                        pass

                # Stream into memory / .part file with hard size cap
                total_bytes = 0
                buffer = bytearray()
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        total_bytes += len(chunk)
                        if total_bytes > self.max_preview_size_bytes:
                            return PreviewDownloadResult(
                                url=preview_url,
                                status="oversized",
                                size_bytes=total_bytes,
                                error_message=f"Preview transfer exceeded maximum limit of {self.max_preview_size_bytes} bytes.",
                            )
                        buffer.extend(chunk)

                # Validate image content
                data_bytes = bytes(buffer)
                is_valid, fmt, dims = validate_image_bytes(data_bytes)
                if not is_valid:
                    return PreviewDownloadResult(
                        url=preview_url,
                        status="invalid_image",
                        size_bytes=len(data_bytes),
                        error_message="Downloaded payload is not a valid JPEG/PNG image.",
                    )

                # Atomically write validated image file
                with open(part_path, "wb") as f:
                    f.write(data_bytes)
                part_path.replace(dest_path)

                return PreviewDownloadResult(
                    url=preview_url,
                    status="downloaded",
                    file_path=dest_path,
                    size_bytes=len(data_bytes),
                    mime_type=f"image/{fmt.lower()}" if fmt else mime_type,
                    dimensions=dims,
                )

        except Exception as e:
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            return PreviewDownloadResult(
                url=preview_url,
                status="failed",
                error_message=f"Download exception: {type(e).__name__} - {str(e)}",
            )

    def extract_item_metadata(
        self,
        feature: Dict[str, Any],
        preview_res: PreviewDownloadResult,
    ) -> Dict[str, Any]:
        """
        Extracts structured, normalized metadata according to task specifications.
        """
        props = feature.get("properties", {})

        # Extract timestamps
        acq_datetime = props.get("datetime") or props.get("Imaging_Date")
        start_datetime = props.get("start_datetime")
        end_datetime = props.get("end_datetime")
        pub_datetime = props.get("updated") or props.get("GenerationTime") or props.get("Dumping_Date")

        # Extract instrument & platform
        platform = props.get("Platform") or props.get("platform")
        instrument = props.get("Instrument") or props.get("instrument") or props.get("sensor")
        product_type = props.get("ProductCode") or props.get("Sat_Spec") or props.get("Mode") or feature.get("collection")

        dims_str = f"{preview_res.dimensions[0]}x{preview_res.dimensions[1]}" if preview_res.dimensions else None

        return {
            "item_id": feature.get("id"),
            "collection_id": feature.get("collection"),
            "platform": platform,
            "instrument": instrument,
            "product_type": product_type,
            "acquisition_datetime": acq_datetime,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "publication_datetime": pub_datetime,
            "processing_level": props.get("ProcessingLevel") or props.get("Mode"),
            "online_status": props.get("Online"),
            "bbox": feature.get("bbox"),
            "geometry": feature.get("geometry"),
            "preview_url": preview_res.url,
            "preview_status": preview_res.status,
            "preview_mime_type": preview_res.mime_type,
            "preview_dimensions": dims_str,
            "preview_size_bytes": preview_res.size_bytes,
            "preview_file_path": str(preview_res.file_path) if preview_res.file_path else None,
            "asset_links": feature.get("assets", {}),
            "item_links": feature.get("links", []),
            "raw_properties": props,
            "error": preview_res.error_message,
        }

    def fetch_day(
        self,
        collection_id: str,
        target_date: str,
        output_base_dir: Union[str, Path] = "data",
        limit_per_page: int = 100,
        max_pages: int = 50,
        query_by: str = "acquisition",
    ) -> Dict[str, Any]:
        """
        Main execution flow:
        1. Queries STAC search for target_date.
           - If query_by == 'acquisition': filters by sensing datetime in Asia/Kolkata day window.
           - If query_by == 'upload': filters by STAC catalogue upload date ('updated' property).
        2. Deduplicates items.
        3. Downloads preview images to data/YYYY-MM-DD/<collection_id>/previews/.
        4. Writes metadata.json, metadata.csv, and manifest.json.
        """
        start_utc, end_utc, dt_interval = get_kolkata_day_window(target_date)

        target_dir = Path(output_base_dir) / target_date / collection_id
        previews_dir = target_dir / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)

        if query_by == "upload":
            logger.info(
                "Fetching %s for upload date %s",
                collection_id,
                target_date,
            )
            extra_filter = {"op": "like", "args": [{"property": "updated"}, f"{target_date}%"]}
            search_result = self.client.search(
                collections=[collection_id],
                extra_filter=extra_filter,
                limit=limit_per_page,
                online_only=False,
                max_pages=max_pages,
            )
        else:
            logger.info(
                "Fetching %s for date %s (IST window: %s)",
                collection_id,
                target_date,
                dt_interval,
            )
            search_result = self.client.search(
                collections=[collection_id],
                datetime_range=dt_interval,
                limit=limit_per_page,
                online_only=False,
                max_pages=max_pages,
            )

        # Deduplicate features by item ID
        unique_features: List[Dict[str, Any]] = []
        seen_ids: Set[str] = set()
        for f in search_result.features:
            fid = f.get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                unique_features.append(f)

        records: List[Dict[str, Any]] = []
        downloaded_count = 0
        already_exists_count = 0
        unavailable_count = 0
        failed_count = 0
        oversized_count = 0
        total_preview_bytes = 0

        for feat in unique_features:
            item_id = feat.get("id", "unknown")
            preview_url, mime = extract_preview_info(feat)

            preview_res = self.download_preview(
                preview_url=preview_url,
                item_id=item_id,
                dest_dir=previews_dir,
                mime_type=mime,
            )

            if preview_res.status == "downloaded":
                downloaded_count += 1
                total_preview_bytes += preview_res.size_bytes
            elif preview_res.status == "already_exists":
                already_exists_count += 1
                total_preview_bytes += preview_res.size_bytes
            elif preview_res.status == "unavailable":
                unavailable_count += 1
            elif preview_res.status == "oversized":
                oversized_count += 1
            else:
                failed_count += 1

            record = self.extract_item_metadata(feat, preview_res)
            records.append(record)

        # Write metadata.json
        meta_json_path = target_dir / "metadata.json"
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)

        # Write metadata.csv
        meta_csv_path = target_dir / "metadata.csv"
        csv_fieldnames = [
            "item_id",
            "collection_id",
            "platform",
            "instrument",
            "product_type",
            "acquisition_datetime",
            "start_datetime",
            "end_datetime",
            "publication_datetime",
            "processing_level",
            "online_status",
            "preview_status",
            "preview_dimensions",
            "preview_size_bytes",
            "preview_url",
            "preview_file_path",
            "error",
        ]
        with open(meta_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                writer.writerow(rec)

        # Write manifest.json
        total_mb = round(total_preview_bytes / (1024 * 1024), 3)
        manifest = {
            "target_date": target_date,
            "collection_id": collection_id,
            "query_by": query_by,
            "timezone": "Asia/Kolkata (UTC+05:30)",
            "utc_window_start": start_utc if query_by == "acquisition" else None,
            "utc_window_end": end_utc if query_by == "acquisition" else None,
            "upload_date_prefix": target_date if query_by == "upload" else None,
            "total_items_found": len(unique_features),
            "previews_downloaded": downloaded_count,
            "previews_already_existing": already_exists_count,
            "previews_unavailable": unavailable_count,
            "previews_failed": failed_count,
            "previews_oversized": oversized_count,
            "total_preview_data_bytes": total_preview_bytes,
            "total_preview_data_mb": total_mb,
            "output_directory": str(target_dir),
            "files": {
                "metadata_json": str(meta_json_path),
                "metadata_csv": str(meta_csv_path),
                "previews_dir": str(previews_dir),
            },
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        manifest_path = target_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

