"""Loads the RGI baseline glacier inventory for Nepal.

Source: RGI 6.0 Region 15 ("South Asia East"), from the public GLIMS/OGGM
mirror — **not** RGI 7.0. RGI 7.0's own geometry files are only
distributed via NSIDC DAAC behind a free-but-required NASA Earthdata
login; scripting around an interactive login isn't something this loader
does. RGI 6.0 is freely downloadable with no auth and, usefully, already
carries per-glacier hypsometry (Zmin/Zmax/Zmed) in its base attribute
table, so no separate DEM sampling step is needed for elevation here.
`rgi_id` values are therefore RGI60-format (`RGI60-15.NNNNN`), not the
RGI2000-v7 format docs/HIMALWATCH_SPEC.md's example uses — flagged here
rather than silently diverging from the spec.

Region 15 covers a wider area than Nepal (parts of India/Bhutan/China
border ranges too), so this loader spatially filters to glaciers whose
centroid falls inside a Nepal district (via load_boundaries' output) —
run that loader first.

Known gap: `debris_covered` is not in RGI 6.0's base attribute table (it's
a separate supplementary layer, e.g. Scherler et al. 2018) and is not
loaded here. Every glacier defaults to `debris_covered=False` until that
layer is added — this is a real gap, not a verified "not debris-covered".
"""

from __future__ import annotations

import logging
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import requests

logger = logging.getLogger(__name__)

_RGI_ZIP_URL = (
    "https://cluster.klima.uni-bremen.de/~oggm/rgi/www.glims.org/RGI/"
    "rgi60_files/15_rgi60_SouthAsiaEast.zip"
)
_MAX_AGE_DAYS = 30


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < _MAX_AGE_DAYS


def _download_rgi_shapefile(tmp_dir: Path) -> Path:
    zip_path = tmp_dir / "rgi15.zip"
    logger.info("Downloading RGI 6.0 Region 15 (%s)", _RGI_ZIP_URL)
    with requests.get(_RGI_ZIP_URL, timeout=180, stream=True) as resp:
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_dir)
    shp_files = list(tmp_dir.glob("*.shp"))
    if not shp_files:
        raise RuntimeError("RGI zip did not contain a .shp file")
    return shp_files[0]


def _nan_to_none(value: object) -> object:
    if isinstance(value, float) and value != value:  # NaN check without numpy import
        return None
    return value


def load_rgi(out_dir: Path, boundaries_dir: Path) -> int:
    """Loads RGI 6.0 Region 15, filters to Nepal, enriches, and writes
    data/reference/glaciers_baseline.geojson. Returns the feature count.
    """
    out_path = out_dir / "glaciers_baseline.geojson"
    if _is_fresh(out_path):
        logger.info("glaciers_baseline.geojson is fresh, skipping download")
        return len(gpd.read_file(out_path))

    districts_path = boundaries_dir / "districts.geojson"
    if not districts_path.exists():
        raise FileNotFoundError(
            f"{districts_path} not found — run `himalwatch-pipeline load` "
            "(boundaries) before loading the RGI baseline."
        )
    districts = gpd.read_file(districts_path)

    with tempfile.TemporaryDirectory() as tmp:
        shp_path = _download_rgi_shapefile(Path(tmp))
        rgi = gpd.read_file(shp_path)

    logger.info("Loaded %d raw RGI Region 15 features", len(rgi))

    # Point-in-polygon join on the centroid RGI already reports (CenLon/
    # CenLat) rather than a full polygon overlay — much cheaper at this
    # feature count, and Region 15 -> Nepal is exactly the kind of
    # centroid-inside-boundary filter that doesn't need edge-of-polygon
    # precision.
    centroids = gpd.GeoDataFrame(
        rgi[["RGIId"]],
        geometry=gpd.points_from_xy(rgi["CenLon"], rgi["CenLat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        centroids,
        districts[["name", "province", "basin", "geometry"]],
        how="inner",
        predicate="within",
    )
    nepal_ids = set(joined["RGIId"])
    district_by_id = dict(zip(joined["RGIId"], joined["name"], strict=True))
    province_by_id = dict(zip(joined["RGIId"], joined["province"], strict=True))
    basin_by_id = dict(zip(joined["RGIId"], joined["basin"], strict=True))

    nepal = rgi[rgi["RGIId"].isin(nepal_ids)].copy()
    logger.info("%d of %d Region 15 glaciers fall within Nepal", len(nepal), len(rgi))

    unmatched_basin = [rid for rid in nepal["RGIId"] if basin_by_id.get(rid) is None]
    if unmatched_basin:
        logger.warning(
            "%d Nepal glacier(s) matched a district with no basin assignment",
            len(unmatched_basin),
        )

    now = datetime.now(UTC).isoformat()
    records = []
    for _, row in nepal.iterrows():
        rgi_id = row["RGIId"]
        records.append(
            {
                "id": f"glacier:{rgi_id}",
                "rgi_id": rgi_id,
                "name": _nan_to_none(row["Name"]),
                "basin": basin_by_id.get(rgi_id),
                "sub_basin": None,
                "province": province_by_id.get(rgi_id),
                "district": district_by_id.get(rgi_id),
                "elevation_min_m": float(row["Zmin"]) if row["Zmin"] > 0 else None,
                "elevation_max_m": float(row["Zmax"]) if row["Zmax"] > 0 else None,
                "elevation_mean_m": float(row["Zmed"]) if row["Zmed"] > 0 else None,
                "area_current_km2": float(row["Area"]),
                "area_2000_km2": float(row["Area"]),
                "area_change_pct_since_2000": 0.0,
                # Known gap — see module docstring.
                "debris_covered": False,
                "sla_current_m": None,
                "terminus_point": None,
                "associated_lake_ids": [],
                "confidence": "medium",  # RGI baseline, not a fresh extraction
                "year": 2000,
                "updated_at": now,
                "geometry": row["geometry"],
            }
        )

    result = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_file(out_path, driver="GeoJSON")
    logger.info("Wrote %d glaciers to %s", len(result), out_path)
    return len(result)
