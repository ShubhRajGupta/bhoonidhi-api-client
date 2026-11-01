"""
Bhoonidhi Ground Station QC Metadata Module.
Extracts and formats operational satellite dump quality-control metadata
from STAC properties across SAR (EOS-04) and Optical (ResourceSat-2/2A) platforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _format_lat_lon(lat: Optional[float], lon: Optional[float]) -> str:
    """Formats latitude and longitude into human-readable coordinate string."""
    if lat is None or lon is None:
        return "N/A"
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        lat_dir = "N" if lat_f >= 0 else "S"
        lon_dir = "E" if lon_f >= 0 else "W"
        return f"{abs(lat_f):.4f}° {lat_dir}, {abs(lon_f):.4f}° {lon_dir}"
    except (ValueError, TypeError):
        return f"{lat}, {lon}"


@dataclass
class QCMetadata:
    """Holds 14+ standardized ground station QC dump parameters for each satellite scene."""
    item_id: str
    collection_id: str
    platform: str
    instrument: str
    cycle_number: str
    date_of_pass: str
    date_of_dump: str
    dumping_orbit_number: str
    observation_id: str
    track_number: str
    frame_number: str
    mode_id: str
    generation_datetime: str
    data_take_id: str
    session_number: str
    scene_centre_lat_lon: str
    input_resolution: str
    rfi_likelihood: str
    online_status: str
    preview_status: str
    preview_file_path: Optional[str] = None
    bbox: Optional[List[float]] = None
    raw_properties: Dict[str, Any] = field(default_factory=dict)

    def to_display_pairs(self) -> List[Tuple[str, str]]:
        """Returns ordered list of (Field Name, Value) tuples for table display."""
        return [
            ("CYCLE NUMBER", self.cycle_number),
            ("DATE OF PASS", self.date_of_pass),
            ("DATE OF DUMP", self.date_of_dump),
            ("DUMPING ORBIT NUMBER", self.dumping_orbit_number),
            ("OBSERVATION ID", self.observation_id),
            ("TRACK NUMBER", self.track_number),
            ("FRAME NUMBER", self.frame_number),
            ("MODE ID", self.mode_id),
            ("GENERATION DATE/TIME", self.generation_datetime),
            ("DATA TAKE ID", self.data_take_id),
            ("SESSION NUMBER", self.session_number),
            ("SCENE CENTRE LAT/LONG", self.scene_centre_lat_lon),
            ("INPUT RESOLUTION", self.input_resolution),
            ("RFI LIKELIHOOD", self.rfi_likelihood),
        ]


def extract_qc_metadata(item: Dict[str, Any]) -> QCMetadata:
    """
    Extracts structured QC parameters from a STAC item record
    (either raw STAC Feature or PreviewFetcher record).
    """
    # Accommodate both raw STAC item or PreviewFetcher record dictionary
    raw = item.get("raw_properties") or item.get("properties") or {}
    item_id = item.get("item_id") or item.get("id") or "UNKNOWN"
    collection_id = item.get("collection_id") or item.get("collection") or "UNKNOWN"

    # Platform & Instrument
    platform = (
        raw.get("Platform")
        or raw.get("platform")
        or item.get("platform")
        or collection_id.split("_")[0]
    )
    instrument = (
        raw.get("Instrument")
        or raw.get("instrument")
        or raw.get("sensor")
        or item.get("instrument")
        or "N/A"
    )

    # 1. Cycle Number
    cycle_number = str(raw.get("CycleNumber") or raw.get("cycle") or "N/A")

    # 2. Date of Pass (Imaging / Acquisition Date)
    date_of_pass = (
        raw.get("Imaging_Date")
        or raw.get("datetime")
        or item.get("acquisition_datetime")
        or "N/A"
    )

    # 3. Date of Dump (Downlink Date)
    date_of_dump = (
        raw.get("Dumping_Date")
        or raw.get("updated")
        or item.get("publication_datetime")
        or "N/A"
    )

    # 4. Dumping Orbit Number
    dumping_orbit_number = str(
        raw.get("Dumping_Orbit")
        or raw.get("dumping_orbit")
        or raw.get("Imaging_Orbit")
        or "N/A"
    )

    # 5. Observation ID
    observation_id = (
        raw.get("ID")
        or raw.get("Scene_Identifier")
        or item_id
    )

    # 6. Track Number (Strip ID or Path)
    track_number = str(
        raw.get("StripId")
        or raw.get("Path")
        or raw.get("track")
        or raw.get("Imaging_Orbit")
        or "N/A"
    )

    # 7. Frame Number (Scene Number or Row)
    frame_number = str(
        raw.get("SceneNumber")
        or raw.get("Row")
        or raw.get("frame")
        or "N/A"
    )

    # 8. Mode ID
    mode_id = (
        raw.get("Mode")
        or raw.get("ProductCode")
        or raw.get("Sat_Spec")
        or item.get("product_type")
        or "N/A"
    )

    # 9. Generation Date/Time
    generation_datetime = (
        raw.get("GenerationTime")
        or raw.get("datetime")
        or "N/A"
    )

    # 10. Data Take ID
    data_take_id = (
        raw.get("Scene_Identifier")
        or raw.get("StripId")
        or item_id
    )

    # 11. Session Number (Ground station ID or subscene)
    station_id = raw.get("StationId")
    subscene_id = raw.get("Subscene_ID")
    if station_id and subscene_id:
        session_number = f"{station_id} / {subscene_id}"
    elif station_id:
        session_number = str(station_id)
    elif subscene_id:
        session_number = f"Subscene {subscene_id}"
    else:
        session_number = "N/A"

    # 12. Scene Centre Lat/Long
    lat = raw.get("SceneCenterLat")
    lon = raw.get("SceneCenterLon")
    if lat is not None and lon is not None:
        scene_centre_lat_lon = _format_lat_lon(lat, lon)
    elif "CentreLatLon" in raw and isinstance(raw["CentreLatLon"], (list, tuple)) and len(raw["CentreLatLon"]) >= 2:
        scene_centre_lat_lon = _format_lat_lon(raw["CentreLatLon"][0], raw["CentreLatLon"][1])
    else:
        bbox = item.get("bbox")
        if bbox and len(bbox) == 4:
            mid_lon = (bbox[0] + bbox[2]) / 2.0
            mid_lat = (bbox[1] + bbox[3]) / 2.0
            scene_centre_lat_lon = _format_lat_lon(mid_lat, mid_lon)
        else:
            scene_centre_lat_lon = "N/A"

    # 13. Input Resolution (Across / Along)
    res_across = raw.get("InputResolutionAcross")
    res_along = raw.get("InputResolutionAlong")
    if res_across is not None and res_along is not None:
        input_resolution = f"{res_across}m (Across) x {res_along}m (Along)"
    elif "Resolution" in raw:
        input_resolution = f"{raw['Resolution']}m"
    elif "AWIF" in instrument or "AWIFS" in collection_id:
        input_resolution = "56.0m (Nominal)"
    elif "LISS3" in collection_id:
        input_resolution = "23.5m (Nominal)"
    elif "LISS4" in collection_id:
        input_resolution = "5.8m (Nominal)"
    elif "FRS" in mode_id:
        input_resolution = "3.0m (Nominal)"
    elif "MRS" in mode_id:
        input_resolution = "25.0m (Nominal)"
    elif "CRS" in mode_id:
        input_resolution = "50.0m (Nominal)"
    else:
        input_resolution = "Standard"

    # 14. RFI Likelihood
    rfi_likelihood = str(
        raw.get("RFI_Likelihood")
        or raw.get("rfi")
        or "Not Reported (Nominal)"
    )

    # Statuses & File Paths
    online_status = str(raw.get("Online") or item.get("online_status") or "Unknown")
    preview_status = str(item.get("preview_status") or ("downloaded" if item.get("preview_file_path") else "unavailable"))
    preview_file_path = item.get("preview_file_path")

    return QCMetadata(
        item_id=item_id,
        collection_id=collection_id,
        platform=platform,
        instrument=instrument,
        cycle_number=cycle_number,
        date_of_pass=str(date_of_pass),
        date_of_dump=str(date_of_dump),
        dumping_orbit_number=dumping_orbit_number,
        observation_id=str(observation_id),
        track_number=track_number,
        frame_number=frame_number,
        mode_id=mode_id,
        generation_datetime=str(generation_datetime),
        data_take_id=str(data_take_id),
        session_number=session_number,
        scene_centre_lat_lon=scene_centre_lat_lon,
        input_resolution=input_resolution,
        rfi_likelihood=rfi_likelihood,
        online_status=online_status,
        preview_status=preview_status,
        preview_file_path=preview_file_path,
        bbox=item.get("bbox"),
        raw_properties=raw,
    )
