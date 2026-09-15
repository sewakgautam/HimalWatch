"use client";

import type { IndexEntry, Manifest } from "@himalwatch/schema";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

/**
 * Loads /data/index.json once per session (SWR's default dedupe/cache
 * handles that) — the flat, geometry-free array every filter in
 * lib/filters.ts runs over client-side. See spec §2.5.
 */
export function useIndex() {
  const { data, error, isLoading } = useSWR<IndexEntry[]>("/data/index.json", fetcher, {
    revalidateOnFocus: false,
  });
  return { entries: data ?? [], error, isLoading };
}

export function useManifest() {
  const { data, error, isLoading } = useSWR<Manifest>("/data/manifest.json", fetcher, {
    revalidateOnFocus: false,
  });
  return { manifest: data, error, isLoading };
}

/** Distinct, sorted values for a given field across the whole index —
 * used to populate the province/district/basin filter options without
 * hardcoding them (a district hardcoded here would drift from whatever
 * districts.geojson actually contains). */
export function distinctValues(entries: IndexEntry[], field: "province" | "district" | "basin") {
  return Array.from(new Set(entries.map((e) => e[field]))).sort();
}

export function distinctYears(entries: IndexEntry[]): number[] {
  return Array.from(new Set(entries.map((e) => e.year))).sort((a, b) => b - a);
}

interface HistoryPoint {
  year: number;
  area_km2: number;
}

/**
 * A subject's area across every extraction year available. Reads each
 * year's per-basin-merged snapshot (data/{type}s/snapshots/{year}.geojson)
 * and pulls out the one matching feature — fine at this project's scale
 * (a few thousand features, a handful of years); a dataset large enough
 * for this to matter would want a dedicated per-subject history file
 * instead of re-reading a full snapshot per year.
 */
export function useSubjectHistory(id: string, type: "glacier" | "lake") {
  const { manifest } = useManifest();
  const years = manifest ? Object.keys(manifest.subjects_by_year).map(Number) : [];
  const subjectDir = type === "glacier" ? "glaciers" : "lakes";

  const { data, isLoading } = useSWR(
    years.length ? [`subject-history`, id, subjectDir, years.join(",")] : null,
    async () => {
      const points: HistoryPoint[] = [];
      for (const year of years) {
        const res = await fetch(`/data/${subjectDir}/snapshots/${year}.geojson`);
        if (!res.ok) continue;
        const geojson = await res.json();
        const feature = (geojson.features as Array<{ properties: Record<string, unknown> }>).find(
          (f) => f.properties.id === id
        );
        if (feature) {
          points.push({ year, area_km2: feature.properties.area_current_km2 as number });
        }
      }
      return points.sort((a, b) => a.year - b.year);
    }
  );

  return { history: data ?? [], isLoading };
}
