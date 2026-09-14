# HimalWatch

A free, static, public monitoring portal for Nepal's high-altitude
cryosphere — roughly 3,800 glaciers and 2,070 glacial lakes (RGI v7 Region
15 / ICIMOD-scale figures). A weekly GitHub Actions pipeline pulls
Sentinel-2 imagery, extracts glacier and lake outlines, and rebuilds a
static bundle (GeoJSON + PMTiles) that Firebase Hosting serves directly.
No live database, no server cost, no paid services.

## Why this exists

[FP272](https://www.greenclimate.fund/sites/default/files/document/funding-proposal-fp272.pdf)
(UNDP/GCF, $50M, 2025–2032) is funding the official glacier and glacial-lake
inventory for Nepal, run with DHM. That inventory is authoritative but
refreshes on a multi-year cycle. HimalWatch is a **complementary**
observational layer: lightweight weekly Sentinel-2 monitoring that fills
the gap between official updates. It is not an alternative to DHM/ICIMOD
data, does not redistribute ICIMOD data without permission, and never
publishes a GLOF risk score without a documented, human-reviewed
methodology.

## Architecture

```
GitHub Actions (weekly cron)
  → Python pipeline (packages/pipeline)   Sentinel-2 → GeoJSON extraction
  → static bundle (data/)                 GeoJSON, PMTiles, CSV, index.json
  → Firebase Hosting (packages/web)       Next.js static export, MapLibre GL
  → Firebase Auth + Firestore (packages/api)   QA annotations only
```

See [`docs/HIMALWATCH_SPEC.md`](docs/HIMALWATCH_SPEC.md) for the full data
model, filter set, and extraction methodology.

## Packages

- `packages/schema` — shared TypeScript types + Zod schemas for every
  entity in the data model (Glacier, Lake, snapshots, Basin, IndexEntry,
  Alert). The single source of truth both the pipeline's output and the
  web client's expectations are checked against.
- `packages/pipeline` — Python 3.11. Loads reference data (Nepal
  boundaries, RGI glacier baseline), extracts glacier/lake outlines from
  Sentinel-2 per basin per year, and builds the deploy-ready static bundle.
- `packages/web` — Next.js 14 (static export) portal: map, client-side
  filters, glacier/lake detail pages.
- `packages/api` — Firebase Cloud Functions. QA annotation endpoints only;
  every public read is a static file, never a function or database query.

## Getting started

Prerequisites: Node 20+, pnpm (`corepack enable && corepack prepare
pnpm@latest --activate`), Python 3.11+ (managed via
[uv](https://docs.astral.sh/uv/): `uv python install 3.11`),
[tippecanoe](https://github.com/felt/tippecanoe) for PMTiles generation
(`brew install tippecanoe` on macOS).

```bash
pnpm install
pnpm --filter @himalwatch/pipeline exec uv sync

pnpm dev          # Next.js portal at localhost:3000
pnpm pipeline load           # load Nepal boundaries + RGI baseline
pnpm pipeline extract-lakes --basin koshi --year 2025 --dry-run
pnpm pipeline extract-glaciers --basin koshi --year 2025 --dry-run
pnpm pipeline build-static    # assemble data/ into the deploy-ready bundle

pnpm lint
pnpm typecheck
pnpm test
```

## Non-negotiables

- $0/mo running cost. No paid services without explicit discussion.
- Static-first: no live database ever serves public glacier/lake data.
- Never contact ICIMOD, DHM, or UNDP endpoints programmatically without
  human approval, and never redistribute ICIMOD data without written
  permission.
- Never publish a GLOF risk score without a documented methodology and a
  human review step.
- Never commit satellite scenes or Sentinel imagery to the repo.

Full working conventions live in [`CLAUDE.md`](CLAUDE.md).

## Status

Sessions 1–5 of the build (workspace bootstrap → reference data → lake
extraction → glacier extraction + static bundle → web portal) are in this
repo. The weekly cron wiring and first production deploy (prompt-book
Session 6) have not landed yet.
