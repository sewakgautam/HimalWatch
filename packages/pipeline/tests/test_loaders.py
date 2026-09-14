from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon

from himalwatch_pipeline.loaders.basins import basin_for_district
from himalwatch_pipeline.loaders.load_boundaries import enrich_districts


class TestBasinForDistrict:
    def test_exact_match(self):
        assert basin_for_district("Kathmandu") == "koshi"
        assert basin_for_district("Kaski") == "gandaki"
        assert basin_for_district("Surkhet") == "karnali"
        assert basin_for_district("Kanchanpur") == "mahakali"

    def test_alias_match(self):
        # geoBoundaries-specific spelling variants -> canonical name
        assert basin_for_district("Baijura") == basin_for_district("Bajura")
        assert basin_for_district("Dadeidhura") == basin_for_district("Dadeldhura")
        assert basin_for_district("Chitawan") == basin_for_district("Chitwan")

    def test_pre_split_district_resolves_to_same_basin_as_both_halves(self):
        # 2006-era datasets have one "Nawalparasi" feature; both post-2015
        # halves are Gandaki, so the pre-split name must resolve the same.
        assert basin_for_district("Nawalparasi") == "gandaki"
        assert basin_for_district("Nawalparasi West") == "gandaki"
        assert basin_for_district("Nawalparasi East") == "gandaki"

    def test_whitespace_is_normalized(self):
        assert basin_for_district("  Kathmandu  ") == "koshi"
        assert basin_for_district("Kathmandu\n") == "koshi"

    def test_unmatched_district_returns_none_rather_than_guessing(self):
        assert basin_for_district("Not A Real District") is None


class TestEnrichDistricts:
    """Small hand-crafted fixtures: two square provinces side by side, and
    three districts — two cleanly inside one province each, one straddling
    the province boundary to exercise the largest-overlap join.

    Coordinates are real Nepal-scale lng/lat (not a toy unit square) —
    `enrich_districts` reprojects to EPSG:32645 (UTM 45N, valid for
    ~lng 78-84°E) to compare overlap areas per CLAUDE.md's area-computation
    convention, and UTM 45N distorts a unit square near (0,0) so badly the
    area comparison becomes meaningless (or NaN) — this only exercises that
    code path realistically with coordinates actually inside the zone.
    """

    def _provinces(self) -> gpd.GeoDataFrame:
        west = Polygon([(80, 28), (83, 28), (83, 29), (80, 29)])
        east = Polygon([(83, 28), (86, 28), (86, 29), (83, 29)])
        return gpd.GeoDataFrame(
            {"name": ["Karnali", "Bagmati"]},
            geometry=[west, east],
            crs="EPSG:4326",
        )

    def test_district_fully_inside_one_province(self):
        district = Polygon([(80.5, 28.2), (82, 28.2), (82, 28.8), (80.5, 28.8)])
        districts = gpd.GeoDataFrame({"name": ["Surkhet"]}, geometry=[district], crs="EPSG:4326")
        result = enrich_districts(districts, self._provinces())
        row = result.iloc[0]
        assert row["province"] == "Karnali"
        assert row["basin"] == "karnali"

    def test_district_straddling_boundary_assigned_to_larger_overlap(self):
        # Spans lng 81.5-83.5: 1.5° west of the lng=83 boundary, 0.5° east
        # of it -> should join to the west province (Karnali), not the
        # east one, despite touching both.
        district = Polygon([(81.5, 28.2), (83.5, 28.2), (83.5, 28.8), (81.5, 28.8)])
        districts = gpd.GeoDataFrame({"name": ["Straddler"]}, geometry=[district], crs="EPSG:4326")
        result = enrich_districts(districts, self._provinces())
        assert result.iloc[0]["province"] == "Karnali"

    def test_unmapped_district_name_gets_null_basin_not_a_guess(self):
        district = Polygon([(80.5, 28.2), (82, 28.2), (82, 28.8), (80.5, 28.8)])
        districts = gpd.GeoDataFrame(
            {"name": ["Definitely Not A District"]},
            geometry=[district],
            crs="EPSG:4326",
        )
        result = enrich_districts(districts, self._provinces())
        assert result.iloc[0]["basin"] is None
        # Province assignment is independent of the basin map, so it
        # should still resolve via the spatial join.
        assert result.iloc[0]["province"] == "Karnali"
