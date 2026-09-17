import type { GlacierIndexEntry, IndexEntry, LakeIndexEntry } from "@himalwatch/schema";

/**
 * Every filter from docs/HIMALWATCH_SPEC.md §3. All optional; an absent
 * filter never excludes anything. Kept as a plain object (not tied to
 * nuqs) so `applyFilters` stays a pure, easily-testable function — see
 * useFilterState.ts for the URL-state wiring on top of this shape.
 */
export interface FilterState {
  // Shared
  province: string[];
  basin: string[];
  district: string[];
  elevMin: number | null;
  elevMax: number | null;
  areaMin: number | null;
  areaMax: number | null;
  year: number | null;
  changeMin: number | null;
  changeMax: number | null;
  confidence: string[];
  q: string;
  // Lake-only
  glofRisk: string[];
  damType: string[];
  pdglOnly: boolean;
  hasOutburst: boolean;
  // Glacier-only
  debrisCovered: boolean;
  hasLakes: boolean;
}

export const EMPTY_FILTERS: FilterState = {
  province: [],
  basin: [],
  district: [],
  elevMin: null,
  elevMax: null,
  areaMin: null,
  areaMax: null,
  year: null,
  changeMin: null,
  changeMax: null,
  confidence: [],
  q: "",
  glofRisk: [],
  damType: [],
  pdglOnly: false,
  hasOutburst: false,
  debrisCovered: false,
  hasLakes: false,
};

function isGlacier(entry: IndexEntry): entry is GlacierIndexEntry {
  return entry.type === "glacier";
}

function isLake(entry: IndexEntry): entry is LakeIndexEntry {
  return entry.type === "lake";
}

/** The elevation this entry is filtered/sorted by — glaciers report a
 * min/max/mean band, lakes a single point value, so "elevation" means
 * different fields depending on type. */
function elevationOf(entry: IndexEntry): number {
  return isGlacier(entry) ? (entry.elevation_mean_m ?? 0) : entry.elevation_m;
}

/**
 * Applies every active filter as an AND. Pure function over the flat
 * IndexEntry array (spec §2.5) — no geometry, no network, so this is
 * exactly what the client runs on every filter-panel change.
 */
export function applyFilters(entries: IndexEntry[], filters: FilterState): IndexEntry[] {
  return entries.filter((entry) => {
    if (filters.province.length && !filters.province.includes(entry.province)) return false;
    if (filters.basin.length && !filters.basin.includes(entry.basin)) return false;
    if (filters.district.length && !filters.district.includes(entry.district)) return false;
    if (filters.confidence.length && !filters.confidence.includes(entry.confidence)) return false;
    // No `entry.year` check here — index.json (spec §2.5) only ever holds
    // the latest year's subjects, one entry per id, so matching against
    // `filters.year` for anything but the latest year would always
    // return zero results. `filters.year` instead drives which year the
    // *map layer* shows (see MapView's `year` prop, applied as a filter
    // directly on the PMTiles' own per-feature `year` property, which —
    // unlike index.json — carries every year) — it deliberately never
    // narrows this list.

    const elevation = elevationOf(entry);
    if (filters.elevMin !== null && elevation < filters.elevMin) return false;
    if (filters.elevMax !== null && elevation > filters.elevMax) return false;

    if (filters.areaMin !== null && entry.area_current_km2 < filters.areaMin) return false;
    if (filters.areaMax !== null && entry.area_current_km2 > filters.areaMax) return false;

    const change = entry.area_change_pct_since_2000;
    if (filters.changeMin !== null && (change === null || change < filters.changeMin)) {
      return false;
    }
    if (filters.changeMax !== null && (change === null || change > filters.changeMax)) {
      return false;
    }

    if (filters.q.trim()) {
      const needle = filters.q.trim().toLowerCase();
      const haystack = (entry.name ?? "").toLowerCase();
      if (!haystack.includes(needle)) return false;
    }

    if (isLake(entry)) {
      if (filters.glofRisk.length && !filters.glofRisk.includes(entry.glof_risk)) return false;
      if (filters.damType.length && !filters.damType.includes(entry.dam_type)) return false;
      if (filters.pdglOnly && !entry.is_pdgl) return false;
      if (filters.hasOutburst && entry.outburst_history.length === 0) return false;
    }

    if (isGlacier(entry)) {
      if (filters.debrisCovered && !entry.debris_covered) return false;
      if (filters.hasLakes && entry.associated_lake_ids.length === 0) return false;
    }

    return true;
  });
}

export function countActiveFilters(filters: FilterState): number {
  let count = 0;
  for (const [key, value] of Object.entries(filters)) {
    if (key === "year") continue; // drives the map layer, not this list — see applyFilters
    const empty =
      value === null ||
      value === "" ||
      value === false ||
      (Array.isArray(value) && value.length === 0);
    if (!empty) count++;
  }
  return count;
}
