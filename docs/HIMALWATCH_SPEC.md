# HimalWatch — Technical Spec

> **Provenance note:** this document was reconstructed from the HimalWatch
> Claude Code Prompt Book (the ordered session prompts used to build this
> repo) rather than copied from a pre-existing spec — the original
> `HIMALWATCH_SPEC.md` and `himalwatch-prototype.html` referenced by the
> prompt book were never placed in this repo before Session 1 ran. Every
> field, filter, and methodology step below is taken directly from what the
> prompt book specifies inline; the district→basin mapping in §2.4 and the
> visual design in §6 are the two places this doc had to make a best-effort
> call rather than quote a source — both are flagged where they appear.
> Replace this note (and the two flagged sections) if the real spec and
> prototype surface later.

## 1. Overview

HimalWatch is a static, public, $0/mo monitoring portal for Nepal's
high-altitude cryosphere: ~3,800 glaciers (RGI v7 Region 15, Nepal subset)
and ~2,070 glacial lakes. A weekly GitHub Actions pipeline pulls Sentinel-2
composites, extracts glacier/lake outlines, and rebuilds a static bundle
(GeoJSON + PMTiles) that Firebase Hosting serves directly — no live
database, no server-rendered pages for public data.

HimalWatch is **complementary** to FP272 (UNDP/GCF/DHM, $50M, 2025–2032),
which produces the official 5-yearly glacier/lake inventory. HimalWatch
fills the gap *between* those updates with lightweight weekly monitoring.
It is never framed as a replacement for DHM/ICIMOD data, and never
redistributes ICIMOD data without written permission.

## 2. Data model

All geometry fields are GeoJSON `Polygon`/`MultiPolygon` in EPSG:4326. All
area computations happen in EPSG:32645 (UTM 45N, which covers all of
Nepal) and are then stored in km². Confidence is a derived field:
`high` if the source composite's cloud coverage over the feature was
`< 10%`, `medium` if `< 30%`, `low` otherwise (or whenever a filter step
had to fall back to a weaker heuristic — e.g. debris-covered glacier ice,
see §5.3).

