"""Sentinel-2 glacial lake extraction. See docs/HIMALWATCH_SPEC.md §5.2
for the methodology each function here implements.

Uses the Copernicus Data Space Ecosystem (CDSE) rather than Google Earth
Engine — CDSE's STAC API + OAuth2 token auth needs no commercial-use
license question the way GEE's terms can raise for some deployments (see
CLAUDE.md's non-negotiables re: paid/commercial services).

Every function that touches network or raster IO is kept separate from
the pure geometry/array logic (compute_mndwi, otsu_threshold, vectorize,
filter_lakes, enrich, match_to_baseline) specifically so the pure
functions are unit-testable with small synthetic fixtures — see
tests/test_extract_lakes.py — without needing real Copernicus credentials
or a live network call.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterio.features import shapes as rasterio_shapes
from shapely.geometry import Point, Polygon, shape
from shapely.ops import unary_union
from skimage.filters import threshold_otsu

logger = logging.getLogger(__name__)

_CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/" "protocol/openid-connect/token"
)
_CDSE_STAC_URL = "https://stac.dataspace.copernicus.eu/v1"
_CDSE_COLLECTION = "sentinel-2-l2a"

MIN_AREA_M2 = 3000.0
MIN_ELEVATION_M = 3500.0
GLACIER_PROXIMITY_KM = 1.0
MAX_ELONGATION = 40.0
MATCH_DISTANCE_M = 200.0

# UTM 45N — see CLAUDE.md: areas/distances are computed in this CRS, never
# in the geographic (degree-based) CRS the source data arrives in.
_METRIC_CRS = "EPSG:32645"


@dataclass
class Composite:
    """A cloud-masked Sentinel-2 median composite over one basin/year, plus
    what filter_lakes/enrich need to interpret it.
    """

    green: np.ndarray
    swir: np.ndarray
    transform: rasterio.Affine
    crs: str
    cloud_pct: float
    year: int


class CopernicusAuthError(RuntimeError):
    """Raised when COPERNICUS_USERNAME/COPERNICUS_PASSWORD are missing or
    the token exchange fails. Never silently falls back to a cached or
    dummy token."""


def _get_cdse_token() -> str:
    username = os.environ.get("COPERNICUS_USERNAME")
    password = os.environ.get("COPERNICUS_PASSWORD")
    if not username or not password:
        raise CopernicusAuthError(
            "COPERNICUS_USERNAME/COPERNICUS_PASSWORD not set — see .env.example"
        )
    resp = requests.post(
        _CDSE_TOKEN_URL,
        data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def build_composite(
    basin_geom: dict,
    year: int,
    window: Literal["post-monsoon", "late-ablation"] = "post-monsoon",
) -> Composite:
    """Builds a cloud-masked Sentinel-2 median composite for the given
    basin geometry and year.

    Lake extraction uses the post-monsoon window (Oct 1 - Nov 30): lowest
    seasonal cloud cover, lake levels stabilized after monsoon inflow —
    see spec §5.1. Cloud masking uses the Scene Classification (SCL) band
    to drop cloud/shadow/snow-ambiguous pixels before compositing.

    This performs real network IO (STAC search + CDSE OAuth2 + band
    download) and is not exercised by the test suite or by
    `extract-lakes --dry-run` — both cover the pure functions below
    instead. A human running this for real needs COPERNICUS_USERNAME/
    COPERNICUS_PASSWORD set (see .env.example).
    """
    from pystac_client import Client  # local import: only needed on this path

    date_range = (
        f"{year}-10-01/{year}-11-30" if window == "post-monsoon" else f"{year}-09-01/{year}-10-31"
    )

    token = _get_cdse_token()
    catalog = Client.open(_CDSE_STAC_URL, headers={"Authorization": f"Bearer {token}"})
    search = catalog.search(
        collections=[_CDSE_COLLECTION],
        intersects=basin_geom,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": 60}},
    )
    items = list(search.items())
    if not items:
        raise RuntimeError(
            f"No Sentinel-2 scenes found for {date_range} over the given basin geometry"
        )
    logger.info("Found %d candidate scenes for %s", len(items), date_range)

    # A real implementation windowed-reads the Green (B03) and SWIR (B11)
    # bands plus SCL for every item, cloud-masks via SCL, and takes a
    # per-pixel median across the stack. Left as the integration point a
    # human fills in against their own CDSE download entitlement — see
    # this module's docstring for why that's not exercised here.
    raise NotImplementedError(
        "Band download + median compositing needs to be wired up against "
        "a real CDSE download entitlement — see build_composite's docstring. "
        "Use `--dry-run` to exercise everything downstream of this."
    )


def compute_mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """MNDWI = (Green - SWIR) / (Green + SWIR). Spec §5.2 step 1."""
    green = green.astype(np.float64)
    swir = swir.astype(np.float64)
    denom = green + swir
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = np.where(denom != 0, (green - swir) / denom, 0.0)
    return mndwi


def otsu_threshold(mndwi: np.ndarray) -> float:
    """Adaptive per-composite threshold rather than a fixed cutoff, since
    glacial lake spectral response varies with sediment load. Spec §5.2
    step 2.
    """
    finite = mndwi[np.isfinite(mndwi)]
    if finite.size == 0:
        raise ValueError("mndwi array has no finite values to threshold")
    return float(threshold_otsu(finite))


def vectorize(
    mndwi: np.ndarray, threshold: float, transform: rasterio.Affine, crs: str
) -> gpd.GeoDataFrame:
    """Binarizes MNDWI at `threshold` and vectorizes into polygons. Spec
    §5.2 step 3.
    """
    binary = (mndwi > threshold).astype(np.uint8)
    polygons = [
        shape(geom)
        for geom, value in rasterio_shapes(binary, mask=binary.astype(bool), transform=transform)
        if value == 1
    ]
    if not polygons:
        return gpd.GeoDataFrame({"geometry": []}, crs=crs)
    return gpd.GeoDataFrame({"geometry": polygons}, crs=crs)


def _elongation(geom) -> float:
    """perimeter^2 / area — a compact lake has a much lower ratio than a
    long thin river/stream segment. Undefined (infinite) for a
    zero-area geometry; callers should have already dropped those via the
    min-area filter before calling this.
    """
    area = geom.area
    if area <= 0:
        return float("inf")
    return (geom.length**2) / area


def filter_lakes(
    candidates: gpd.GeoDataFrame,
    dem_elevation_by_point: callable[[Point], float],
    glaciers_baseline: gpd.GeoDataFrame,
    min_area_m2: float = MIN_AREA_M2,
    min_elevation_m: float = MIN_ELEVATION_M,
    glacier_proximity_km: float = GLACIER_PROXIMITY_KM,
    max_elongation: float = MAX_ELONGATION,
) -> gpd.GeoDataFrame:
    """Applies the four lake filters from spec §5.2 step 4: elevation,
    glacier proximity, minimum area, elongation ratio.

    `dem_elevation_by_point` is injected rather than a DEM file path so
    this stays testable with a plain synthetic function in unit tests —
    the real CLI wires it to an actual DEM sample.

    Expects `candidates` and `glaciers_baseline` in a projected CRS
    (EPSG:32645) already, since this compares areas/distances in meters —
    callers should reproject before calling, not after.
    """
    if candidates.empty:
        return candidates

    if candidates.crs is None or candidates.crs.to_epsg() != 32645:
        raise ValueError(
            "filter_lakes expects candidates already reprojected to EPSG:32645 "
            f"(got {candidates.crs}) — see CLAUDE.md's area-computation convention"
        )

    gdf = candidates.copy()
    gdf["area_m2"] = gdf.geometry.area
    gdf = gdf[gdf["area_m2"] >= min_area_m2]

    gdf["elongation"] = gdf.geometry.map(_elongation)
    gdf = gdf[gdf["elongation"] <= max_elongation]

    gdf["elevation_m"] = gdf.geometry.centroid.map(dem_elevation_by_point)
    gdf = gdf[gdf["elevation_m"] >= min_elevation_m]

    if not glaciers_baseline.empty:
        buffer_m = glacier_proximity_km * 1000
        glacier_union = unary_union(glaciers_baseline.geometry.buffer(buffer_m))
        gdf = gdf[gdf.geometry.intersects(glacier_union)]
    else:
        logger.warning("glaciers_baseline is empty — glacier-proximity filter is a no-op")

    return gdf.drop(columns=["area_m2", "elongation"])


def enrich(
    features: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame,
    glaciers_baseline: gpd.GeoDataFrame,
    year: int,
    cloud_pct: float,
) -> gpd.GeoDataFrame:
    """Adds province/district/basin (spatial join against districts),
    parent_glacier_id (nearest baseline glacier), area_current_km2, and
    confidence. Spec §5.2 step 5 / §5.4.

    Expects `features` reprojected to EPSG:32645 already (matches
    filter_lakes' expectation) and `districts` in EPSG:4326 (the format
    load_boundaries.py writes) — reprojects districts internally rather
    than pushing that requirement onto callers, since districts are
    reused as-is across every extraction call in a run.
    """
    if features.empty:
        return features

    gdf = features.copy()
    gdf["area_current_km2"] = gdf.geometry.area / 1_000_000
    gdf["confidence"] = "high" if cloud_pct < 10 else "medium" if cloud_pct < 30 else "low"
    gdf["year"] = year

    districts_utm = districts.to_crs(_METRIC_CRS)
    joined = gpd.sjoin(
        gdf.set_geometry(gdf.geometry.centroid),
        districts_utm[["name", "province", "basin", "geometry"]],
        how="left",
        predicate="within",
    )
    gdf["district"] = joined["name"].values
    gdf["province"] = joined["province"].values
    gdf["basin"] = joined["basin"].values
    gdf = gdf.set_geometry(features.geometry)

    if not glaciers_baseline.empty:
        glaciers_utm = glaciers_baseline.to_crs(_METRIC_CRS)

        def _nearest_glacier_id(point: Point) -> str | None:
            distances = glaciers_utm.geometry.distance(point)
            nearest_idx = distances.idxmin()
            if distances.loc[nearest_idx] > GLACIER_PROXIMITY_KM * 1000:
                return None
            return glaciers_utm.loc[nearest_idx, "id"]

        gdf["parent_glacier_id"] = gdf.geometry.centroid.map(_nearest_glacier_id)
    else:
        gdf["parent_glacier_id"] = None

    return gdf


def match_to_baseline(
    current: gpd.GeoDataFrame,
    previous: gpd.GeoDataFrame,
    max_distance_m: float = MATCH_DISTANCE_M,
) -> gpd.GeoDataFrame:
    """Matches `current` features to `previous` year's by centroid
    distance to preserve stable ids across years. Unmatched current
    features get a new `lake:gen:{hash}` id. Spec §5.2 step 6.

    Expects both GeoDataFrames in EPSG:32645 already (distance
    comparison). `previous` may be empty (first-ever run for this basin).
    """
    gdf = current.copy()
    if gdf.empty:
        gdf["id"] = []
        return gdf

    if previous.empty:
        gdf["id"] = [_generate_id(geom) for geom in gdf.geometry]
        return gdf

    prev_centroids = previous.geometry.centroid
    ids: list[str] = []
    used_previous: set[int] = set()
    for geom in gdf.geometry:
        centroid = geom.centroid
        distances = prev_centroids.distance(centroid)
        # Exclude previous features already claimed by an earlier current
        # feature in this loop — otherwise two nearby current lakes could
        # both match the same previous one.
        distances = distances.drop(index=[i for i in used_previous if i in distances.index])
        nearest_idx = distances.idxmin() if not distances.empty else None
        if nearest_idx is not None and distances.loc[nearest_idx] <= max_distance_m:
            used_previous.add(nearest_idx)
            ids.append(previous.loc[nearest_idx, "id"])
        else:
            ids.append(_generate_id(geom))
    gdf["id"] = ids
    return gdf


def _generate_id(geom) -> str:
    """Stable-ish id for a newly-appeared feature: hash of the centroid
    rounded to ~10m precision, so re-running extraction on the exact same
    composite reproduces the same id rather than a fresh random one every
    time.
    """
    import hashlib

    c = geom.centroid
    key = f"{round(c.x, 4)}:{round(c.y, 4)}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]
    return f"lake:gen:{digest}"


def synthetic_dry_run_lakes(basin: str, year: int) -> gpd.GeoDataFrame:
    """5 fake lakes for `extract-lakes --dry-run` — wires up the CLI and
    static-bundle path end to end without a real Sentinel-2 composite.
    Coordinates are within Nepal's Koshi basin regardless of the
    requested `basin`, since this only needs to look plausible, not be
    geographically correct for basins other than Koshi.
    """
    now = datetime.now(UTC).isoformat()
    base_lng, base_lat = 86.9, 27.9  # near Everest region, Koshi basin
    records = []
    for i in range(5):
        offset = i * 0.02
        cx, cy = base_lng + offset, base_lat + offset
        poly = Polygon(
            [
                (cx - 0.002, cy - 0.001),
                (cx + 0.002, cy - 0.001),
                (cx + 0.002, cy + 0.001),
                (cx - 0.002, cy + 0.001),
            ]
        )
        records.append(
            {
                "id": f"lake:gen:dryrun{i}",
                "icimod_id": None,
                "name": None,
                "basin": basin,
                "sub_basin": None,
                "province": "Koshi",
                "district": "Solukhumbu",
                "elevation_m": 4200 + i * 50,
                "area_current_km2": 0.05 + i * 0.01,
                "area_2000_km2": None,
                "area_change_pct_since_2000": None,
                "dam_type": "unknown",
                "glof_risk": "unassessed",
                "is_pdgl": False,
                "parent_glacier_id": None,
                "outburst_history": [],
                "downstream_population": None,
                "confidence": "medium",
                "year": year,
                "updated_at": now,
                "geometry": poly,
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def extract_lakes(
    basin: str,
    year: int,
    out_path: Path,
    reference_dir: Path,
    dry_run: bool = False,
) -> int:
    """Top-level entry point the CLI calls. Returns the feature count
    written to `out_path`.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        logger.info("--dry-run: generating synthetic lakes instead of a real extraction")
        result = synthetic_dry_run_lakes(basin, year)
        result.to_file(out_path, driver="GeoJSON")
        return len(result)

    basins_gdf = gpd.read_file(reference_dir / "basins.geojson")
    basin_row = basins_gdf[basins_gdf["id"] == basin]
    if basin_row.empty:
        raise ValueError(f"Unknown basin {basin!r} — check data/reference/basins.geojson")
    basin_geom = basin_row.iloc[0].geometry.__geo_interface__

    composite = build_composite(basin_geom, year, window="post-monsoon")
    mndwi = compute_mndwi(composite.green, composite.swir)
    threshold = otsu_threshold(mndwi)
    candidates = vectorize(mndwi, threshold, composite.transform, composite.crs)
    candidates_utm = candidates.to_crs(_METRIC_CRS)

    glaciers_baseline = gpd.read_file(reference_dir / "glaciers_baseline.geojson")
    districts = gpd.read_file(reference_dir / "districts.geojson")

    # TODO(human): wire dem_elevation_by_point to a real DEM sample once a
    # Nepal DEM is loaded (see load_rgi.py's docstring re: RGI6 already
    # carrying hypsometry for glaciers — lakes have no such shortcut).
    def _unavailable_dem(_point: Point) -> float:
        raise NotImplementedError("No DEM wired up yet — see extract_lakes' TODO")

    filtered = filter_lakes(candidates_utm, _unavailable_dem, glaciers_baseline.to_crs(_METRIC_CRS))
    enriched = enrich(filtered, districts, glaciers_baseline, year, composite.cloud_pct)

    previous = gpd.GeoDataFrame()
    if out_path.exists():
        previous = gpd.read_file(out_path).to_crs(_METRIC_CRS)
    matched = match_to_baseline(enriched, previous)

    result = matched.to_crs("EPSG:4326")
    result.to_file(out_path, driver="GeoJSON")
    return len(result)
