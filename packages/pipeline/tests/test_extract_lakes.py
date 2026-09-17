from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from himalwatch_pipeline.extract.lakes import (
    _asset_href,
    _target_grid,
    compute_mndwi,
    filter_lakes,
    match_to_baseline,
    otsu_threshold,
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


def _rectangle(cx: float, cy: float, half_w: float, half_h: float) -> Polygon:
    return Polygon(
        [
            (cx - half_w, cy - half_h),
            (cx + half_w, cy - half_h),
            (cx + half_w, cy + half_h),
            (cx - half_w, cy + half_h),
        ]
    )


class TestComputeMndwiAndOtsu:
    def test_mndwi_is_positive_over_water_negative_over_land(self):
        # Water: high green, low SWIR. Land: low green, high SWIR.
        green = np.array([[200, 20], [200, 20]], dtype=np.float64)
        swir = np.array([[20, 200], [20, 200]], dtype=np.float64)
        mndwi = compute_mndwi(green, swir)
        assert mndwi[0, 0] > 0  # water pixel
        assert mndwi[0, 1] < 0  # land pixel

    def test_mndwi_handles_zero_denominator_without_raising(self):
        green = np.array([[0.0]])
        swir = np.array([[0.0]])
        mndwi = compute_mndwi(green, swir)
        assert mndwi[0, 0] == 0.0

    def test_otsu_threshold_separates_two_clusters(self):
        water = np.full(100, 0.6)
        land = np.full(100, -0.4)
        mndwi = np.concatenate([water, land])
        threshold = otsu_threshold(mndwi)
        assert -0.4 < threshold < 0.6


class TestFilterLakes:
    """5 hand-crafted candidate polygons — exactly 2 should survive every
    filter in spec §5.2 step 4 (min area, elongation, elevation, glacier
    proximity); the other 3 each fail a single, distinct filter so a
    regression in any one filter shows up as a specific test failure
    elsewhere, not just a changed count here.
    """

    def _glaciers(self) -> gpd.GeoDataFrame:
        # Two glaciers, positioned near good1/good2 but far from
        # `too_far_from_glacier`.
        near_good1 = _square(500_000, 3_100_000, 50)
        near_good2 = _square(505_000, 3_100_000, 50)
        return gpd.GeoDataFrame(
            {"id": ["glacier:1", "glacier:2"]},
            geometry=[near_good1, near_good2],
            crs=_CRS,
        )

    def _candidates(self) -> gpd.GeoDataFrame:
        good1 = _square(500_000, 3_100_100, 60)  # 120x120 = 14400 m², compact
        good2 = _square(505_000, 3_100_100, 60)
        too_small = _square(510_000, 3_100_100, 10)  # 20x20 = 400 m²
        elongated = _rectangle(515_000, 3_100_100, 500, 2.5)  # long thin strip
        too_far_from_glacier = _square(600_000, 3_100_100, 60)  # 60km from any glacier

        return gpd.GeoDataFrame(
            {
                "label": ["good1", "good2", "too_small", "elongated", "too_far"],
            },
            geometry=[good1, good2, too_small, elongated, too_far_from_glacier],
            crs=_CRS,
        )

    def _constant_elevation(self, _point: Point) -> float:
        return 4000.0  # above the 3500m threshold for every candidate

    def test_exactly_two_of_five_survive(self):
        result = filter_lakes(
            self._candidates(),
            dem_elevation_by_point=self._constant_elevation,
            glaciers_baseline=self._glaciers(),
        )
        assert set(result["label"]) == {"good1", "good2"}
        assert len(result) == 2

    def test_too_small_is_dropped_by_area_filter_alone(self):
        candidates = self._candidates()
        only_small_and_good = candidates[candidates["label"].isin(["good1", "too_small"])]
        result = filter_lakes(
            only_small_and_good,
            dem_elevation_by_point=self._constant_elevation,
            glaciers_baseline=self._glaciers(),
        )
        assert list(result["label"]) == ["good1"]

    def test_low_elevation_candidate_is_dropped(self):
        def _low_elevation(_point: Point) -> float:
            return 2000.0  # below the 3500m threshold

        candidates = self._candidates()
        just_good1 = candidates[candidates["label"] == "good1"]
        result = filter_lakes(
            just_good1,
            dem_elevation_by_point=_low_elevation,
            glaciers_baseline=self._glaciers(),
        )
        assert result.empty

    def test_raises_if_not_already_in_utm45n(self):
        wgs84_candidates = self._candidates().set_crs(_CRS, allow_override=True).to_crs("EPSG:4326")
        try:
            filter_lakes(
                wgs84_candidates,
                dem_elevation_by_point=self._constant_elevation,
                glaciers_baseline=self._glaciers(),
            )
            raised = False
        except ValueError:
            raised = True
        assert raised, "filter_lakes should refuse non-EPSG:32645 input, not silently misfilter"


class TestMatchToBaseline:
    """3 previous lakes + 4 current lakes -> 2 should match an existing id
    (centroid within 200m), 2 should get a fresh `lake:gen:` id.
    """

    def _previous(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {"id": ["lake:a", "lake:b", "lake:c"]},
            geometry=[
                _square(500_000, 3_100_000, 30),
                _square(510_000, 3_100_000, 30),
                _square(520_000, 3_100_000, 30),  # this one won't reappear
            ],
            crs=_CRS,
        )

    def _current(self) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {
                "label": ["matches_a", "matches_b", "new_1", "new_2"],
            },
            geometry=[
                _square(500_050, 3_100_050, 30),  # ~70m from lake:a's centroid
                _square(510_100, 3_099_950, 30),  # ~110m from lake:b's centroid
                _square(700_000, 3_100_000, 30),  # nowhere near any previous lake
                _square(800_000, 3_100_000, 30),
            ],
            crs=_CRS,
        )

    def test_two_match_two_are_new(self):
        result = match_to_baseline(self._current(), self._previous())
        by_label = dict(zip(result["label"], result["id"], strict=True))

        assert by_label["matches_a"] == "lake:a"
        assert by_label["matches_b"] == "lake:b"
        assert by_label["new_1"].startswith("lake:gen:")
        assert by_label["new_2"].startswith("lake:gen:")
        assert by_label["new_1"] != by_label["new_2"]

    def test_empty_previous_gives_every_current_feature_a_new_id(self):
        result = match_to_baseline(self._current(), gpd.GeoDataFrame())
        assert all(id_.startswith("lake:gen:") for id_ in result["id"])

    def test_empty_current_returns_empty_with_no_error(self):
        result = match_to_baseline(gpd.GeoDataFrame(geometry=[], crs=_CRS), self._previous())
        assert result.empty

    def test_two_current_features_never_claim_the_same_previous_id(self):
        # Two current features both near lake:a — only the closer one
        # should get "lake:a"; the other must get a new id, not a
        # duplicate.
        previous = gpd.GeoDataFrame(
            {"id": ["lake:a"]}, geometry=[_square(500_000, 3_100_000, 30)], crs=_CRS
        )
        current = gpd.GeoDataFrame(
            {"label": ["closer", "farther"]},
            geometry=[
                _square(500_010, 3_100_010, 30),
                _square(500_050, 3_100_050, 30),
            ],
            crs=_CRS,
        )
        result = match_to_baseline(current, previous)
        by_label = dict(zip(result["label"], result["id"], strict=True))
        assert by_label["closer"] == "lake:a"
        assert by_label["farther"].startswith("lake:gen:")


