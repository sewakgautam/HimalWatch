"""Merges per-basin, per-year extraction outputs (data/{glaciers,lakes}/
{basin}-{year}.geojson) into the deploy-ready static bundle. See
docs/HIMALWATCH_SPEC.md §4 for the shape this produces and §2.5 for the
IndexEntry schema index.json follows.

Idempotent and additive: re-running after a new basin/year extraction
just re-derives everything from whatever *.geojson files currently exist
under data/glaciers/ and data/lakes/ — there's no incremental state to
get out of sync.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

SUBJECT_TYPES = ("glaciers", "lakes")

# Fields dropped from IndexEntry per spec §2.5 — everything else on a
# Glacier/Lake carries through as-is.
_INDEX_DROPPED_FIELDS = {"geom", "terminus_point"}


def _discover_extraction_files(data_dir: Path, subject_type: str) -> list[Path]:
    """Non-recursive glob directly in data/{subject_type}/ — deliberately
    doesn't recurse into latest/, snapshots/, or downloads/, which are
    this module's own *output* directories, not extraction inputs.
    """
    subject_dir = data_dir / subject_type
    if not subject_dir.exists():
        return []
    return sorted(p for p in subject_dir.glob("*.geojson") if p.is_file())


def _year_from_filename(path: Path) -> int:
    # Filenames are "{basin}-{year}.geojson"; year is always the trailing
    # numeric segment.
    stem = path.stem
    return int(stem.rsplit("-", 1)[-1])


def _load_by_year(files: list[Path]) -> dict[int, gpd.GeoDataFrame]:
    by_year: dict[int, list[gpd.GeoDataFrame]] = {}
    for path in files:
        year = _year_from_filename(path)
        by_year.setdefault(year, []).append(gpd.read_file(path))
    return {
        year: gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)
        for year, gdfs in by_year.items()
    }


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if gdf.empty:
        path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        return
    gdf.to_file(path, driver="GeoJSON")


def _to_index_entries(gdf: gpd.GeoDataFrame, subject_type: str) -> list[dict]:
    """One IndexEntry per feature: every property except the dropped
    geometry-shaped fields, plus `type` and a `centroid` for label
    placement / flyTo (spec §2.5).
    """
    entries = []
    for _, row in gdf.iterrows():
        entry = {
            k: v
            for k, v in row.items()
            if k != "geometry" and k not in _INDEX_DROPPED_FIELDS
        }
        entry["type"] = subject_type[:-1]  # "glaciers" -> "glacier", "lakes" -> "lake"
        centroid = row.geometry.centroid
        entry["centroid"] = [centroid.x, centroid.y]
        entries.append(_json_safe(entry))
    return entries


def _json_safe(entry: dict) -> dict:
    """geopandas/pandas can hand back numpy scalar types and NaN for
    missing values — normalize to plain JSON-serializable Python values
    (NaN/NaT -> None) rather than letting json.dumps choke on them.
    """
    safe = {}
    for k, v in entry.items():
        if isinstance(v, float) and v != v:  # NaN
            safe[k] = None
        elif isinstance(v, pd.Timestamp):
            # pyogrio infers ISO-8601-looking string columns (updated_at)
            # as datetime on read-back, even though this pipeline always
            # writes/consumes them as plain strings everywhere else.
            safe[k] = None if pd.isna(v) else v.isoformat()
        elif hasattr(v, "item"):  # numpy scalar
            safe[k] = v.item()
        else:
            safe[k] = v
    return safe


def _write_csv_download(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if gdf.empty:
        path.write_text("")
        return
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["geometry_wkt"] = gdf.geometry.apply(lambda g: g.wkt)
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def _build_pmtiles(source_geojson: Path, out_path: Path, layer_name: str) -> bool:
    """Shells out to tippecanoe. Returns False (and logs a warning rather
    than raising) if tippecanoe isn't installed — PMTiles are the one
    output a missing external binary shouldn't be allowed to take the
    entire static-bundle build down with it.
    """
    if shutil.which("tippecanoe") is None:
        logger.warning(
            "tippecanoe not found on PATH — skipping %s. Install it "
            "(`brew install tippecanoe` on macOS) to generate PMTiles.",
            out_path,
        )
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "tippecanoe",
            "-o",
            str(out_path),
            "-l",
            layer_name,
            "-zg",
            "--drop-densest-as-needed",
            "--force",
            str(source_geojson),
        ],
        check=True,
    )
    return True


def _git_commit_sha(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_static_bundle(data_dir: Path) -> dict:
    """Runs the full build: per-basin/per-year extraction files ->
    latest/, snapshots/, index.json, manifest.json, tiles/, downloads/.
    Returns the manifest dict (also written to manifest.json).
    """
    by_type_by_year: dict[str, dict[int, gpd.GeoDataFrame]] = {}
    for subject_type in SUBJECT_TYPES:
        files = _discover_extraction_files(data_dir, subject_type)
        by_type_by_year[subject_type] = _load_by_year(files)
        logger.info(
            "%s: found %d extraction file(s) across %d year(s)",
            subject_type,
            len(files),
            len(by_type_by_year[subject_type]),
        )

    counts_by_basin: dict[str, dict[str, int]] = {}
    subjects_by_year: dict[str, int] = {}
    index_entries: list[dict] = []

    for subject_type, by_year in by_type_by_year.items():
        if not by_year:
            continue
        latest_year = max(by_year)

        for year, gdf in by_year.items():
            _write_geojson(gdf, data_dir / subject_type / "snapshots" / f"{year}.geojson")
            subjects_by_year[str(year)] = subjects_by_year.get(str(year), 0) + len(gdf)

            download_stem = f"{subject_type}-nepal-{year}"
            _write_geojson(gdf, data_dir / "downloads" / f"{download_stem}.geojson")
            _write_csv_download(gdf, data_dir / "downloads" / f"{download_stem}.csv")

        latest_gdf = by_year[latest_year]
        _write_geojson(latest_gdf, data_dir / subject_type / "latest" / "nepal.geojson")
        for basin, basin_gdf in latest_gdf.groupby("basin"):
            _write_geojson(
                gpd.GeoDataFrame(basin_gdf, crs=latest_gdf.crs),
                data_dir / subject_type / "latest" / f"{basin}.geojson",
            )
            counts_by_basin.setdefault(basin, {"glaciers": 0, "lakes": 0})
            counts_by_basin[basin][subject_type] = len(basin_gdf)

        index_entries.extend(_to_index_entries(latest_gdf, subject_type))

        singular = subject_type[:-1]
        _build_pmtiles(
            data_dir / subject_type / "latest" / "nepal.geojson",
            data_dir / "tiles" / f"nepal-{subject_type}.pmtiles",
            layer_name=singular,
        )

    (data_dir).mkdir(parents=True, exist_ok=True)
    with open(data_dir / "index.json", "w") as f:
        json.dump(index_entries, f)
    logger.info("Wrote %d index entries to %s", len(index_entries), data_dir / "index.json")

    manifest = {
        "version": "0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "commit_sha": _git_commit_sha(data_dir.parent),
        "counts_by_basin": counts_by_basin,
        "subjects_by_year": subjects_by_year,
    }
    with open(data_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Wrote manifest to %s", data_dir / "manifest.json")

    return manifest
