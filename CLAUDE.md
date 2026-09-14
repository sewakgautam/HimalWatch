# HimalWatch — Nepal Cryosphere Monitoring

## What this is
Nepal High-Altitude Glacier & Glacial Lake Monitoring and Inventory System.
Weekly Sentinel-2 pipeline → static GeoJSON + PMTiles → Firebase-hosted portal.
Positioned as complementary observational monitoring to FP272 (UNDP/GCF/DHM $50M project).
Public tool for tracking Nepal's ~3,800 glaciers and ~2,070 glacial lakes.

## Non-negotiables
- $0/mo running cost. No paid services without discussion.
- Static-first architecture. No live database for public data.
- Firebase Hosting + Auth + Firestore (QA annotations only) + GitHub Actions cron.
- Never contact ICIMOD, DHM, or UNDP endpoints programmatically without human approval.
- Never redistribute ICIMOD data without written permission.
- Never publish a "GLOF risk score" without documented methodology and caveats.
- Never commit satellite scenes or Sentinel imagery to the repo (large + licensed).

## Stack
- Pipeline: Python 3.11, GEE Python API (or Copernicus Data Space), rasterio, geopandas, shapely, pysheds
- Frontend: Next.js 14 (static export), MapLibre GL, PMTiles
- Types: shared TypeScript in `packages/schema`
- Package manager: pnpm workspaces
- Testing: pytest for pipeline, vitest for web
- Formatting: ruff + black (Python), prettier + eslint (TS)
- Commits: Conventional Commits

## Repo layout
- `packages/pipeline/` — Python extraction and static bundle builder
- `packages/web/` — Next.js portal
- `packages/schema/` — shared TS types + Zod schemas
- `packages/api/` — Firebase Cloud Functions (QA endpoints only; public reads are static)
- `.github/workflows/` — weekly cron pipeline
- `docs/` — spec, methodology, FP272 alignment brief
- `data/` — generated static bundle (git-ignored except structure)

## Data model
Full attribute schemas in `docs/HIMALWATCH_SPEC.md` §2.
- Glacier: rgi_id, name, geom, basin, province, district, elevation_{min,max,mean}, area_current_km2, area_2000_km2, area_change_pct_since_2000, debris_covered, sla_current_m, associated_lake_ids, confidence
- Lake: icimod_id, name, geom, basin, province, district, elevation_m, area_current_km2, area_2000_km2, area_change_pct_since_2000, dam_type, glof_risk, is_pdgl, parent_glacier_id, outburst_history, confidence

## Filters (all client-side)
Shared: province, basin, sub-basin, district, elevation range, area range, year, change since 2000, confidence, free text.
Lake-only: GLOF risk, dam type, PDGL toggle, outburst history, downstream population.
Glacier-only: debris-covered, has associated lakes, SLA trend.
URL-encoded state so filter combinations are shareable.

## Working conventions
- Type hints everywhere in Python. TypeScript everywhere in web.
- Every pipeline function that emits geometry writes GeoJSON `FeatureCollection` with EPSG:4326 coords.
- Areas computed in EPSG:32645 (UTM 45N covers Nepal).
- Confidence: `high` if cloud_pct < 10, `medium` if < 30, `low` otherwise.
- Every generated file goes in `data/` and is regeneratable. Don't hand-edit.
- Every commit under Conventional Commits (feat/fix/chore/docs/refactor/test).
- Every phase ends with a runnable demo. If the frontend can't render what the pipeline just produced, the phase isn't done.

## What Claude Code should NOT do
- Do not add paid services or cloud accounts.
- Do not commit satellite scenes or large binary assets.
- Do not deploy to production DNS without an explicit "deploy" command from me.
- Do not scrape ICIMOD or UNDP portals.
- Do not assume debris-covered glacier extraction works — flag as low confidence, defer.
- Do not compute or publish a public GLOF risk score without checking with me first.
- Do not switch to Firestore for lake/glacier data even if it seems simpler.

## Reference documents
- `docs/HIMALWATCH_SPEC.md` — full technical spec (data model, methodology, phases)
- `docs/himalwatch-prototype.html` — v0 prototype with live GLIMS WMS integration
- FP272 funding proposal: https://www.greenclimate.fund/sites/default/files/document/funding-proposal-fp272.pdf
- GLIMS WMS: https://www.glims.org/geoserver/ows

## The FP272 context
UNDP/GCF FP272 ($50M, 2025-2032) is doing the official inventory work with DHM.
Their inventory refreshes every 5 years. HimalWatch fills the between-updates gap
with weekly Sentinel-2 monitoring. This is a complementary tool, not a competitor.
Never frame HimalWatch as an alternative to DHM/ICIMOD data.
