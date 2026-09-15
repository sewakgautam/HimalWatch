"use client";

import type { IndexEntry } from "@himalwatch/schema";
import Link from "next/link";
import { HistoryChart } from "./HistoryChart";

interface SubjectDetailDrawerProps {
  entry: IndexEntry;
  onClose: () => void;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between border-b border-black/5 py-1.5 text-sm">
      <span className="text-navy/60">{label}</span>
      <span className="font-medium text-navy">{value}</span>
    </div>
  );
}

export function SubjectDetailDrawer({ entry, onClose }: SubjectDetailDrawerProps) {
  const isGlacier = entry.type === "glacier";
  const detailHref = isGlacier ? `/glaciers/${entry.rgi_id}` : `/lakes/${entry.id.replace(/^lake:/, "")}`;

  return (
    <aside className="flex h-full w-80 flex-col overflow-y-auto border-l border-black/10 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
        <div>
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white"
            style={{ backgroundColor: isGlacier ? "#2a9d8f" : entry.is_pdgl ? "#d84a4a" : "#7b6fd8" }}
          >
            {isGlacier ? "Glacier" : entry.is_pdgl ? "PDGL Lake" : "Lake"}
          </span>
          <h2 className="mt-1 text-base font-semibold text-navy">
            {entry.name ?? (isGlacier ? entry.rgi_id : "Unnamed lake")}
          </h2>
        </div>
        <button onClick={onClose} className="text-navy/50 hover:text-navy" aria-label="Close">
          ✕
        </button>
      </div>

      <div className="px-4 py-3">
        <Row label="Province" value={entry.province} />
        <Row label="District" value={entry.district} />
        <Row label="Basin" value={entry.basin} />
        <Row
          label="Elevation"
          value={isGlacier ? `${entry.elevation_mean_m ?? "—"} m (mean)` : `${entry.elevation_m} m`}
        />
        <Row label="Current area" value={`${entry.area_current_km2.toFixed(3)} km²`} />
        <Row
          label="Change since 2000"
          value={
            entry.area_change_pct_since_2000 !== null
              ? `${entry.area_change_pct_since_2000.toFixed(1)}%`
              : "Unknown"
          }
        />
        <Row label="Confidence" value={entry.confidence} />
        <Row label="Year" value={entry.year} />

        {isGlacier ? (
          <>
            <Row label="Debris-covered" value={entry.debris_covered ? "Yes" : "No"} />
            <Row label="Associated lakes" value={entry.associated_lake_ids.length} />
          </>
        ) : (
          <>
            <Row label="Dam type" value={entry.dam_type} />
            <Row label="GLOF risk" value={entry.glof_risk} />
            <Row label="Outburst history" value={entry.outburst_history.length ? "Yes" : "None recorded"} />
          </>
        )}

        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-navy/60">
            Area over time
          </p>
          <HistoryChart id={entry.id} type={entry.type} color={isGlacier ? "#2a9d8f" : "#7b6fd8"} />
        </div>

        <Link
          href={detailHref}
          className="mt-4 block rounded bg-navy px-3 py-2 text-center text-sm font-medium text-white hover:bg-navy/90"
        >
          View full detail page
        </Link>
      </div>
    </aside>
  );
}
