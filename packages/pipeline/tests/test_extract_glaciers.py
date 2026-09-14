from __future__ import annotations

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

from himalwatch_pipeline.extract.glaciers import (
    apply_slope_mask,
    compute_ndsi,
    constrain_to_baseline,
    match_to_rgi,
)

_CRS = "EPSG:32645"


def _square(cx: float, cy: float, half_side: float) -> Polygon:
    return Polygon(
        [
            (cx - half_side, cy - half_side),
            (cx + half_side, cy - half_side),
            (cx + half_side, cy + half_side),
            (cx - half_side, cy + half_side),
        ]
    )


class TestComputeNdsi:
    def test_ndsi_is_positive_over_snow_ice_negative_over_bare_rock(self):
        green = np.array([[220, 30]], dtype=np.float64)
        swir = np.array([[30, 220]], dtype=np.float64)
        ndsi = compute_ndsi(green, swir)
        assert ndsi[0, 0] > 0  # snow/ice pixel
        assert ndsi[0, 1] < 0  # bare rock pixel


class TestApplySlopeMask:
    def test_steep_pixels_are_excluded_regardless_of_ndsi(self):
        ndsi_binary = np.array([[True, True], [True, True]])
        slope_deg = np.array([[10.0, 50.0], [44.9, 45.0]])
        result = apply_slope_mask(ndsi_binary, slope_deg)
        assert result.tolist() == [[True, False], [True, False]]


class TestConstrainToBaseline:
    def test_candidate_outside_buffered_baseline_is_dropped_entirely(self):
        baseline = gpd.GeoDataFrame(
            {"rgi_id": ["RGI60-15.1"]},
            geometry=[_square(500_000, 3_100_000, 100)],
            crs=_CRS,
        )
        far_candidate = gpd.GeoDataFrame(
            {"label": ["far"]}, geometry=[_square(600_000, 3_100_000, 50)], crs=_CRS
        )
        result = constrain_to_baseline(far_candidate, baseline, buffer_m=200)
        assert result.empty

    def test_candidate_extending_past_buffer_is_clipped_not_dropped(self):
        baseline = gpd.GeoDataFrame(
            {"rgi_id": ["RGI60-15.1"]},
            geometry=[_square(500_000, 3_100_000, 100)],
            crs=_CRS,
        )
        # Extends 500m past the buffered baseline edge (100 + 200 = 300m
        # from center) — should survive but shrink to the buffered extent.
        overextended = gpd.GeoDataFrame(
            {"label": ["overextended"]},
            geometry=[_square(500_000, 3_100_000, 800)],
            crs=_CRS,
        )
        result = constrain_to_baseline(overextended, baseline, buffer_m=200)
        assert len(result) == 1
        assert result.iloc[0].geometry.area < overextended.iloc[0].geometry.area

    def test_raises_if_not_already_in_utm45n(self):
        baseline = gpd.GeoDataFrame(
            {"rgi_id": ["RGI60-15.1"]}, geometry=[_square(500_000, 3_100_000, 100)], crs=_CRS
        )
        wgs84_candidate = gpd.GeoDataFrame(
            {"label": ["x"]}, geometry=[_square(500_000, 3_100_000, 50)], crs=_CRS
        ).to_crs("EPSG:4326")
        try:
            constrain_to_baseline(wgs84_candidate, baseline)
            raised = False
        except ValueError:
            raised = True
        assert raised


class TestMatchToRgi:
    def test_candidate_near_baseline_gets_its_rgi_id(self):
        baseline = gpd.GeoDataFrame(
            {"rgi_id": ["RGI60-15.1", "RGI60-15.2"]},
            geometry=[
                _square(500_000, 3_100_000, 50),
                _square(510_000, 3_100_000, 50),
            ],
            crs=_CRS,
        )
        candidates = gpd.GeoDataFrame(
            {"label": ["near_1", "near_2"]},
            geometry=[
                _square(500_020, 3_100_020, 50),
                _square(510_030, 3_099_980, 50),
            ],
            crs=_CRS,
        )
        result = match_to_rgi(candidates, baseline, max_distance_m=500)
        by_label = dict(zip(result["label"], result["rgi_id"], strict=True))
        assert by_label["near_1"] == "RGI60-15.1"
        assert by_label["near_2"] == "RGI60-15.2"
        assert all(id_.startswith("glacier:RGI60-15.") for id_ in result["id"])

    def test_candidate_far_from_any_baseline_is_dropped_not_fabricated(self):
        baseline = gpd.GeoDataFrame(
            {"rgi_id": ["RGI60-15.1"]},
            geometry=[_square(500_000, 3_100_000, 50)],
            crs=_CRS,
        )
        candidates = gpd.GeoDataFrame(
            {"label": ["near", "far"]},
            geometry=[
                _square(500_020, 3_100_020, 50),
                _square(900_000, 3_100_000, 50),
            ],
            crs=_CRS,
        )
        result = match_to_rgi(candidates, baseline, max_distance_m=500)
        assert list(result["label"]) == ["near"]
