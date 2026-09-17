import type { GlacierIndexEntry, LakeIndexEntry } from "@himalwatch/schema";
import { describe, expect, it } from "vitest";
import { applyFilters, countActiveFilters, EMPTY_FILTERS, type FilterState } from "./filters";

function glacier(overrides: Partial<GlacierIndexEntry> = {}): GlacierIndexEntry {
  return {
    type: "glacier",
    id: "glacier:RGI60-15.1",
    rgi_id: "RGI60-15.1",
    name: null,
    basin: "koshi",
    sub_basin: null,
    province: "Koshi",
    district: "Solukhumbu",
    elevation_min_m: 5000,
    elevation_max_m: 6000,
    elevation_mean_m: 5500,
    area_current_km2: 2.0,
    area_2000_km2: 2.2,
    area_change_pct_since_2000: -9.1,
    debris_covered: false,
    sla_current_m: null,
    associated_lake_ids: [],
    confidence: "medium",
    year: 2025,
    updated_at: "2026-01-01T00:00:00.000Z",
    centroid: [86.8, 27.9],
    ...overrides,
  };
}

function lake(overrides: Partial<LakeIndexEntry> = {}): LakeIndexEntry {
  return {
    type: "lake",
    id: "lake:gen:1",
    icimod_id: null,
    name: null,
    basin: "koshi",
    sub_basin: null,
    province: "Koshi",
    district: "Solukhumbu",
    elevation_m: 4200,
    area_current_km2: 0.08,
    area_2000_km2: null,
    area_change_pct_since_2000: null,
    dam_type: "unknown",
    glof_risk: "unassessed",
    is_pdgl: false,
    parent_glacier_id: null,
    outburst_history: [],
    downstream_population: null,
    confidence: "medium",
    year: 2025,
    updated_at: "2026-01-01T00:00:00.000Z",
    centroid: [86.9, 27.95],
    ...overrides,
  };
}

describe("applyFilters", () => {
  it("returns everything when no filter is active", () => {
    const entries = [glacier(), lake()];
    expect(applyFilters(entries, EMPTY_FILTERS)).toHaveLength(2);
  });

  it("filters by basin across both subject types", () => {
    const entries = [glacier({ basin: "koshi" }), glacier({ basin: "gandaki" }), lake({ basin: "koshi" })];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, basin: ["koshi"] });
    expect(result).toHaveLength(2);
    expect(result.every((e) => e.basin === "koshi")).toBe(true);
  });

  it("filters glacier elevation by elevation_mean_m, lake elevation by elevation_m", () => {
    const entries = [
      glacier({ elevation_mean_m: 5000 }),
      glacier({ elevation_mean_m: 6500 }),
      lake({ elevation_m: 3800 }),
      lake({ elevation_m: 4500 }),
    ];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, elevMin: 4200 });
    expect(result).toHaveLength(3); // both glaciers (5000, 6500) + the 4500 lake
  });

  it("lake-only filters never exclude glaciers, only non-matching lakes", () => {
    const entries = [glacier(), lake({ is_pdgl: true }), lake({ is_pdgl: false })];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, pdglOnly: true });
    expect(result).toHaveLength(2); // the glacier passes through + the PDGL lake
    expect(result.some((e) => e.type === "glacier")).toBe(true);
    expect(result.filter((e) => e.type === "lake")).toHaveLength(1);
  });

  it("debrisCovered filter only ever evaluates glaciers, lakes pass through", () => {
    const entries = [glacier({ debris_covered: false }), glacier({ debris_covered: true }), lake()];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, debrisCovered: true });
    expect(result).toHaveLength(2); // the debris-covered glacier + the lake
    expect(result.some((e) => e.type === "lake")).toBe(true);
  });

  it("outstanding change filter treats a null area_change as excluded, not zero", () => {
    const entries = [lake({ area_change_pct_since_2000: null }), glacier({ area_change_pct_since_2000: -5 })];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, changeMax: 0 });
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("glacier");
  });

  it("free-text search matches name case-insensitively", () => {
    const entries = [glacier({ name: "Khumbu Glacier" }), glacier({ name: "Ngozumpa Glacier" })];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, q: "khumbu" });
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Khumbu Glacier");
  });

  it("combines multiple filters with AND, not OR", () => {
    const entries = [
      lake({ basin: "koshi", is_pdgl: true }),
      lake({ basin: "koshi", is_pdgl: false }),
      lake({ basin: "gandaki", is_pdgl: true }),
    ];
    const filters: FilterState = { ...EMPTY_FILTERS, basin: ["koshi"], pdglOnly: true };
    const result = applyFilters(entries, filters);
    expect(result).toHaveLength(1);
  });

  it("never excludes entries by filters.year — index.json only ever holds the latest year, so that would zero out the whole list for any other year", () => {
    // Regression: dragging the year slider away from "latest" used to
    // blank the entire map, because this used to filter entries by
    // `entry.year === filters.year` against an index that only ever
    // contains one year's worth of entries. `filters.year` now drives the
    // map's tile-layer filter (see MapView's `year` prop) instead.
    const entries = [glacier({ year: 2025 }), lake({ year: 2025 })];
    const result = applyFilters(entries, { ...EMPTY_FILTERS, year: 2024 });
    expect(result).toHaveLength(2);
  });
});

describe("countActiveFilters", () => {
  it("is zero for the empty state", () => {
    expect(countActiveFilters(EMPTY_FILTERS)).toBe(0);
  });

  it("counts each non-empty field once, arrays included", () => {
    const filters: FilterState = { ...EMPTY_FILTERS, basin: ["koshi"], pdglOnly: true, q: "tsho" };
    expect(countActiveFilters(filters)).toBe(3);
  });

  it("never counts filters.year — it drives the map layer, not this filtered list", () => {
    const filters: FilterState = { ...EMPTY_FILTERS, year: 2024 };
    expect(countActiveFilters(filters)).toBe(0);
  });
});
