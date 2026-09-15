"use client";

import { useIndex, useManifest } from "../lib/data";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-black/10 bg-white px-4 py-2 text-center shadow-sm">
      <div className="text-xl font-bold text-navy">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-navy/60">{label}</div>
    </div>
  );
}

export function NepalOverview() {
  const { entries } = useIndex();
  const { manifest } = useManifest();
  const glacierCount = entries.filter((e) => e.type === "glacier").length;
  const lakeCount = entries.filter((e) => e.type === "lake").length;
  const pdglCount = entries.filter((e) => e.type === "lake" && e.is_pdgl).length;

  return (
    <div className="flex flex-wrap gap-2">
      <StatCard label="Glaciers tracked" value={glacierCount} />
      <StatCard label="Glacial lakes tracked" value={lakeCount} />
      <StatCard label="PDGLs" value={pdglCount} />
      {manifest && (
        <StatCard
          label="Bundle generated"
          value={new Date(manifest.generated_at).toLocaleDateString()}
        />
      )}
    </div>
  );
}
