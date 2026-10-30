"""
Bhoonidhi API Package.
"""

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.download import BhoonidhiDownloader, DownloadResult
from bhoonidhi.exceptions import (
    BhoonidhiAuthError,
    BhoonidhiConcurrencyError,
    BhoonidhiError,
    BhoonidhiNotFoundError,
    BhoonidhiRateLimitError,
    BhoonidhiServerError,
    BhoonidhiSessionLimitError,
    DownloadIntegrityError,
    ProductNotOnlineError,
    STACSearchError,
)
from bhoonidhi.product_mapping import (
    ResolutionResult,
    resolve_product_types,
)
from bhoonidhi.search import BhoonidhiSearch, STACSearchResult

__all__ = [
    "BhoonidhiAuth",
    "BhoonidhiClient",
    "BhoonidhiConfig",
    "BhoonidhiCredentials",
    "BhoonidhiDownloader",
    "BhoonidhiSearch",
    "DownloadResult",
    "ResolutionResult",
    "STACSearchResult",
    "resolve_product_types",
    "BhoonidhiError",
    "BhoonidhiAuthError",
    "BhoonidhiSessionLimitError",
    "BhoonidhiNotFoundError",
    "BhoonidhiConcurrencyError",
    "BhoonidhiRateLimitError",
    "BhoonidhiServerError",
    "ProductNotOnlineError",
    "STACSearchError",
    "DownloadIntegrityError",
]

