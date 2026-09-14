"""Sentinel-2 glacier extraction. See docs/HIMALWATCH_SPEC.md §5.3 for the
methodology each function here implements.

Structurally mirrors extract/lakes.py: pure geometry/array functions
(compute_ndsi, slope-mask/baseline-constraint logic, match_to_rgi) are
kept separate from the network/raster IO in build_composite so the pure
functions are unit-testable with small synthetic fixtures — see
tests/test_extract_glaciers.py.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

from .lakes import Composite
from .lakes import build_composite as _build_composite_shared

logger = logging.getLogger(__name__)

NDSI_THRESHOLD = 0.4
MAX_SLOPE_DEG = 45.0
BASELINE_BUFFER_M = 200.0

# UTM 45N — see CLAUDE.md's area-computation convention, and
# extract/lakes.py's _METRIC_CRS for the same choice there.
_METRIC_CRS = "EPSG:32645"


def build_composite(basin_geom: dict, year: int) -> Composite:
    """Glacier extraction uses the late-ablation window (Sep 1 - Oct 31),
    not lakes' post-monsoon window — see spec §5.1. Delegates to
    extract/lakes.py's build_composite (same CDSE auth/STAC-search
    mechanics, different date window), rather than duplicating that
    network/auth code here.
    """
    return _build_composite_shared(basin_geom, year, window="late-ablation")


def compute_ndsi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """NDSI = (Green - SWIR) / (Green + SWIR) — same band pair as lakes'
    MNDWI; the difference is thresholding and downstream filtering, not
    the index itself. Spec §5.3 step 1.
    """
    green = green.astype(np.float64)
    swir = swir.astype(np.float64)
    denom = green + swir
    with np.errstate(divide="ignore", invalid="ignore"):
        ndsi = np.where(denom != 0, (green - swir) / denom, 0.0)
    return ndsi


def apply_slope_mask(ndsi_binary: np.ndarray, slope_deg: np.ndarray) -> np.ndarray:
    """Excludes slopes >= 45° — steep faces produce spurious snow/ice
    signal that isn't glacier body. Spec §5.3 step 2.
    """
    return ndsi_binary & (slope_deg < MAX_SLOPE_DEG)


def constrain_to_baseline(
    candidates: gpd.GeoDataFrame,
    rgi_baseline: gpd.GeoDataFrame,
    buffer_m: float = BASELINE_BUFFER_M,
) -> gpd.GeoDataFrame:
    """Clips extraction candidates to the RGI baseline outline buffered by
    `buffer_m` — glaciers only retreat over the monitoring window, so
    anything outside baseline+buffer is extraction noise, not real
    advance. Spec §5.3 step 3.

    Expects both GeoDataFrames already in EPSG:32645 (matches
    extract/lakes.py's filter_lakes convention).
    """
    if candidates.empty or rgi_baseline.empty:
        return candidates.iloc[0:0]

    if candidates.crs is None or candidates.crs.to_epsg() != 32645:
        raise ValueError(
            "constrain_to_baseline expects candidates already reprojected to "
            f"EPSG:32645 (got {candidates.crs})"
        )

    buffered_baseline = rgi_baseline.geometry.buffer(buffer_m).union_all()
    clipped = candidates.copy()
    clipped["geometry"] = clipped.geometry.intersection(buffered_baseline)
    return clipped[~clipped.geometry.is_empty]


def match_to_rgi(
    candidates: gpd.GeoDataFrame,
    rgi_baseline: gpd.GeoDataFrame,
    max_distance_m: float = 500.0,
) -> gpd.GeoDataFrame:
    """Matches each candidate to its RGI baseline glacier by nearest
    centroid, for a stable `rgi_id` across extraction years. Spec §5.3
    step 4.

    Unlike lakes' match_to_baseline, this never mints a new id for an
    unmatched candidate — every real glacier extraction should fall
    within `max_distance_m` of *some* RGI baseline entry (that's what
    constrain_to_baseline already enforced via the buffered intersection);
    an unmatched candidate here means the buffer/matching distance needs
    tuning, not a genuinely new glacier, so those rows are dropped with a
    warning rather than assigned a fabricated id.
    """
    if candidates.empty:
        return candidates.assign(rgi_id=[], id=[])

    baseline_centroids = rgi_baseline.geometry.centroid
    rgi_ids: list[str | None] = []
    for geom in candidates.geometry:
        centroid = geom.centroid
        distances = baseline_centroids.distance(centroid)
        nearest_idx = distances.idxmin()
        if distances.loc[nearest_idx] <= max_distance_m:
            rgi_ids.append(rgi_baseline.loc[nearest_idx, "rgi_id"])
        else:
            rgi_ids.append(None)

    result = candidates.copy()
    result["rgi_id"] = rgi_ids
    unmatched = result["rgi_id"].isna().sum()
    if unmatched:
        logger.warning(
            "%d candidate(s) did not match any RGI baseline glacier within %dm "
            "— dropped rather than assigned a fabricated id",
            unmatched,
            max_distance_m,
        )
    result = result[result["rgi_id"].notna()]
    result["id"] = result["rgi_id"].map(lambda r: f"glacier:{r}")
    return result


def enrich(
    features: gpd.GeoDataFrame,
    districts: gpd.GeoDataFrame,
    rgi_baseline: gpd.GeoDataFrame,
    year: int,
    cloud_pct: float,
) -> gpd.GeoDataFrame:
    """Adds province/district/basin, area_current_km2/area_change_pct,
    and confidence. Spec §5.3 step 5 / §5.4 — including the debris-covered
    confidence override (capped at "low" regardless of cloud cover; RGI's
    baseline `debris_covered` flag is currently always False per
    loaders/load_rgi.py's documented gap, so this override is a no-op
    until that gap is closed, not dead code).
    """
    if features.empty:
        return features

    gdf = features.copy()
    gdf["area_current_km2"] = gdf.geometry.area / 1_000_000

    baseline_by_id = rgi_baseline.set_index("rgi_id")

    def _baseline_area(rid: str) -> float | None:
        return baseline_by_id.loc[rid, "area_2000_km2"] if rid in baseline_by_id.index else None

    gdf["area_2000_km2"] = gdf["rgi_id"].map(_baseline_area)
    gdf["area_change_pct_since_2000"] = gdf.apply(
        lambda row: (
            (row["area_current_km2"] - row["area_2000_km2"]) / row["area_2000_km2"] * 100
            if row["area_2000_km2"]
            else None
        ),
        axis=1,
    )
    gdf["debris_covered"] = gdf["rgi_id"].map(
        lambda rid: (
            bool(baseline_by_id.loc[rid, "debris_covered"])
            if rid in baseline_by_id.index
            else False
        )
    )

    gdf["confidence"] = "high" if cloud_pct < 10 else "medium" if cloud_pct < 30 else "low"
    gdf.loc[gdf["debris_covered"], "confidence"] = "low"
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
    return gdf.set_geometry(features.geometry)


def synthetic_dry_run_glaciers(
    basin: str, year: int, reference_dir: Path | None = None
) -> gpd.GeoDataFrame:
    """10 fake glaciers for `extract-glaciers --dry-run`, reusing the real
    RGI ids from `reference_dir`/glaciers_baseline.geojson (when given) so
    the static bundle builder's RGI-id matching has something real to
    match against — a purely-fabricated id would make Session 4's
    bundle-builder demo (and any human spot-checking a detail page) look
    broken for the wrong reason.
    """
    now = datetime.now(UTC).isoformat()
    rgi_ids: list[str] = []
    reference_path = reference_dir / "glaciers_baseline.geojson" if reference_dir else None
    if reference_path is not None and reference_path.exists():
        baseline = gpd.read_file(reference_path)
        koshi_glaciers = baseline[baseline["basin"] == basin]
        rgi_ids = koshi_glaciers["rgi_id"].head(10).tolist()
    if not rgi_ids:
        logger.warning(
            "No baseline glaciers found for basin=%r — run `pipeline load` first "
            "for realistic dry-run ids; falling back to fabricated ids",
            basin,
        )
        rgi_ids = [f"RGI60-15.{90000 + i}" for i in range(10)]

    base_lng, base_lat = 86.8, 27.95
    records = []
    for i, rgi_id in enumerate(rgi_ids):
        offset = i * 0.015
        cx, cy = base_lng + offset, base_lat - offset
        poly = Polygon(
            [
                (cx - 0.003, cy - 0.003),
                (cx + 0.003, cy - 0.003),
                (cx + 0.003, cy + 0.003),
                (cx - 0.003, cy + 0.003),
            ]
        )
        records.append(
            {
                "id": f"glacier:{rgi_id}",
                "rgi_id": rgi_id,
                "name": None,
                "basin": basin,
                "sub_basin": None,
                "province": "Koshi",
                "district": "Solukhumbu",
                "elevation_min_m": 5000.0,
                "elevation_max_m": 6200.0,
                "elevation_mean_m": 5600.0,
                "area_current_km2": 2.5 - i * 0.05,
                "area_2000_km2": 2.6 - i * 0.05,
                "area_change_pct_since_2000": -3.8,
                "debris_covered": False,
                "sla_current_m": None,
                "terminus_point": None,
                "associated_lake_ids": [],
                "confidence": "medium",
                "year": year,
                "updated_at": now,
                "geometry": poly,
            }
        )
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def extract_glaciers(
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
        logger.info("--dry-run: generating synthetic glaciers instead of a real extraction")
        result = synthetic_dry_run_glaciers(basin, year, reference_dir)
        result.to_file(out_path, driver="GeoJSON")
        return len(result)

    basins_gdf = gpd.read_file(reference_dir / "basins.geojson")
    basin_row = basins_gdf[basins_gdf["id"] == basin]
    if basin_row.empty:
        raise ValueError(f"Unknown basin {basin!r} — check data/reference/basins.geojson")
    basin_geom = basin_row.iloc[0].geometry.__geo_interface__

    composite = build_composite(basin_geom, year)
    compute_ndsi(composite.green, composite.swir)  # thresholding happens once slope masking lands

    # A real implementation samples slope from the DEM here and applies
    # apply_slope_mask before vectorizing — left as an integration point
    # alongside build_composite's, for the same "needs a real CDSE/DEM
    # entitlement" reason documented in extract/lakes.py.
    raise NotImplementedError(
        "Slope masking + vectorization needs a real DEM wired up — see "
        "extract_glaciers' TODO. Use `--dry-run` to exercise everything "
        "downstream of this."
    )
