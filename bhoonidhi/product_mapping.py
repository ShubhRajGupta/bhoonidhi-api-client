"""
Bhoonidhi Product and Collection Mapping.
Resolves user-friendly satellite, sensor, and product names to verified Bhoonidhi STAC collection IDs.
Provides deterministic resolution, alias normalization, and structured diagnostics for unresolved terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Union


# Verified Bhoonidhi collection catalog with canonical IDs and descriptions
KNOWN_COLLECTIONS: Dict[str, Dict[str, str]] = {
    "ResourceSat-2_AWIFS_L2": {
        "platform": "ResourceSat-2",
        "sensor": "AWIFS",
        "level": "L2",
        "description": "ResourceSat-2 Advanced Wide Field Sensor Level-2 Standard Product",
    },
    "ResourceSat-2_LISS3_L2": {
        "platform": "ResourceSat-2",
        "sensor": "LISS-3",
        "level": "L2",
        "description": "ResourceSat-2 Linear Imaging Self-Scanning Sensor-3 Level-2 Product",
    },
    "ResourceSat-2_LISS4_L2": {
        "platform": "ResourceSat-2",
        "sensor": "LISS-4",
        "level": "L2",
        "description": "ResourceSat-2 Linear Imaging Self-Scanning Sensor-4 Level-2 Product",
    },
    "EOS-04_SAR-MRS_L2A": {
        "platform": "EOS-04",
        "sensor": "SAR-MRS",
        "level": "L2A",
        "description": "EOS-04 (RISAT-1A) Synthetic Aperture Radar Medium Resolution ScanSAR Level-2A",
    },
    "EOS-06_OCM-LAC_L1C": {
        "platform": "EOS-06",
        "sensor": "OCM-LAC",
        "level": "L1C",
        "description": "EOS-06 (Oceansat-3) Ocean Colour Monitor Local Area Coverage Level-1C",
    },
    "Sentinel-1A_SAR-IW_GRD": {
        "platform": "Sentinel-1A",
        "sensor": "SAR-IW",
        "level": "GRD",
        "description": "Sentinel-1A SAR Interferometric Wide Swath Ground Range Detected",
    },
    "CartoSat-1_PAN_CartoDEM_30m": {
        "platform": "CartoSat-1",
        "sensor": "PAN",
        "level": "CartoDEM_30m",
        "description": "CartoSat-1 Panchromatic CartoDEM 30m Digital Elevation Model",
    },
    "NISAR_SSAR_GSLC": {
        "platform": "NISAR",
        "sensor": "SSAR",
        "level": "GSLC",
        "description": "NASA-ISRO SAR Geocoded Single Look Complex Product",
    },
}

# Normalization alias mapping: normalized term -> canonical collection ID
ALIAS_MAP: Dict[str, str] = {
    # AWIFS
    "awifs": "ResourceSat-2_AWIFS_L2",
    "awifsl2": "ResourceSat-2_AWIFS_L2",
    "resourcesat2awifs": "ResourceSat-2_AWIFS_L2",
    "resourcesat2awifsl2": "ResourceSat-2_AWIFS_L2",
    "rs2awifs": "ResourceSat-2_AWIFS_L2",
    # LISS-3
    "liss3": "ResourceSat-2_LISS3_L2",
    "liss3l2": "ResourceSat-2_LISS3_L2",
    "resourcesat2liss3": "ResourceSat-2_LISS3_L2",
    "rs2liss3": "ResourceSat-2_LISS3_L2",
    # LISS-4
    "liss4": "ResourceSat-2_LISS4_L2",
    "liss4l2": "ResourceSat-2_LISS4_L2",
    "resourcesat2liss4": "ResourceSat-2_LISS4_L2",
    "rs2liss4": "ResourceSat-2_LISS4_L2",
    # EOS-04 / RISAT-1A
    "eos04": "EOS-04_SAR-MRS_L2A",
    "eos4": "EOS-04_SAR-MRS_L2A",
    "eos04sar": "EOS-04_SAR-MRS_L2A",
    "eos04sarmrs": "EOS-04_SAR-MRS_L2A",
    "eos04sarmrsl2a": "EOS-04_SAR-MRS_L2A",
    "risat1a": "EOS-04_SAR-MRS_L2A",
    # EOS-06 / Oceansat-3
    "eos06": "EOS-06_OCM-LAC_L1C",
    "eos6": "EOS-06_OCM-LAC_L1C",
    "eos06ocm": "EOS-06_OCM-LAC_L1C",
    "eos06ocmlacl1c": "EOS-06_OCM-LAC_L1C",
    "ocm": "EOS-06_OCM-LAC_L1C",
    "ocmlac": "EOS-06_OCM-LAC_L1C",
    "oceansat3": "EOS-06_OCM-LAC_L1C",
    # Sentinel-1A
    "sentinel1a": "Sentinel-1A_SAR-IW_GRD",
    "sentinel1": "Sentinel-1A_SAR-IW_GRD",
    "s1a": "Sentinel-1A_SAR-IW_GRD",
    "s1agrd": "Sentinel-1A_SAR-IW_GRD",
    "sentinel1asariwgrd": "Sentinel-1A_SAR-IW_GRD",
    # CartoSat-1 / CartoDEM
    "cartosat1": "CartoSat-1_PAN_CartoDEM_30m",
    "cartosat": "CartoSat-1_PAN_CartoDEM_30m",
    "cartodem": "CartoSat-1_PAN_CartoDEM_30m",
    "cartodem30m": "CartoSat-1_PAN_CartoDEM_30m",
    "cartosat1pancartodem30m": "CartoSat-1_PAN_CartoDEM_30m",
    # NISAR
    "nisar": "NISAR_SSAR_GSLC",
    "nisargslc": "NISAR_SSAR_GSLC",
    "nisarssargslc": "NISAR_SSAR_GSLC",
}


def normalize_term(term: str) -> str:
    """Normalize input term by lowercasing and stripping non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", term.lower().strip())


