import type { LakeIndexEntry } from "@himalwatch/schema";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Header } from "../../../components/Header";
import { HistoryChart } from "../../../components/HistoryChart";
import { readIndexAtBuildTime } from "../../../lib/build-time-index";

function shortId(fullId: string): string {
  return fullId.replace(/^lake:/, "");
}

export function generateStaticParams() {
  const index = readIndexAtBuildTime();
  return index
    .filter((e): e is LakeIndexEntry => e.type === "lake")
    .map((e) => ({ id: shortId(e.id) }));
}

function findLake(shortLakeId: string): LakeIndexEntry | undefined {
  const index = readIndexAtBuildTime();
  return index.find(
    (e): e is LakeIndexEntry => e.type === "lake" && shortId(e.id) === shortLakeId
  );
}

export default function LakeDetailPage({ params }: { params: { id: string } }) {
  const lake = findLake(params.id);
  if (!lake) notFound();

  return (
    <div className="min-h-screen bg-offwhite">
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Link href="/" className="text-sm text-navy/60 hover:underline">
          ← Back to map
        </Link>
        <span
          className="mt-4 inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase text-white"
          style={{ backgroundColor: lake.is_pdgl ? "#d84a4a" : "#7b6fd8" }}
        >
          {lake.is_pdgl ? "PDGL Lake" : "Glacial lake"}
        </span>
        <h1 className="mt-2 text-2xl font-bold text-navy">{lake.name ?? "Unnamed lake"}</h1>
        <p className="text-sm text-navy/60">{shortId(lake.id)}</p>

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border border-black/10 bg-white p-5 text-sm">
          <Field label="Province" value={lake.province} />
          <Field label="District" value={lake.district} />
          <Field label="Basin" value={lake.basin} />
          <Field label="Extraction year" value={lake.year} />
          <Field label="Elevation" value={`${lake.elevation_m} m`} />
          <Field label="Current area" value={`${lake.area_current_km2.toFixed(3)} km²`} />
          <Field
            label="Change since 2000"
            value={
              lake.area_change_pct_since_2000 !== null
                ? `${lake.area_change_pct_since_2000.toFixed(1)}%`
                : "Unknown — pending ICIMOD baseline"
            }
          />
          <Field label="Dam type" value={lake.dam_type} />
          <Field label="GLOF risk" value={lake.glof_risk} />
          <Field label="Confidence" value={lake.confidence} />
          <Field
            label="Outburst history"
            value={lake.outburst_history.length ? lake.outburst_history.map((o) => o.year).join(", ") : "None recorded"}
          />
        </dl>

        <div className="mt-6 rounded-lg border border-black/10 bg-white p-5">
          <h2 className="mb-2 text-sm font-semibold text-navy">Area over time</h2>
          <HistoryChart id={lake.id} type="lake" color="#7b6fd8" />
        </div>

        <p className="mt-4 rounded-lg border border-black/10 bg-white p-3 text-xs text-navy/60">
          GLOF risk here is <strong>never</strong> set by automated extraction — it stays{" "}
          <code>unassessed</code> until a human-reviewed ICIMOD or equivalent assessment exists.
          See the <Link href="/methodology" className="underline">methodology page</Link> for why.
        </p>
      </main>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-navy/50">{label}</dt>
      <dd className="font-medium text-navy">{value}</dd>
    </div>
  );
}
