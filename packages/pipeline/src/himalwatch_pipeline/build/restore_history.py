"""Restores prior years' snapshot files from the live deployed site before
a fresh pipeline run.

Every CI run starts from a bare checkout: `data/` is deliberately
gitignored (see CLAUDE.md — generated files aren't version-controlled),
and nothing else persists it between runs. Left alone, that means every
run only ever knows about whatever year it extracts *this* time — prior
years are silently lost, not accumulated, even though the pipeline
otherwise behaves as if it were building up multi-year history.

Since the live site already publicly serves the entire `data/` tree
(Next's `public/data` symlink -> repo root `data/`), the fix doesn't need
any new infrastructure: fetch last run's already-merged per-year snapshot
files straight from the site itself, before running anything else. Still
$0/mo, still no database.

This only restores `snapshots/{year}.geojson` — the already-merged,
across-every-basin files — not the raw per-basin extraction inputs. A
restored year is treated as closed history: `build_static_bundle` folds
its count into `subjects_by_year` and regenerates its download files, but
it never contributes to `latest/` or `index.json` (which only ever
reflect the freshly-extracted current year) and can't be re-split back
into per-basin files.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_TIMEOUT_S = 30


def restore_history(data_dir: Path, site_url: str) -> dict[str, int]:
    """Downloads every year currently listed in the live site's
    manifest.json into data/{glaciers,lakes}/snapshots/{year}.geojson.

    Never raises on a missing/unreachable site — the very first-ever run
    (nothing deployed yet) has nothing to restore, and that's a normal
    state, not an error.
    """
    site_url = site_url.rstrip("/")
    manifest_url = f"{site_url}/data/manifest.json"
    try:
        resp = requests.get(manifest_url, timeout=_TIMEOUT_S)
        resp.raise_for_status()
        manifest = resp.json()
    except requests.RequestException as exc:
        logger.warning(
            "Could not fetch %s (%s) — nothing to restore, treating this as the "
            "first-ever run",
            manifest_url,
            exc,
        )
        return {}

    years = sorted(manifest.get("subjects_by_year", {}).keys())
    if not years:
        logger.info("Live manifest has no years on record — nothing to restore")
        return {}

    restored: dict[str, int] = {}
    for subject_type in ("glaciers", "lakes"):
        for year in years:
            url = f"{site_url}/data/{subject_type}/snapshots/{year}.geojson"
            dest = data_dir / subject_type / "snapshots" / f"{year}.geojson"
            try:
                resp = requests.get(url, timeout=_TIMEOUT_S)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("Could not restore %s (%s) — skipping", url, exc)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            restored[f"{subject_type}/{year}"] = len(resp.content)
            logger.info("Restored %s <- %s", dest, url)

    return restored
