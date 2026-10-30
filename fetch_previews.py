"""
Bhoonidhi Daily Satellite Data Fetcher — JPEG Previews + Metadata Only.
CLI entrypoint to discover catalogue items for a specific date (Asia/Kolkata window)
and download verified JPEG/PNG browse images without downloading heavy product archives.
"""

import argparse
import json
import sys
from pathlib import Path

from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.preview_fetcher import PreviewFetcher, get_kolkata_day_window


def main():
    parser = argparse.ArgumentParser(
        description="Fetch one day of Bhoonidhi satellite browse images and STAC metadata."
    )
    parser.add_argument(
        "--collection",
        default="Sentinel-1A_SAR-IW_GRD",
        help="Bhoonidhi STAC collection ID (default: Sentinel-1A_SAR-IW_GRD)",
    )
    parser.add_argument(
        "--date",
        default="2026-10-29",
        help="Target date YYYY-MM-DD in Asia/Kolkata local time (default: 2026-10-29)",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output base directory (default: data)",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=10.0,
        help="Maximum allowed preview image size in MB (default: 10.0)",
    )
    parser.add_argument(
        "--fallback",
        default="EOS-04_SAR-FRS2_L2A",
        help="Fallback collection if primary returns 0 items (default: EOS-04_SAR-FRS2_L2A)",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not automatically query fallback collection if primary has 0 items",
    )

    args = parser.parse_args()

    start_utc, end_utc, dt_interval = get_kolkata_day_window(args.date)

    print("=" * 70)
    print("Bhoonidhi Satellite Preview & Metadata Harvester")
    print("=" * 70)
    print(f"Target Date       : {args.date} (Asia/Kolkata)")
    print(f"UTC Search Window : {dt_interval}")
    print(f"Primary Collection: {args.collection}")
    print(f"Output Directory  : {Path(args.output_dir).resolve()}")
    print("=" * 70)

    client = BhoonidhiClient()
    fetcher = PreviewFetcher(
        client=client,
        max_preview_size_bytes=int(args.max_size_mb * 1024 * 1024),
    )

    # 1. Run primary collection
    print(f"\n[1] Querying catalogue for: {args.collection}...")
    manifest = fetcher.fetch_day(
        collection_id=args.collection,
        target_date=args.date,
        output_base_dir=args.output_dir,
    )

    print(f"    Items found          : {manifest['total_items_found']}")
    print(f"    Previews downloaded  : {manifest['previews_downloaded']}")
    print(f"    Previews existing    : {manifest['previews_already_existing']}")
    print(f"    Previews unavailable : {manifest['previews_unavailable']}")
    print(f"    Previews failed      : {manifest['previews_failed']}")
    print(f"    Total data (MB)      : {manifest['total_preview_data_mb']}")
    print(f"    Manifest saved at    : {manifest['output_directory']}\\manifest.json")

    # 2. Check if primary had 0 items and fallback requested
    if manifest["total_items_found"] == 0 and not args.no_fallback and args.fallback:
        print(f"\n[NOTE] Primary collection '{args.collection}' returned 0 items for {args.date}.")
        print(f"       Investigating active collections with demonstrable previews...")
        print(f"       Querying fallback collection: {args.fallback}...")

        fb_manifest = fetcher.fetch_day(
            collection_id=args.fallback,
            target_date=args.date,
            output_base_dir=args.output_dir,
        )

        print(f"    Items found          : {fb_manifest['total_items_found']}")
        print(f"    Previews downloaded  : {fb_manifest['previews_downloaded']}")
        print(f"    Previews existing    : {fb_manifest['previews_already_existing']}")
        print(f"    Previews unavailable : {fb_manifest['previews_unavailable']}")
        print(f"    Previews failed      : {fb_manifest['previews_failed']}")
        print(f"    Total data (MB)      : {fb_manifest['total_preview_data_mb']}")
        print(f"    Manifest saved at    : {fb_manifest['output_directory']}\\manifest.json")

    print("\n" + "=" * 70)
    print("Execution complete. All artifacts saved safely.")
    print("=" * 70)


if __name__ == "__main__":
    main()

