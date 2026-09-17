from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from himalwatch_pipeline.build.restore_history import restore_history


def _response(status_code: int, json_body: dict | None = None, content: bytes = b"") -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.content = content
    if json_body is not None:
        resp.json.return_value = json_body
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    else:
        resp.raise_for_status.side_effect = None
    return resp


class TestRestoreHistory:
    def test_first_ever_run_with_no_live_site_returns_empty_without_raising(self, tmp_path: Path):
        with patch(
            "himalwatch_pipeline.build.restore_history.requests.get",
            side_effect=requests.ConnectionError("no such host"),
        ):
            result = restore_history(tmp_path, "https://nonexistent.example")
        assert result == {}

    def test_manifest_with_no_years_returns_empty(self, tmp_path: Path):
        with patch(
            "himalwatch_pipeline.build.restore_history.requests.get",
            return_value=_response(200, json_body={"subjects_by_year": {}}),
        ):
            result = restore_history(tmp_path, "https://example.test")
        assert result == {}

    def test_restores_a_snapshot_file_per_type_per_year(self, tmp_path: Path):
        manifest = _response(200, json_body={"subjects_by_year": {"2024": 10, "2025": 12}})
        snapshot_body = json.dumps({"type": "FeatureCollection", "features": []}).encode()

        def _fake_get(url: str, timeout: int):
            if url.endswith("manifest.json"):
                return manifest
            return _response(200, content=snapshot_body)

        with patch("himalwatch_pipeline.build.restore_history.requests.get", side_effect=_fake_get):
            result = restore_history(tmp_path, "https://example.test/")

        assert set(result.keys()) == {
            "glaciers/2024",
            "glaciers/2025",
            "lakes/2024",
            "lakes/2025",
        }
        assert (tmp_path / "glaciers" / "snapshots" / "2024.geojson").read_bytes() == snapshot_body
        assert (tmp_path / "lakes" / "snapshots" / "2025.geojson").read_bytes() == snapshot_body

    def test_one_missing_year_does_not_block_the_others(self, tmp_path: Path):
        manifest = _response(200, json_body={"subjects_by_year": {"2024": 10, "2025": 12}})
        snapshot_body = b'{"type": "FeatureCollection", "features": []}'

        def _fake_get(url: str, timeout: int):
            if url.endswith("manifest.json"):
                return manifest
            if "2024" in url:
                return _response(404)
            return _response(200, content=snapshot_body)

        with patch("himalwatch_pipeline.build.restore_history.requests.get", side_effect=_fake_get):
            result = restore_history(tmp_path, "https://example.test")

        assert "glaciers/2024" not in result
        assert "glaciers/2025" in result
        assert not (tmp_path / "glaciers" / "snapshots" / "2024.geojson").exists()
        assert (tmp_path / "glaciers" / "snapshots" / "2025.geojson").exists()

    def test_strips_trailing_slash_from_site_url(self, tmp_path: Path):
        seen_urls = []

        def _fake_get(url: str, timeout: int):
            seen_urls.append(url)
            if url.endswith("manifest.json"):
                return _response(200, json_body={"subjects_by_year": {}})
            return _response(200)

        with patch("himalwatch_pipeline.build.restore_history.requests.get", side_effect=_fake_get):
            restore_history(tmp_path, "https://example.test///")

        assert seen_urls == ["https://example.test/data/manifest.json"]