### 2.1 Glacier

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable internal id, `glacier:{rgi_id}` |
| `rgi_id` | string | Randolph Glacier Inventory v7 id, e.g. `RGI2000-v7.0-G-15-12345` |
| `name` | string \| null | From RGI if present, else null |
| `geom` | GeoJSON geometry | Current-year outline |
| `basin` | string | One of `koshi` \| `gandaki` \| `karnali` \| `mahakali` |
| `sub_basin` | string \| null | Populated once sub-basin boundaries are loaded (post-MVP) |
| `province` | string | Province name |
| `district` | string | District name |
| `elevation_min_m` | number \| null | From Copernicus GLO-30 DEM |
| `elevation_max_m` | number \| null | |
| `elevation_mean_m` | number \| null | |
| `area_current_km2` | number | Latest extraction |
| `area_2000_km2` | number | RGI baseline area (RGI's inventory date is ~2000-era for Region 15) |
| `area_change_pct_since_2000` | number | `(area_current - area_2000) / area_2000 * 100` |
| `debris_covered` | boolean | From RGI attribute; extraction confidence is always capped at `low` for these (see §5.3) |
| `sla_current_m` | number \| null | Snow line altitude, current year; null until Phase 2 |
| `terminus_point` | GeoJSON Point \| null | Lowest-elevation point of the outline |
| `associated_lake_ids` | string[] | Lakes within 1km whose `parent_glacier_id` points back here |
| `confidence` | `"high"` \| `"medium"` \| `"low"` | |
| `year` | number | Extraction year this record reflects |
| `updated_at` | ISO 8601 string | |

### 2.2 Lake

| Field | Type | Notes |
|---|---|---|
| `id` | string | `lake:{icimod_id}` if known, else `lake:gen:{stable_hash}` |
| `icimod_id` | string \| null | Null until the ICIMOD baseline import (§5.5 — blocked pending permission) |
| `name` | string \| null | |
| `geom` | GeoJSON geometry | Current-year outline |
| `basin` | string | Same enum as Glacier |
| `sub_basin` | string \| null | |
| `province` | string | |
| `district` | string | |
| `elevation_m` | number | Sampled at centroid from DEM |
| `area_current_km2` | number | |
| `area_2000_km2` | number \| null | Null until the ICIMOD 2018 baseline import supplies a pre-2000/2000-era reference; do not backfill from extraction |
| `area_change_pct_since_2000` | number \| null | Same null condition as `area_2000_km2` |
| `dam_type` | `"moraine"` \| `"ice"` \| `"bedrock"` \| `"unknown"` | `"unknown"` until ICIMOD baseline import; never inferred from imagery alone |
| `glof_risk` | `"low"` \| `"medium"` \| `"high"` \| `"unassessed"` | **Never** set to anything but `"unassessed"` by the automated pipeline — see CLAUDE.md's non-negotiables. A real value only ever comes from a human-reviewed QA annotation. |
| `is_pdgl` | boolean | Potentially Dangerous Glacial Lake, per ICIMOD's 2020 PDGL list. `false` until that list is imported |
| `parent_glacier_id` | string \| null | Nearest glacier within 1km, if any |
| `outburst_history` | `{ year: number; note: string }[]` | Empty until manually curated |
| `downstream_population` | number \| null | Post-MVP; requires a population raster join |
| `confidence` | `"high"` \| `"medium"` \| `"low"` | |
| `year` | number | |
| `updated_at` | ISO 8601 string | |

### 2.3 Snapshots (`GlacierSnapshot` / `LakeSnapshot`)

One row per subject per extraction year — the time series the detail-page
area chart reads. No geometry (keeps these tiny; the outline for a given
year lives in `data/{glaciers,lakes}/snapshots/{year}.geojson` instead).

| Field | Type | Notes |
|---|---|---|
| `subject_id` | string | Matches `Glacier.id` / `Lake.id` |
| `subject_type` | `"glacier"` \| `"lake"` | |
| `year` | number | |
| `area_km2` | number | |
| `elevation_mean_m` | number \| null | Glacier only |
| `elevation_m` | number \| null | Lake only |
| `confidence` | `"high"` \| `"medium"` \| `"low"` | |
| `cloud_pct` | number | Cloud coverage over this feature in the source composite |

### 2.4 Basin

Dissolved from districts. **Best-effort district→basin mapping** (flagged
per the provenance note above) — Nepal's real watershed boundaries are
finer-grained than district lines; this mapping approximates each district
to whichever of the four major basins its majority area drains into, and
should be replaced with a real watershed shapefile (e.g. HydroSHEDS/HydroBASINS
for Nepal) as soon as one is loaded. Districts are grouped west→east:

- **Mahakali**: Darchula, Baitadi, Dadeldhura, Kanchanpur
- **Karnali**: Bajhang, Bajura, Achham, Doti, Kailali, Humla, Mugu, Kalikot,
  Jumla, Dailekh, Surkhet, Dolpa, Jajarkot, Salyan, Rukum West, Rukum East,
  Banke, Bardiya
- **Gandaki**: Rolpa, Pyuthan, Gulmi, Arghakhanchi, Kapilvastu, Rupandehi,
  Nawalparasi West, Nawalparasi East, Palpa, Baglung, Myagdi, Mustang,
  Manang, Kaski, Parbat, Syangja, Tanahun, Gorkha, Lamjung, Nawalpur,
  Chitwan, Makwanpur
- **Koshi**: everything east of and including Kathmandu Valley —
  Dhading, Nuwakot, Rasuwa, Kathmandu, Bhaktapur, Lalitpur, Sindhupalchok,
  Kavrepalanchok, Dolakha, Ramechhap, Sindhuli, Okhaldhunga, Khotang,
  Bhojpur, Solukhumbu, Sankhuwasabha, Taplejung, Panchthar, Ilam,
  Jhapa, Morang, Sunsari, Dhankuta, Terhathum, Udayapur, Saptari, Siraha,
  Mahottari, Dhanusa, Sarlahi, Rautahat, Bara, Parsa

| Field | Type |
|---|---|
| `id` | string (`koshi` \| `gandaki` \| `karnali` \| `mahakali`) |
| `name` | string |
| `name_ne` | string |
| `geom` | GeoJSON geometry (dissolved district union) |

### 2.5 IndexEntry

The flat, geometry-free array the web client loads once (`data/index.json`)
and filters entirely client-side. One entry per Glacier or per Lake —
every field from §2.1/§2.2 **except** `geom` and `terminus_point`, plus:

| Field | Type | Notes |
|---|---|---|
| `type` | `"glacier"` \| `"lake"` | Discriminator |
| `centroid` | `[number, number]` | `[lng, lat]`, for label placement / search-result flyTo |

### 2.6 Alert

Reserved for Phase 2+ (not built in Sessions 1–5). A detected
week-over-week change worth surfacing — e.g. a lake's area growing beyond
a threshold, or a new feature appearing. Never auto-populates `glof_risk`;
an Alert is a prompt for human QA review, not a public risk claim.

| Field | Type |
|---|---|
| `id` | string |
| `subject_id` | string |
| `subject_type` | `"glacier"` \| `"lake"` |
| `kind` | `"rapid_area_change"` \| `"new_feature"` \| `"low_confidence_review"` |
| `severity` | `"info"` \| `"warning"` |
| `message` | string |
| `year` | number |
| `created_at` | ISO 8601 string |

## 3. Filters

All filtering happens client-side over `index.json` (see §2.5). Filter
state is URL-encoded (e.g. `?province=1,3&basin=koshi&elev_min=4000`) so
any filter combination is a shareable link.

**Shared** (both glaciers and lakes): province, basin, sub-basin, district,
elevation range, area range, year, change-since-2000 range, confidence,
free-text name search.

**Lake-only**: GLOF risk, dam type, PDGL toggle, outburst history
(has-history toggle), downstream population range.

**Glacier-only**: debris-covered toggle, has-associated-lakes toggle, SLA
trend (post-MVP, hidden until `sla_current_m` has ≥2 years of history).

## 4. Architecture

```
GitHub Actions (weekly cron)
  → Python pipeline (packages/pipeline)
      loaders/         one-time or rarely-refreshed reference data
      extract/         per-basin, per-year Sentinel-2 → GeoJSON
      build/           merges extractions into the deploy-ready bundle
  → data/ (static bundle: GeoJSON, PMTiles, CSV, index.json, manifest.json)
  → Firebase Hosting (packages/web, Next.js static export)
  → Firebase Auth + Firestore (packages/api) — QA annotation only,
    never a path for public glacier/lake data
```

No public read ever touches a database. Firestore exists solely so a
signed-in reviewer can attach QA notes (e.g. confirming/correcting a
`confidence: low` extraction) — those annotations are periodically folded
back into the static bundle by the pipeline, not read live by the public site.

## 5. Extraction methodology

### 5.1 Compositing

For a given basin and year, build a cloud-masked Sentinel-2 median
composite using the SCL band to mask clouds/shadows/snow-ambiguous pixels.

- **Lakes**: post-monsoon window, Oct 1 – Nov 30 (lowest seasonal cloud
  cover, lake levels stabilized after monsoon inflow).
- **Glaciers**: late-ablation window, Sep 1 – Oct 31 (minimizes seasonal
  snow being mistaken for glacier ice; closest to annual minimum extent).

Log the composite's cloud coverage percentage — this directly drives the
`confidence` field (§2, cutoffs `<10%` high / `<30%` medium / else low).

### 5.2 Lake extraction

1. **MNDWI** = `(Green − SWIR) / (Green + SWIR)`.
2. **Otsu threshold** the MNDWI raster (`skimage.filters.threshold_otsu`)
   to get a binary water mask — adaptive per composite rather than a fixed
   cutoff, since glacial lake spectral response varies with sediment load.
3. **Vectorize** the binary mask into polygons.
4. **Filter**:
   - elevation (from DEM) `> 3500m`
   - within `1km` of a baseline glacier polygon
   - minimum area `3000 m²`
   - elongation ratio `perimeter² / area < 40` (drops river/stream segments,
     which are long and thin relative to their area — a compact lake has
     a much lower ratio)
5. **Enrich**: province/district/basin via spatial join, `parent_glacier_id`
   from the nearest baseline glacier, `elevation_m` sampled at centroid.
6. **Match to baseline**: centroid distance `< 200m` to the prior year's
   extraction preserves a stable internal id across years; anything
   unmatched is a new `lake:gen:{hash}` entry.

### 5.3 Glacier extraction

1. **NDSI** = `(Green − SWIR) / (Green + SWIR)` — same band pair as MNDWI;
   the difference is thresholding and downstream filtering, not the index
   itself. Threshold at `0.4`.
2. **Slope mask**: exclude slopes `≥ 45°` (from the DEM) — steep faces
   produce spurious snow/ice signal that isn't glacier body.
3. **Constrain to baseline**: intersect with the RGI baseline outline
   buffered by `200m` (glaciers only retreat over the monitoring window;
   this buffer accommodates extraction noise, not real advance).
4. **Match to RGI ID** for stable identity across extraction years.
5. **Confidence override**: any glacier flagged `debris_covered=true` in
   the RGI baseline is capped at `confidence: "low"` regardless of cloud
   cover — debris-covered ice has a spectral signature close to
   surrounding moraine/rock, and this pipeline does not attempt to solve
   that (see CLAUDE.md: "Do not assume debris-covered glacier extraction
   works — flag as low confidence, defer.").

### 5.4 Confidence

```
if cloud_pct < 10: confidence = "high"
elif cloud_pct < 30: confidence = "medium"
else: confidence = "low"

# glaciers only, applied after the above:
if debris_covered: confidence = "low"
```

### 5.5 ICIMOD baseline data (blocked)

The 2018 lake inventory baseline and the 2020 PDGL list are ICIMOD
products. **Do not fetch, scrape, or redistribute these without written
permission.** Until permission is granted, `lakes_baseline.geojson` and
`pdgls.geojson` are empty `FeatureCollection`s and every Lake's
`area_2000_km2`, `dam_type`, and `is_pdgl` stay at their "unknown" defaults
described in §2.2. This is a real, not cosmetic, gap in the current bundle.

## 6. Portal design language

**Best-effort reconstruction** (flagged per the provenance note above) —
the actual prototype (`himalwatch-prototype.html`) wasn't available, so
this is inferred from the palette CLAUDE.md specifies rather than copied
from a working design:

- Header: deep navy (`#1a2e3b`), bilingual title (हिमताल र हिमनदी अनुगमन /
  "Glacier & Glacial Lake Monitoring"), Noto Sans Devanagari for Nepali text.
- Background: off-white (`#f5f5f0`).
- Map layer colors: glaciers teal, lakes purple, PDGL lakes red (PDGL red
  overrides the normal lake purple regardless of the `glof_risk` filter
  state — it's the one visual cue that's always on, since it's the one
  category ICIMOD has already assessed).
- Layout: full-bleed map, floating filter panel (left, collapsible on
  mobile), year slider (bottom), detail drawer (right, slides in on
  feature click), legend (bottom-left).

## 7. Phases (maps to prompt-book sessions)

1. Workspace bootstrap (pnpm monorepo, schema package, CI skeleton)
2. Reference data (Nepal boundaries, RGI baseline, ICIMOD placeholder)
3. Lake extraction pipeline
4. Glacier extraction pipeline + static bundle builder
5. Next.js portal (map, filters, detail pages)
6. Weekly cron wiring + first production deploy (not yet reached — see
   the prompt book's Session 6, which was truncated when handed to
   Claude Code)

Every phase ends with a runnable demo — if the frontend can't render what
the pipeline just produced, the phase isn't done.
