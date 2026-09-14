"""ICIMOD baseline lake inventory + PDGL list — BLOCKED pending permission.

Requires written permission from ICIMOD before this loader fetches
anything (see CLAUDE.md's non-negotiables: "Never redistribute ICIMOD
data without written permission" and "Never contact ICIMOD, DHM, or UNDP
endpoints programmatically without human approval"). Once permission is
received, this module should load:

  - the 2018 baseline glacial lake inventory -> data/reference/lakes_baseline.geojson
  - the 2020 Potentially Dangerous Glacial Lake (PDGL) list -> data/reference/pdgls.geojson

Until then, this writes empty FeatureCollections so downstream code
(matching, enrichment, the static bundle builder) doesn't have to
special-case "baseline not loaded yet" — every Lake's `area_2000_km2`,
`dam_type`, and `is_pdgl` simply stay at the "unknown" defaults described
in docs/HIMALWATCH_SPEC.md §2.2 / §5.5.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_EMPTY_FEATURE_COLLECTION = {"type": "FeatureCollection", "features": []}


def load_icimod_lakes(out_dir: Path) -> dict[str, int]:
    logger.warning(
        "ICIMOD baseline import is blocked pending written permission — "
        "writing empty placeholders for lakes_baseline.geojson and "
        "pdgls.geojson. See this module's docstring before changing that."
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    lakes_path = out_dir / "lakes_baseline.geojson"
    pdgls_path = out_dir / "pdgls.geojson"
    for path in (lakes_path, pdgls_path):
        path.write_text(json.dumps(_EMPTY_FEATURE_COLLECTION, indent=2))

    return {"lakes_baseline": 0, "pdgls": 0}
