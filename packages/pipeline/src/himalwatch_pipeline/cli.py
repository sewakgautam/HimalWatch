"""HimalWatch pipeline CLI. See docs/HIMALWATCH_SPEC.md §7 for the phases
this implements."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from dotenv import load_dotenv

from .extract.lakes import extract_lakes
from .loaders.load_boundaries import load_boundaries
from .loaders.load_icimod_lakes import load_icimod_lakes
from .loaders.load_rgi import load_rgi

load_dotenv()

app = typer.Typer(help="HimalWatch Sentinel-2 extraction pipeline.")

# Repo root is four levels up from this file:
# packages/pipeline/src/himalwatch_pipeline/cli.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DATA_DIR = _REPO_ROOT / "data"
_REFERENCE_DIR = _DATA_DIR / "reference"


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def load(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Loads reference data: Nepal boundaries, RGI glacier baseline, and
    the (currently blocked/empty) ICIMOD lake baseline placeholder.
    """
    _configure_logging(verbose)
    logger = logging.getLogger(__name__)

    boundary_counts = load_boundaries(_REFERENCE_DIR)
    typer.echo(
        f"Boundaries: {boundary_counts['provinces']} provinces, "
        f"{boundary_counts['districts']} districts, "
        f"{boundary_counts['basins']} basins"
    )

    glacier_count = load_rgi(_REFERENCE_DIR, _REFERENCE_DIR)
    typer.echo(f"Glaciers (RGI baseline): {glacier_count}")

    lake_counts = load_icimod_lakes(_REFERENCE_DIR)
    typer.echo(
        f"Lakes baseline: {lake_counts['lakes_baseline']} "
        f"(blocked pending ICIMOD permission — see loaders/load_icimod_lakes.py)"
    )
    typer.echo(f"PDGLs: {lake_counts['pdgls']} (same block)")

    logger.info("Reference data written to %s", _REFERENCE_DIR)


@app.command(name="extract-lakes")
def extract_lakes_command(
    basin: str = typer.Option(..., "--basin", help="Basin id, e.g. koshi"),
    year: int = typer.Option(..., "--year", help="Extraction year"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Skip the real Sentinel-2 pull and write synthetic lakes instead — "
        "for wiring up downstream stages without Copernicus credentials.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Extracts glacial lakes for one basin/year from a Sentinel-2
    post-monsoon composite. See docs/HIMALWATCH_SPEC.md §5.2.
    """
    _configure_logging(verbose)
    out_path = _DATA_DIR / "lakes" / f"{basin}-{year}.geojson"
    count = extract_lakes(
        basin=basin,
        year=year,
        out_path=out_path,
        reference_dir=_REFERENCE_DIR,
        dry_run=dry_run,
    )
    typer.echo(f"Wrote {count} lakes to {out_path}")


if __name__ == "__main__":
    app()