@dataclass
class ResolutionResult:
    """Structured outcome of collection / product type resolution."""
    resolved: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    mapping: Dict[str, str] = field(default_factory=dict)
    suggestions: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def has_unresolved(self) -> bool:
        return len(self.unresolved) > 0


def resolve_product_types(
    inputs: Union[str, Iterable[str]],
    available_collections: Optional[Iterable[str]] = None,
) -> ResolutionResult:
    """
    Resolves product labels, sensor names, or partial strings into exact Bhoonidhi STAC collection IDs.

    Args:
        inputs: A single product string or an iterable of strings.
        available_collections: Optional iterable of collection IDs discovered live from /data/collections.

    Returns:
        ResolutionResult containing resolved collection IDs, unresolved inputs, mapping, and suggestions.
    """
    if isinstance(inputs, str):
        raw_terms = [inputs]
    elif isinstance(inputs, Iterable):
        raw_terms = list(inputs)
    else:
        raise TypeError(f"inputs must be a str or Iterable[str], got {type(inputs).__name__}")

    # Build catalog of valid canonical IDs
    known_ids: Set[str] = set(KNOWN_COLLECTIONS.keys())
    if available_collections:
        known_ids.update(available_collections)

    # Normalize canonical IDs for exact normalized lookup
    canonical_normalized: Dict[str, str] = {
        normalize_term(cid): cid for cid in known_ids
    }

    resolved_order: List[str] = []
    seen_resolved: Set[str] = set()
    unresolved: List[str] = []
    mapping: Dict[str, str] = {}
    suggestions: Dict[str, List[str]] = {}

    for term in raw_terms:
        if not isinstance(term, str):
            unresolved.append(str(term))
            continue

        clean_term = term.strip()
        if not clean_term:
            continue

        # 1. Exact match against known collection IDs (case-insensitive)
        exact_match = None
        for cid in known_ids:
            if clean_term.lower() == cid.lower():
                exact_match = cid
                break

        if exact_match:
            mapping[clean_term] = exact_match
            if exact_match not in seen_resolved:
                seen_resolved.add(exact_match)
                resolved_order.append(exact_match)
            continue

        # 2. Normalized match against canonical names
        norm = normalize_term(clean_term)
        if norm in canonical_normalized:
            target_id = canonical_normalized[norm]
            mapping[clean_term] = target_id
            if target_id not in seen_resolved:
                seen_resolved.add(target_id)
                resolved_order.append(target_id)
            continue

        # 3. Known alias lookup
        if norm in ALIAS_MAP:
            target_id = ALIAS_MAP[norm]
            mapping[clean_term] = target_id
            if target_id not in seen_resolved:
                seen_resolved.add(target_id)
                resolved_order.append(target_id)
            continue

        # 4. Unresolved term - find candidate suggestions based on substring or token presence
        candidates = []
        tokens = set(re.findall(r"[a-z0-9]+", clean_term.lower()))
        for cid in sorted(known_ids):
            norm_cid = normalize_term(cid)
            if norm in norm_cid or norm_cid in norm:
                candidates.append(cid)
            elif any(tok in norm_cid for tok in tokens if len(tok) >= 4):
                candidates.append(cid)

        unresolved.append(clean_term)
        if candidates:
            suggestions[clean_term] = sorted(list(dict.fromkeys(candidates)))

    return ResolutionResult(
        resolved=resolved_order,
        unresolved=unresolved,
        mapping=mapping,
        suggestions=suggestions,
    )


