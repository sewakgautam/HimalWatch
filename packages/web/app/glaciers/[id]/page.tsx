import type { GlacierIndexEntry } from "@himalwatch/schema";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Header } from "../../../components/Header";
import { HistoryChart } from "../../../components/HistoryChart";
import { readIndexAtBuildTime } from "../../../lib/build-time-index";

export function generateStaticParams() {
  const index = readIndexAtBuildTime();
  return index
    .filter((e): e is GlacierIndexEntry => e.type === "glacier")
    .map((e) => ({ id: e.rgi_id }));
}

function findGlacier(rgiId: string): GlacierIndexEntry | undefined {
  const index = readIndexAtBuildTime();
  return index.find(
    (e): e is GlacierIndexEntry => e.type === "glacier" && e.rgi_id === rgiId
  );
}

export default function GlacierDetailPage({ params }: { params: { id: string } }) {
  const glacier = findGlacier(params.id);
  if (!glacier) notFound();

  return (
    <div className="min-h-screen bg-offwhite">
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Link href="/" className="text-sm text-navy/60 hover:underline">
          ← Back to map
        </Link>
        <span className="mt-4 inline-block rounded bg-glacier px-2 py-0.5 text-xs font-semibold uppercase text-white">
          Glacier
        </span>
        <h1 className="mt-2 text-2xl font-bold text-navy">{glacier.name ?? glacier.rgi_id}</h1>
        <p className="text-sm text-navy/60">{glacier.rgi_id}</p>

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border border-black/10 bg-white p-5 text-sm">
          <Field label="Province" value={glacier.province} />
          <Field label="District" value={glacier.district} />
          <Field label="Basin" value={glacier.basin} />
          <Field label="Extraction year" value={glacier.year} />
          <Field
            label="Elevation range"
            value={`${glacier.elevation_min_m ?? "—"}–${glacier.elevation_max_m ?? "—"} m`}
          />
          <Field label="Mean elevation" value={`${glacier.elevation_mean_m ?? "—"} m`} />
          <Field label="Current area" value={`${glacier.area_current_km2.toFixed(3)} km²`} />
          <Field label="Area circa 2000" value={`${glacier.area_2000_km2.toFixed(3)} km²`} />
          <Field
            label="Change since 2000"
            value={`${glacier.area_change_pct_since_2000.toFixed(1)}%`}
          />
          <Field label="Debris-covered" value={glacier.debris_covered ? "Yes" : "No"} />
          <Field label="Confidence" value={glacier.confidence} />
          <Field label="Associated lakes" value={glacier.associated_lake_ids.length} />
        </dl>

        <div className="mt-6 rounded-lg border border-black/10 bg-white p-5">
          <h2 className="mb-2 text-sm font-semibold text-navy">Area over time</h2>
          <HistoryChart id={glacier.id} type="glacier" color="#2a9d8f" />
        </div>

        {glacier.debris_covered && (
          <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
            This glacier is flagged debris-covered in the RGI baseline. Debris-covered ice has a
            spectral signature close to surrounding moraine/rock, so this pipeline caps confidence
            at &quot;low&quot; for it rather than trusting the automated extraction — see the{" "}
            <Link href="/methodology" className="underline">
              methodology page
            </Link>
            .
          </p>
        )}
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
