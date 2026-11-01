"""
Root-level entrypoint for Bhoonidhi Daily Satellite Browse Harvester & QC Report Generator.
Usage:
    python main.py --date 2026-10-29 --collection Sentinel-1A_SAR-IW_GRD
    python main.py --yesterday --collection EOS-04_SAR-FRS2_L2A
    python main.py --date 2026-10-29 --by-upload --all-scenes
"""

from bhoonidhi.fetch_previews import main

if __name__ == "__main__":
    main()

