"use client";

import type { IndexEntry } from "@himalwatch/schema";
import { Suspense, useMemo, useState } from "react";
import { FilterPanel } from "../components/FilterPanel";
import { Header } from "../components/Header";
import { Legend } from "../components/Legend";
import { MapView } from "../components/MapView";
import { NepalOverview } from "../components/NepalOverview";
import { SubjectDetailDrawer } from "../components/SubjectDetailDrawer";
import { YearSlider } from "../components/YearSlider";
import { distinctYears, useIndex } from "../lib/data";
import { applyFilters, countActiveFilters } from "../lib/filters";
import { useFilterState } from "../lib/useFilterState";

// nuqs' useQueryStates reads useSearchParams() internally, which forces
// this whole subtree to bail out of static prerendering unless it's
// wrapped in Suspense — see
// https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout.
export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-offwhite text-navy">
          Loading map…
        </div>
      }
    >
      <MapPageContent />
    </Suspense>
  );
}

function MapPageContent() {
  const { entries, isLoading } = useIndex();
  const { filters, setFilters } = useFilterState();
  const [selected, setSelected] = useState<IndexEntry | null>(null);

  const years = useMemo(() => distinctYears(entries), [entries]);

  const filtered = useMemo(() => applyFilters(entries, filters), [entries, filters]);

  const indexById = useMemo(() => new Map(entries.map((e) => [e.id, e])), [entries]);

  // Only pass a restrictive id set to the map when a filter is actually
  // active — otherwise every feature shows, and we skip building a
  // multi-thousand-entry Set on every render for nothing.
  const visibleIds = useMemo(() => {
    if (countActiveFilters(filters) === 0) return null;
    return new Set(filtered.map((e) => e.id));
  }, [filters, filtered]);

  return (
    <div className="flex h-screen flex-col">
      <Header />
      <div className="relative flex-1">
        <MapView visibleIds={visibleIds} onSelectFeature={setSelected} indexById={indexById} />

        <div className="pointer-events-none absolute inset-0 flex">
          <div className="pointer-events-auto m-3 flex flex-col gap-3">
            <FilterPanel
              allEntries={entries}
              filteredCount={filtered.length}
              filters={filters}
              onChange={(patch) => setFilters(patch)}
            />
            <NepalOverview />
          </div>

          <div className="flex flex-1 flex-col justify-end">
            <div className="pointer-events-auto mb-3 ml-3 self-start">
              <YearSlider
                years={years}
                selected={filters.year}
                onChange={(year) => setFilters({ year })}
              />
            </div>
          </div>

          <div className="pointer-events-auto m-3 self-start">
            <Legend />
          </div>
        </div>

        {selected && (
          <div className="absolute inset-y-0 right-0">
            <SubjectDetailDrawer entry={selected} onClose={() => setSelected(null)} />
          </div>
        )}

        {isLoading && (
          <div className="absolute inset-x-0 top-1/2 flex justify-center">
            <div className="rounded-full bg-white px-4 py-2 text-sm text-navy shadow-md">
              Loading dataset…
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
