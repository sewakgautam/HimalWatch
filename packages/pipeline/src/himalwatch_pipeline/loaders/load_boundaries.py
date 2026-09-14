"""Loads Nepal's 7 provinces + 75 districts (geoBoundaries) and dissolves
districts into the 4 major basins (see basins.py for the mapping).

Source: geoBoundaries (https://www.geoboundaries.org), CC-BY 3.0 IGO for
provinces / public domain for districts — a stable, directly-downloadable
GeoJSON source, chosen over a live OSM/Overpass query for reliability (a
full-country admin-boundary Overpass query is slow and prone to timeout).

Pinned to a specific geoBoundaries commit so re-running this loader months
later doesn't silently pick up a different boundary revision.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import requests

from .basins import BASIN_NAMES, basin_for_district

logger = logging.getLogger(__name__)

_GEOBOUNDARIES_COMMIT = "9469f09"
_ADM1_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/"
    f"{_GEOBOUNDARIES_COMMIT}/releaseData/gbOpen/NPL/ADM1/geoBoundaries-NPL-ADM1.geojson"
)
_ADM2_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/"
    f"{_GEOBOUNDARIES_COMMIT}/releaseData/gbOpen/NPL/ADM2/geoBoundaries-NPL-ADM2.geojson"
)

# geoBoundaries' pre-2023 renaming still calls two provinces "Province 1"
# and "Province 2" — map to the official names adopted in 2023.
_PROVINCE_NAME_OVERRIDES: dict[str, str] = {
    "Province 1": "Koshi",
    "Province 2": "Madhesh",
}

_PROVINCE_NAME_NE: dict[str, str] = {
    "Koshi": "कोशी प्रदेश",
    "Madhesh": "मधेश प्रदेश",
    "Bagmati": "बागमती प्रदेश",
    "Gandaki": "गण्डकी प्रदेश",
    "Lumbini": "लुम्बिनी प्रदेश",
    "Karnali": "कर्णाली प्रदेश",
    "Sudurpaschim": "सुदूरपश्चिम प्रदेश",
}

_MAX_AGE_DAYS = 30


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < _MAX_AGE_DAYS


def _download_geojson(url: str) -> gpd.GeoDataFrame:
    logger.info("Downloading %s", url)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return gpd.GeoDataFrame.from_features(json.loads(resp.text)["features"], crs="EPSG:4326")


def load_provinces(out_dir: Path) -> gpd.GeoDataFrame:
    out_path = out_dir / "provinces.geojson"
    if _is_fresh(out_path):
        logger.info("provinces.geojson is fresh, skipping download")
        return gpd.read_file(out_path)

    gdf = _download_geojson(_ADM1_URL)
    gdf["name"] = gdf["shapeName"].map(lambda n: _PROVINCE_NAME_OVERRIDES.get(n, n))
    gdf["name_ne"] = gdf["name"].map(_PROVINCE_NAME_NE)
    gdf["code"] = gdf["shapeISO"]
    result = gdf[["name", "name_ne", "code", "geometry"]]

    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_file(out_path, driver="GeoJSON")
    logger.info("Wrote %d provinces to %s", len(result), out_path)
    return result


def load_districts(out_dir: Path, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out_path = out_dir / "districts.geojson"
    if _is_fresh(out_path):
        logger.info("districts.geojson is fresh, skipping download")
        return gpd.read_file(out_path)

    gdf = _download_geojson(_ADM2_URL)
    gdf["name"] = gdf["shapeName"]
    result = enrich_districts(gdf, provinces)

    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_file(out_path, driver="GeoJSON")
    logger.info("Wrote %d districts to %s", len(result), out_path)
    return result


def enrich_districts(districts: gpd.GeoDataFrame, provinces: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assigns `basin` (via the hardcoded district->basin map) and
    `province` (via largest-overlap spatial join) to each district.

    Pulled out of `load_districts` so it's testable against small
    hand-crafted fixtures without needing a live download — see
    tests/test_loaders.py.

    The overlay-then-largest-area approach (rather than a plain "within"
    predicate) is deliberate: a district whose boundary crosses a
    province edge due to minor topology mismatches between two
    independently-sourced datasets would otherwise match zero or more
    than one province.
    """
    gdf = districts.copy()
    gdf["basin"] = gdf["name"].map(basin_for_district)
    unmatched = gdf.loc[gdf["basin"].isna(), "name"].tolist()
    if unmatched:
        logger.warning(
            "No basin mapping for %d district(s): %s — extend "
            "loaders/basins.py DISTRICT_ALIASES/DISTRICT_TO_BASIN",
            len(unmatched),
            unmatched,
        )

    joined = gpd.overlay(
        gdf[["name", "basin", "geometry"]],
        provinces[["name", "geometry"]].rename(columns={"name": "province"}),
        how="intersection",
        keep_geom_type=False,
    )
    # Per CLAUDE.md: areas are computed in EPSG:32645 (UTM 45N, covers all
    # of Nepal), never in the geographic CRS the data arrives in — degree²
    # comparisons distort east-west vs. north-south overlap unevenly.
    joined["area"] = joined.geometry.to_crs("EPSG:32645").area
    largest = joined.loc[joined.groupby("name")["area"].idxmax()]
    province_by_district = dict(zip(largest["name"], largest["province"], strict=True))

    gdf["province"] = gdf["name"].map(province_by_district)
    unmatched_province = gdf.loc[gdf["province"].isna(), "name"].tolist()
    if unmatched_province:
        logger.warning(
            "Could not assign a province (no overlap found) for: %s",
            unmatched_province,
        )

    return gdf[["name", "province", "basin", "geometry"]]


def build_basins(out_dir: Path, districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out_path = out_dir / "basins.geojson"

    with_basin = districts.dropna(subset=["basin"])
    dissolved = with_basin.dissolve(by="basin", as_index=False)
    dissolved["id"] = dissolved["basin"]
    dissolved["name"] = dissolved["id"].map(lambda b: BASIN_NAMES[b][0])
    dissolved["name_ne"] = dissolved["id"].map(lambda b: BASIN_NAMES[b][1])
    result = dissolved[["id", "name", "name_ne", "geometry"]]

    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_file(out_path, driver="GeoJSON")
    logger.info("Wrote %d basins to %s", len(result), out_path)
    return result


def load_boundaries(out_dir: Path) -> dict[str, int]:
    """Runs the full boundaries load: provinces -> districts -> basins.

    Returns summary counts for the CLI to print.
    """
    provinces = load_provinces(out_dir)
    districts = load_districts(out_dir, provinces)
    basins = build_basins(out_dir, districts)
    return {
        "provinces": len(provinces),
        "districts": len(districts),
        "basins": len(basins),
    }
