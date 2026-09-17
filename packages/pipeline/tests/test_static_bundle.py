from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from himalwatch_pipeline.build.static_bundle import build_static_bundle


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


def _write_fixture(path: Path, subject_type: str, basin: str, year: int, count: int) -> None:
    now = datetime.now(UTC).isoformat()
    common = {
        "basin": basin,
        "sub_basin": None,
        "province": "Koshi",
        "district": "Solukhumbu",
        "confidence": "medium",
        "year": year,
        "updated_at": now,
    }
    if subject_type == "glaciers":
        records = [
            {
                **common,
                "id": f"glacier:RGI60-15.{i}",
                "rgi_id": f"RGI60-15.{i}",
                "name": None,
                "elevation_min_m": 5000.0,
                "elevation_max_m": 6000.0,
                "elevation_mean_m": 5500.0,
                "area_current_km2": 1.0 + i,
                "area_2000_km2": 1.1 + i,
                "area_change_pct_since_2000": -5.0,
                "debris_covered": False,
                "sla_current_m": None,
                "associated_lake_ids": [],
                "geometry": _square(86.8 + i * 0.01, 27.9, 0.002),
            }
            for i in range(count)
        ]
    else:
        records = [
            {
                **common,
                "id": f"lake:gen:{i}",
                "icimod_id": None,
                "name": None,
                "elevation_m": 4200.0,
                "area_current_km2": 0.05 + i * 0.01,
                "area_2000_km2": None,
                "area_change_pct_since_2000": None,
                "dam_type": "unknown",
                "glof_risk": "unassessed",
                "is_pdgl": False,
                "parent_glacier_id": None,
                "outburst_history": [],
                "downstream_population": None,
                "geometry": _square(86.9 + i * 0.01, 27.95, 0.001),
            }
            for i in range(count)
        ]
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")


class TestBuildStaticBundle:
    def test_manifest_index_and_pmtiles_are_produced(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        _write_fixture(data_dir / "glaciers" / "koshi-2025.geojson", "glaciers", "koshi", 2025, 3)
        _write_fixture(data_dir / "lakes" / "koshi-2025.geojson", "lakes", "koshi", 2025, 2)

        manifest = build_static_bundle(data_dir)

        assert (data_dir / "manifest.json").exists()
        assert (data_dir / "index.json").exists()
        assert json.loads((data_dir / "manifest.json").read_text()) == manifest

        index_entries = json.loads((data_dir / "index.json").read_text())
        assert len(index_entries) == 5  # 3 glaciers + 2 lakes
        types = {e["type"] for e in index_entries}
        assert types == {"glacier", "lake"}
        # geom/terminus_point must never leak into the index (spec §2.5).
        assert all("geom" not in e and "terminus_point" not in e for e in index_entries)
        assert all("centroid" in e for e in index_entries)

        assert manifest["counts_by_basin"]["koshi"] == {"glaciers": 3, "lakes": 2}
        assert manifest["subjects_by_year"]["2025"] == 5

        assert (data_dir / "glaciers" / "latest" / "nepal.geojson").exists()
        assert (data_dir / "glaciers" / "latest" / "koshi.geojson").exists()
        assert (data_dir / "glaciers" / "snapshots" / "2025.geojson").exists()
        assert (data_dir / "lakes" / "latest" / "nepal.geojson").exists()

        assert (data_dir / "downloads" / "glaciers-nepal-2025.geojson").exists()
        assert (data_dir / "downloads" / "glaciers-nepal-2025.csv").exists()
        assert (data_dir / "downloads" / "lakes-nepal-2025.csv").exists()

        csv_text = (data_dir / "downloads" / "glaciers-nepal-2025.csv").read_text()
        assert "geometry_wkt" in csv_text
        assert "POLYGON" in csv_text

        # At least one PMTiles file — the session-4 checkpoint's own
        # wording. Both should exist since tippecanoe is available in
        # this environment, but the strict requirement is "at least one".
        pmtiles = list((data_dir / "tiles").glob("*.pmtiles"))
        assert len(pmtiles) >= 1

    def test_idempotent_rerun_produces_the_same_counts(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        _write_fixture(data_dir / "glaciers" / "koshi-2025.geojson", "glaciers", "koshi", 2025, 4)

        first = build_static_bundle(data_dir)
        second = build_static_bundle(data_dir)

        assert first["counts_by_basin"] == second["counts_by_basin"]
        assert first["subjects_by_year"] == second["subjects_by_year"]

    def test_two_basins_same_year_merge_into_one_nepal_file(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        _write_fixture(data_dir / "glaciers" / "koshi-2025.geojson", "glaciers", "koshi", 2025, 2)
        _write_fixture(
            data_dir / "glaciers" / "gandaki-2025.geojson", "glaciers", "gandaki", 2025, 3
        )

        manifest = build_static_bundle(data_dir)

        nepal = gpd.read_file(data_dir / "glaciers" / "latest" / "nepal.geojson")
        assert len(nepal) == 5
        assert manifest["counts_by_basin"]["koshi"]["glaciers"] == 2
        assert manifest["counts_by_basin"]["gandaki"]["glaciers"] == 3


class TestRestoredHistoryFoldIn:
    """Regression coverage for "why do I only ever see the current year" —
    a prior year's snapshot file, as restore_history.py would have placed
    it before this run, must be folded into subjects_by_year and get its
    own downloads regenerated, without being mistaken for the current
    (fresh) year or leaking into latest/index.json.
    """

    def test_a_restored_prior_year_is_counted_but_never_becomes_latest(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        # Only 2025 is a *fresh* extraction this run.
        _write_fixture(data_dir / "glaciers" / "koshi-2025.geojson", "glaciers", "koshi", 2025, 3)
        # 2024 exists only as an already-merged snapshot — exactly what
        # restore_history.py would have placed there before this run,
        # with no matching raw per-basin file at all.
        _write_fixture(
            data_dir / "glaciers" / "snapshots" / "2024.geojson", "glaciers", "koshi", 2024, 2
        )

        manifest = build_static_bundle(data_dir)

        assert manifest["subjects_by_year"] == {"2024": 2, "2025": 3}
        # latest/ and index.json reflect only the fresh 2025 extraction.
        nepal = gpd.read_file(data_dir / "glaciers" / "latest" / "nepal.geojson")
        assert len(nepal) == 3
        index_entries = json.loads((data_dir / "index.json").read_text())
        assert all(e["year"] == 2025 for e in index_entries)
        # The restored year still gets its own download files.
        assert (data_dir / "downloads" / "glaciers-nepal-2024.geojson").exists()
        assert (data_dir / "downloads" / "glaciers-nepal-2024.csv").exists()

    def test_a_year_with_both_a_restored_snapshot_and_a_fresh_extraction_uses_the_fresh_one(
        self, tmp_path: Path
    ):
        data_dir = tmp_path / "data"
        _write_fixture(data_dir / "glaciers" / "koshi-2025.geojson", "glaciers", "koshi", 2025, 3)
        # A stale leftover snapshot for the *same* year 2025 — e.g. from a
        # re-run — must not be double-counted alongside the fresh one.
        _write_fixture(
            data_dir / "glaciers" / "snapshots" / "2025.geojson", "glaciers", "koshi", 2025, 99
        )

        manifest = build_static_bundle(data_dir)

        assert manifest["subjects_by_year"]["2025"] == 3
