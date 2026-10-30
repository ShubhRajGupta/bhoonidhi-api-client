"""
Configuration for Bhoonidhi API client.
Enforces API constraints including concurrency limits (<= 5) and timeouts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BhoonidhiConfig:
    """Holds configuration parameters for Bhoonidhi API interactions."""
    base_url: str = "https://bhoonidhi-api.nrsc.gov.in"
    download_dir: Path = Path("./downloads")
    max_concurrent_downloads: int = 2
    request_timeout: float = 60.0
    connect_timeout: float = 10.0
    max_retries: int = 3
    retry_backoff_factor: float = 1.5
    max_pagination_pages: int = 50
    search_rate_delay: float = 0.35  # Max 3 requests/sec per IP

    def __post_init__(self):
        # Enforce Bhoonidhi hard ceiling of 5 concurrent downloads per user/IP
        if self.max_concurrent_downloads > 5:
            self.max_concurrent_downloads = 5
        elif self.max_concurrent_downloads < 1:
            self.max_concurrent_downloads = 1

        self.download_dir = Path(self.download_dir)
        self.base_url = self.base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> BhoonidhiConfig:
        """Construct configuration from environment variables."""
        base_url = os.environ.get("BHOONIDHI_BASE_URL", "https://bhoonidhi-api.nrsc.gov.in")
        download_dir = Path(os.environ.get("BHOONIDHI_DOWNLOAD_DIR", "./downloads"))

        max_concurrent = 2
        if "BHOONIDHI_MAX_CONCURRENT_DOWNLOADS" in os.environ:
            try:
                max_concurrent = int(os.environ["BHOONIDHI_MAX_CONCURRENT_DOWNLOADS"])
            except ValueError:
                pass

        timeout = 60.0
        if "BHOONIDHI_REQUEST_TIMEOUT" in os.environ:
            try:
                timeout = float(os.environ["BHOONIDHI_REQUEST_TIMEOUT"])
            except ValueError:
                pass

        return cls(
            base_url=base_url,
            download_dir=download_dir,
            max_concurrent_downloads=max_concurrent,
            request_timeout=timeout,
        )