class _FakeAsset:
    def __init__(self, href: str):
        self.href = href


class TestAssetHref:
    """_asset_href tries several known STAC asset-naming conventions in
    order (see _ASSET_KEY_CANDIDATES) since this hasn't been verified
    against a live CDSE catalog response — these lock down the fallback
    order itself, independent of which naming CDSE turns out to use.
    """

    def test_finds_common_name_key_first(self):
        item = type(
            "Item", (), {"assets": {"green": _FakeAsset("g.tif"), "B03": _FakeAsset("b03.tif")}}
        )()
        assert _asset_href(item, "green") == "g.tif"

    def test_falls_back_to_raw_band_id(self):
        item = type("Item", (), {"assets": {"B03": _FakeAsset("b03.tif")}})()
        assert _asset_href(item, "green") == "b03.tif"

    def test_returns_none_rather_than_raising_when_nothing_matches(self):
        item = type("Item", (), {"assets": {"unrelated": _FakeAsset("x.tif")}})()
        assert _asset_href(item, "green") is None


class TestTargetGrid:
    """A basin bbox near Everest (comfortably inside UTM zone 45N) ->
    _target_grid should produce a 10m-resolution EPSG:32645 grid whose
    extent covers that bbox.
    """

    def test_pixel_size_matches_composite_resolution(self):
        transform, shape_ = _target_grid((86.8, 27.9, 86.9, 28.0))
        # Not exact: transform_from_bounds distributes whatever fraction
        # of a pixel the bbox doesn't evenly divide into across the
        # width/height, so pixel size is only approximately 10m — that's
        # correct, not a bug. 1% tolerance is generous enough to catch a
        # real regression (e.g. someone changing _COMPOSITE_RESOLUTION_M
        # or the rounding) while tolerating that snapping.
        assert transform.a == pytest.approx(10.0, rel=0.01)
        assert transform.e == pytest.approx(-10.0, rel=0.01)
        assert shape_[0] > 0 and shape_[1] > 0

    def test_larger_bbox_produces_a_larger_grid(self):
        _, small_shape = _target_grid((86.80, 27.90, 86.81, 27.91))
        _, big_shape = _target_grid((86.5, 27.5, 87.0, 28.0))
        assert big_shape[0] > small_shape[0]
        assert big_shape[1] > small_shape[1]

    def test_degenerate_bbox_still_returns_at_least_one_pixel(self):
        _, shape_ = _target_grid((86.8, 27.9, 86.8, 27.9))
        assert shape_ == (1, 1)
