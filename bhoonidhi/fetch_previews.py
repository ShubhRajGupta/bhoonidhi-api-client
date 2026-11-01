"""
Bhoonidhi Daily Satellite Data Fetcher & PowerPoint Quality Report Pipeline.
CLI entrypoint to discover catalogue items for a specific date, download verified
JPEG/PNG browse images without downloading heavy product archives, and automatically
generate professional 16:9 widescreen PowerPoint quality-control reports.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Support running directly as script or as module
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.preview_fetcher import PreviewFetcher, get_kolkata_day_window
from bhoonidhi.report_generator import SatelliteReportGenerator


ACTIVE_ISRO_COLLECTIONS = [
    "EOS-04_SAR-FRS2_L2A",
    "EOS-04_SAR-FRS1_L2A",
    "EOS-04_SAR-MRS_L2B",
    "ResourceSat-2_AWIFS_L2",
    "ResourceSat-2_LISS3_L2",
    "ResourceSat-2A_AWIFS_L2",
    "ResourceSat-2A_LISS3_L2",
]


def get_yesterday_kolkata() -> str:
    """Returns yesterday's date formatted as YYYY-MM-DD in Asia/Kolkata timezone (UTC+05:30)."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(ist)
    yesterday = now_ist - datetime.timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def build_parser() -> argparse.ArgumentParser:
    """Builds and returns the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Daily Satellite Browse Image Harvester & PowerPoint Quality Report Generator."
    )
    parser.add_argument(
        "--collection",
        default="Sentinel-1A_SAR-IW_GRD",
        help="Bhoonidhi STAC collection ID, comma-separated list, or 'ALL' (default: Sentinel-1A_SAR-IW_GRD)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Target date YYYY-MM-DD in Asia/Kolkata local time (default: 2026-10-29 or yesterday)",
    )
    parser.add_argument(
        "--yesterday",
        action="store_true",
        help="Automatically use yesterday's calendar date in Asia/Kolkata local time",
    )
    parser.add_argument(
        "--by-upload",
        action="store_true",
        help="Query by catalogue publication/upload date ('updated') instead of satellite sensing time",
    )
    parser.add_argument(
        "--query-by",
        choices=["acquisition", "upload"],
        default=None,
        help="Query filter mode: 'acquisition' (sensing datetime) or 'upload' (catalogued date)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Harvest all active ISRO satellite collections that have data for the target date",
    )
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Output base directory for downloaded images and raw STAC metadata (default: data)",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Output directory for generated PowerPoint presentations and audit logs (default: reports)",
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
    parser.add_argument(
        "--max-slides",
        type=int,
        default=30,
        help="Maximum product slides to include in presentation deck (default: 30)",
    )
    parser.add_argument(
        "--all-scenes",
        action="store_true",
        help="Include all harvested scenes in presentation deck without capping at 30 slides",
    )
    parser.add_argument(
        "--no-pptx",
        action="store_true",
        help="Skip PowerPoint report generation (harvest previews and metadata only)",
    )
    return parser


def run_pipeline(args) -> Dict[str, Any]:
    """
    Executes the end-to-end harvest and PowerPoint reporting pipeline.
    """
    # 1. Resolve Target Date
    if args.yesterday:
        target_date = get_yesterday_kolkata()
    elif args.date:
        target_date = args.date
    else:
        target_date = "2026-10-29"  # Default baseline date

    # 2. Determine Query Mode
    query_mode = "upload" if args.by_upload else (args.query_by or "acquisition")

    # 3. Determine Slide Cap
    max_slides = None if args.all_scenes else args.max_slides

    # 4. Resolve Target Collections
    if args.all or args.collection.strip().upper() == "ALL":
        target_collections = list(ACTIVE_ISRO_COLLECTIONS)
    elif "," in args.collection:
        target_collections = [c.strip() for c in args.collection.split(",") if c.strip()]
    else:
        target_collections = [args.collection.strip()]

    start_utc, end_utc, dt_interval = get_kolkata_day_window(target_date)

    # Setup directories
    reports_base = Path(args.reports_dir) / target_date
    reports_base.mkdir(parents=True, exist_ok=True)
    log_file_path = reports_base / "execution_log.txt"

    log_lines: List[str] = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("BHOONIDHI SATELLITE BROWSE HARVESTER & QC REPORT GENERATOR")
    log("=" * 80)
    log(f"Target Date       : {target_date} (Asia/Kolkata)")
    log(f"Query Mode        : {query_mode.upper()} ({'Catalogue Upload Date' if query_mode == 'upload' else 'Sensing Datetime'})")
    if query_mode == "acquisition":
        log(f"UTC Search Window : {dt_interval} (00:00:00-23:59:59 IST)")
    log(f"Collections ({len(target_collections)})  : {', '.join(target_collections)}")
    log(f"Max Slide Cap     : {'Unlimited (--all-scenes)' if max_slides is None else f'{max_slides} slides'}")
    log(f"Data Directory    : {Path(args.output_dir).resolve()}")
    log(f"Reports Directory : {reports_base.resolve()}")
    log("=" * 80)

    client = BhoonidhiClient()
    fetcher = PreviewFetcher(
        client=client,
        max_preview_size_bytes=int(args.max_size_mb * 1024 * 1024),
    )

    manifests: List[Dict[str, Any]] = []
    generated_reports: List[Path] = []
    summary_data: Dict[str, Any] = {
        "target_date": target_date,
        "query_mode": query_mode,
        "utc_window": dt_interval if query_mode == "acquisition" else None,
        "collections": {},
        "generated_reports": [],
        "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    for idx, col in enumerate(target_collections, 1):
        log(f"\n[{idx}/{len(target_collections)}] Processing collection: {col}...")
        api_limitations = ""
        try:
            manifest = fetcher.fetch_day(
                collection_id=col,
                target_date=target_date,
                output_base_dir=args.output_dir,
                query_by=query_mode,
            )
            manifests.append(manifest)

            items_found = manifest["total_items_found"]
            downloaded = manifest["previews_downloaded"]
            existing = manifest["previews_already_existing"]
            data_mb = manifest["total_preview_data_mb"]

            log(f"    Catalogue items found : {items_found}")
            log(f"    Previews downloaded   : {downloaded}")
            log(f"    Previews cached/reuse : {existing}")
            log(f"    Previews unavailable  : {manifest['previews_unavailable']}")
            log(f"    Downloads failed      : {manifest['previews_failed']}")
            log(f"    Preview volume (MB)   : {data_mb}")

            # Load harvested items metadata
            meta_path = Path(manifest["files"]["metadata_json"])
            items = []
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    items = json.load(f)

            # Check for Sentinel-1A mirror cutoff limitation
            if "Sentinel-1A" in col and items_found == 0:
                api_limitations = (
                    "• NOTICE: Bhoonidhi Sentinel-1A mirror extent terminates at 2026-06-30T00:00:00Z.\n"
                    f"• Target date {target_date} is beyond the indexed archive range (0 items catalogued).\n"
                    "• For historical Sentinel-1A imagery, select dates prior to 2026-06-30 (e.g. 2026-06-29)."
                )
                log(f"    [LIMITATION] {api_limitations.replace(chr(10), ' ')}")

            # Generate PowerPoint Report if enabled
            if not args.no_pptx:
                pptx_filename = f"daily_satellite_report_{col}.pptx"
                pptx_path = reports_base / pptx_filename
                log(f"    Compiling PowerPoint quality report: {pptx_filename}...")

                reporter = SatelliteReportGenerator(
                    collection_id=col,
                    target_date=target_date,
                    manifest=manifest,
                    max_slides=max_slides,
                )
                report_file = reporter.generate_report(
                    items=items,
                    output_file_path=pptx_path,
                    api_limitations=api_limitations,
                )
                generated_reports.append(report_file)
                log(f"    [OK] Saved presentation: {report_file} ({report_file.stat().st_size:,} bytes)")

            summary_data["collections"][col] = {
                "items_found": items_found,
                "previews_downloaded": downloaded,
                "previews_existing": existing,
                "previews_unavailable": manifest["previews_unavailable"],
                "data_volume_mb": data_mb,
                "api_limitations": api_limitations or None,
            }

            # Check fallback if single collection requested and returned 0 items
            if (
                len(target_collections) == 1
                and items_found == 0
                and not args.no_fallback
                and args.fallback
                and col != args.fallback
            ):
                log(f"\n[AUTO-FALLBACK] Primary collection '{col}' returned 0 items for {target_date}.")
                log(f"                Auto-switching to verified active collection: {args.fallback}...")

                fb_manifest = fetcher.fetch_day(
                    collection_id=args.fallback,
                    target_date=target_date,
                    output_base_dir=args.output_dir,
                    query_by=query_mode,
                )
                manifests.append(fb_manifest)

                fb_items_found = fb_manifest["total_items_found"]
                fb_downloaded = fb_manifest["previews_downloaded"]
                fb_existing = fb_manifest["previews_already_existing"]
                fb_data_mb = fb_manifest["total_preview_data_mb"]

                log(f"    Fallback items found  : {fb_items_found}")
                log(f"    Previews downloaded   : {fb_downloaded}")
                log(f"    Previews cached/reuse : {fb_existing}")
                log(f"    Preview volume (MB)   : {fb_data_mb}")

                fb_meta_path = Path(fb_manifest["files"]["metadata_json"])
                fb_items = []
                if fb_meta_path.exists():
                    with open(fb_meta_path, "r", encoding="utf-8") as f:
                        fb_items = json.load(f)

                if not args.no_pptx:
                    fb_pptx_filename = f"daily_satellite_report_{args.fallback}.pptx"
                    fb_pptx_path = reports_base / fb_pptx_filename
                    log(f"    Compiling Fallback PowerPoint report: {fb_pptx_filename}...")

                    fb_reporter = SatelliteReportGenerator(
                        collection_id=args.fallback,
                        target_date=target_date,
                        manifest=fb_manifest,
                        max_slides=max_slides,
                    )
                    fb_limitation_note = (
                        f"• Generated via automatic fallback from {col} (0 items found for {target_date}).\n"
                        f"• {args.fallback} demonstrates live active ISRO satellite telemetry and browse imagery."
                    )
                    fb_report_file = fb_reporter.generate_report(
                        items=fb_items,
                        output_file_path=fb_pptx_path,
                        api_limitations=fb_limitation_note,
                    )
                    generated_reports.append(fb_report_file)
                    log(f"    [OK] Saved fallback presentation: {fb_report_file} ({fb_report_file.stat().st_size:,} bytes)")

                summary_data["collections"][args.fallback] = {
                    "is_fallback": True,
                    "items_found": fb_items_found,
                    "previews_downloaded": fb_downloaded,
                    "previews_existing": fb_existing,
                    "data_volume_mb": fb_data_mb,
                }

        except Exception as err:
            log(f"    [ERROR] Failed processing collection {col}: {err}")
            summary_data["collections"][col] = {"error": str(err)}

    # Save summary and execution log
    summary_data["generated_reports"] = [str(p) for p in generated_reports]
    summary_path = reports_base / "collection_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    total_bytes = sum(m.get("total_preview_data_bytes", 0) for m in manifests)
    total_found = sum(m.get("total_items_found", 0) for m in manifests)
    total_dl = sum(m.get("previews_downloaded", 0) for m in manifests)
    total_exist = sum(m.get("previews_already_existing", 0) for m in manifests)

    log("\n" + "=" * 80)
    log("PIPELINE EXECUTION SUMMARY")
    log("=" * 80)
    log(f"Total Collections Processed : {len(summary_data['collections'])}")
    log(f"Total Catalogue Items Found : {total_found}")
    log(f"Total Previews Downloaded   : {total_dl}")
    log(f"Total Previews Reused       : {total_exist}")
    log(f"Total Storage Consumed      : {round(total_bytes / (1024 * 1024), 2)} MB")
    log(f"PowerPoint Reports Built    : {len(generated_reports)}")
    for r in generated_reports:
        log(f"  • {r}")
    log(f"Collection Summary JSON     : {summary_path}")
    log(f"Execution Log File          : {log_file_path}")
    log("=" * 80)

    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    return summary_data


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
