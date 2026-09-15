"use client";

import type { IndexEntry } from "@himalwatch/schema";
import { useState } from "react";
import { distinctValues } from "../lib/data";
import { countActiveFilters, EMPTY_FILTERS, type FilterState } from "../lib/filters";

interface FilterPanelProps {
  allEntries: IndexEntry[];
  filteredCount: number;
  filters: FilterState;
  onChange: (patch: Partial<FilterState>) => void;
}

function CheckboxGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="mb-3">
      <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy/70">
        {label}
      </legend>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {options.map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 text-sm text-navy">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => onToggle(opt)}
              className="h-3.5 w-3.5"
            />
            {opt}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function RangeInputs({
  label,
  min,
  max,
  onChangeMin,
  onChangeMax,
}: {
  label: string;
  min: number | null;
  max: number | null;
  onChangeMin: (v: number | null) => void;
  onChangeMax: (v: number | null) => void;
}) {
  const parse = (v: string) => (v === "" ? null : Number(v));
  return (
    <fieldset className="mb-3">
      <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy/70">
        {label}
      </legend>
      <div className="flex items-center gap-2">
        <input
          type="number"
          placeholder="Min"
          value={min ?? ""}
          onChange={(e) => onChangeMin(parse(e.target.value))}
          className="w-full rounded border border-black/15 px-2 py-1 text-sm"
        />
        <span className="text-navy/40">–</span>
        <input
          type="number"
          placeholder="Max"
          value={max ?? ""}
          onChange={(e) => onChangeMax(parse(e.target.value))}
          className="w-full rounded border border-black/15 px-2 py-1 text-sm"
        />
      </div>
    </fieldset>
  );
}

export function FilterPanel({ allEntries, filteredCount, filters, onChange }: FilterPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const provinces = distinctValues(allEntries, "province");
  const basins = distinctValues(allEntries, "basin");
  const districts = distinctValues(allEntries, "district");
  const activeCount = countActiveFilters(filters);

  const toggleArrayValue = (key: keyof FilterState, value: string) => {
    const current = filters[key] as string[];
    onChange({
      [key]: current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value],
    });
  };

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm font-medium text-navy shadow-md"
      >
        Filters {activeCount > 0 && `(${activeCount})`}
      </button>
    );
  }

  return (
    <div className="flex max-h-[80vh] w-72 flex-col rounded-lg border border-black/10 bg-white shadow-md">
      <div className="flex items-center justify-between border-b border-black/10 px-3 py-2">
        <span className="text-sm font-semibold text-navy">
          Filters · {filteredCount} of {allEntries.length}
        </span>
        <div className="flex gap-2">
          {activeCount > 0 && (
            <button
              onClick={() => onChange(EMPTY_FILTERS)}
              className="text-xs text-navy/60 underline"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => setCollapsed(true)}
            className="text-xs text-navy/60"
            aria-label="Collapse filters"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="overflow-y-auto px-3 py-3">
        <input
          type="text"
          placeholder="Search by name…"
          value={filters.q}
          onChange={(e) => onChange({ q: e.target.value })}
          className="mb-3 w-full rounded border border-black/15 px-2 py-1 text-sm"
        />

        <CheckboxGroup
          label="Basin"
          options={basins}
          selected={filters.basin}
          onToggle={(v) => toggleArrayValue("basin", v)}
        />
        <CheckboxGroup
          label="Province"
          options={provinces}
          selected={filters.province}
          onToggle={(v) => toggleArrayValue("province", v)}
        />

        <fieldset className="mb-3">
          <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy/70">
            District
          </legend>
          <select
            value={filters.district[0] ?? ""}
            onChange={(e) => onChange({ district: e.target.value ? [e.target.value] : [] })}
            className="w-full rounded border border-black/15 px-2 py-1 text-sm"
          >
            <option value="">All districts</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </fieldset>

        <RangeInputs
          label="Elevation (m)"
          min={filters.elevMin}
          max={filters.elevMax}
          onChangeMin={(v) => onChange({ elevMin: v })}
          onChangeMax={(v) => onChange({ elevMax: v })}
        />
        <RangeInputs
          label="Area (km²)"
          min={filters.areaMin}
          max={filters.areaMax}
          onChangeMin={(v) => onChange({ areaMin: v })}
          onChangeMax={(v) => onChange({ areaMax: v })}
        />
        <RangeInputs
          label="Change since 2000 (%)"
          min={filters.changeMin}
          max={filters.changeMax}
          onChangeMin={(v) => onChange({ changeMin: v })}
          onChangeMax={(v) => onChange({ changeMax: v })}
        />
        <CheckboxGroup
          label="Confidence"
          options={["high", "medium", "low"]}
          selected={filters.confidence}
          onToggle={(v) => toggleArrayValue("confidence", v)}
        />

        <div className="my-3 border-t border-black/10 pt-2">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-lake">Lakes</p>
          <CheckboxGroup
            label="GLOF risk"
            options={["unassessed", "low", "medium", "high"]}
            selected={filters.glofRisk}
            onToggle={(v) => toggleArrayValue("glofRisk", v)}
          />
          <CheckboxGroup
            label="Dam type"
            options={["unknown", "moraine", "ice", "bedrock"]}
            selected={filters.damType}
            onToggle={(v) => toggleArrayValue("damType", v)}
          />
          <label className="flex items-center gap-1.5 text-sm text-navy">
            <input
              type="checkbox"
              checked={filters.pdglOnly}
              onChange={(e) => onChange({ pdglOnly: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            PDGL only
          </label>
          <label className="mt-1 flex items-center gap-1.5 text-sm text-navy">
            <input
              type="checkbox"
              checked={filters.hasOutburst}
              onChange={(e) => onChange({ hasOutburst: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            Has outburst history
          </label>
        </div>

        <div className="border-t border-black/10 pt-2">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-glacier">
            Glaciers
          </p>
          <label className="flex items-center gap-1.5 text-sm text-navy">
            <input
              type="checkbox"
              checked={filters.debrisCovered}
              onChange={(e) => onChange({ debrisCovered: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            Debris-covered only
          </label>
          <label className="mt-1 flex items-center gap-1.5 text-sm text-navy">
            <input
              type="checkbox"
              checked={filters.hasLakes}
              onChange={(e) => onChange({ hasLakes: e.target.checked })}
              className="h-3.5 w-3.5"
            />
            Has associated lake(s)
          </label>
        </div>
      </div>
    </div>
  );
}