# Active ISRO and Partner Satellite Collections Groupings
SATELLITE_COLLECTIONS: Dict[str, List[str]] = {
    "EOS-04": [
        "EOS-04_SAR-FRS1_L2A",
        "EOS-04_SAR-FRS2_L2A",
        "EOS-04_SAR-MRS_L2B",
        "EOS-04_SAR-CRS_L2B",
    ],
    "ResourceSat-2": [
        "ResourceSat-2_AWIFS_L2",
        "ResourceSat-2_LISS3_L2",
        "ResourceSat-2_LISS4-MX70_L2",
    ],
    "ResourceSat-2A": [
        "ResourceSat-2A_AWIFS_L2",
        "ResourceSat-2A_LISS3_L2",
        "ResourceSat-2A_LISS4-MX70_L2",
    ],
    "EOS-06": [
        "EOS-06_OCM-LAC_L1C",
        "EOS-06_OCM-GAC_L2C-AOD",
        "EOS-06_OCM-GAC_L2C-CHL",
        "EOS-06_SCAT_L1B",
    ],
    "Sentinel-1A": [
        "Sentinel-1A_SAR-IW_GRD",
        "Sentinel-1A_SAR-IW_SLC",
    ],
    "CartoSat-1": [
        "CartoSat-1_PAN_CartoDEM_30m",
    ],
    "NISAR": [
        "NISAR_SSAR_ROFF",
        "NISAR_SSAR-Beta_GSLC",
    ],
}


def get_satellite_collections(satellite_name: str) -> List[str]:
    """
    Returns all constituent STAC collection IDs belonging to a satellite platform.
    Handles aliases like 'eos-04', 'eos04', 'rs2', 'resourcesat-2', 'all'.
    """
    if not satellite_name:
        return []

    clean = satellite_name.strip().upper()

    if clean in ("ALL", "FLEET", "ISRO"):
        all_cols = []
        for cols in SATELLITE_COLLECTIONS.values():
            for c in cols:
                if c not in all_cols:
                    all_cols.append(c)
        return all_cols

    # Direct match
    for sat, cols in SATELLITE_COLLECTIONS.items():
        if clean == sat.upper():
            return list(cols)

    # Normalized match
    norm_input = re.sub(r"[^A-Z0-9]", "", clean)
    for sat, cols in SATELLITE_COLLECTIONS.items():
        norm_sat = re.sub(r"[^A-Z0-9]", "", sat.upper())
        if norm_input == norm_sat:
            return list(cols)

    # Specific common aliases
    alias_dict = {
        "RS2": "ResourceSat-2",
        "RESOURCESAT2": "ResourceSat-2",
        "RS2A": "ResourceSat-2A",
        "RESOURCESAT2A": "ResourceSat-2A",
        "EOS4": "EOS-04",
        "EOS04": "EOS-04",
        "RISAT1A": "EOS-04",
        "EOS6": "EOS-06",
        "EOS06": "EOS-06",
        "OCEANSAT3": "EOS-06",
        "SENTINEL1": "Sentinel-1A",
        "S1A": "Sentinel-1A",
        "CARTOSAT": "CartoSat-1",
    }
    if norm_input in alias_dict:
        return list(SATELLITE_COLLECTIONS[alias_dict[norm_input]])

    return []

