import type { Metadata } from "next";
import { Header } from "../../components/Header";

export const metadata: Metadata = { title: "Methodology — HimalWatch" };

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-offwhite">
      <Header />
      <main className="prose prose-slate mx-auto max-w-2xl px-4 py-10 prose-h2:text-navy prose-h1:text-navy">
        <h1>Methodology</h1>
        <p>
          HimalWatch runs a weekly extraction pipeline over Sentinel-2 imagery to track glacier
          and glacial-lake extent across Nepal. This page explains how, and — just as
          importantly — what it deliberately does not claim.
        </p>

        <h2>Compositing</h2>
        <p>
          For each basin and year, a cloud-masked Sentinel-2 median composite is built from the
          Scene Classification (SCL) band. Lakes use a post-monsoon window (Oct 1 – Nov 30, when
          cloud cover is lowest and lake levels have stabilized); glaciers use a late-ablation
          window (Sep 1 – Oct 31, closest to each year&apos;s minimum extent).
        </p>

        <h2>Lake extraction</h2>
        <ol>
          <li>
            <strong>MNDWI</strong> = (Green − SWIR) / (Green + SWIR), thresholded adaptively per
            composite via Otsu&apos;s method rather than a fixed cutoff.
          </li>
          <li>Vectorize the resulting water mask into polygons.</li>
          <li>
            Filter to elevation &gt; 3500m, within 1km of a known glacier, minimum area 3000 m²,
            and an elongation ratio (perimeter²/area) under 40 — the last of these specifically to
            drop river and stream segments, which are long and thin relative to their area.
          </li>
          <li>Match to the prior year&apos;s extraction by centroid distance to keep a stable id.</li>
        </ol>

        <h2>Glacier extraction</h2>
        <ol>
          <li>NDSI (same band pair as MNDWI), thresholded at 0.4.</li>
          <li>Exclude slopes ≥ 45°, which produce spurious snow/ice signal.</li>
          <li>
            Constrain to the RGI baseline outline buffered by 200m — glaciers only retreat over
            the monitoring window, so anything further out is extraction noise, not real advance.
          </li>
          <li>Match to the RGI baseline&apos;s own id for stable identity across years.</li>
        </ol>

        <h2>Confidence, not certainty</h2>
        <p>
          Every extracted feature carries a confidence label: <code>high</code> if the source
          composite&apos;s cloud cover was under 10%, <code>medium</code> under 30%, and{" "}
          <code>low</code> otherwise. Glaciers flagged debris-covered in the RGI baseline are
          always capped at <code>low</code> regardless of cloud cover — debris-covered ice has a
          spectral signature close to surrounding moraine and rock, and this pipeline does not
          attempt to solve that; it flags it instead.
        </p>

        <h2>What this deliberately does not do</h2>
        <ul>
          <li>
            <strong>No automated GLOF risk score.</strong> A lake&apos;s <code>glof_risk</code>{" "}
            field only ever reads <code>unassessed</code> from this pipeline. A real risk
            assessment requires dam geometry, downstream population, and hydrological modeling
            that a weekly satellite pass cannot substitute for — that value only ever comes from a
            human-reviewed assessment.
          </li>
          <li>
            <strong>No ICIMOD data redistribution.</strong> The 2018 baseline lake inventory and
            2020 PDGL list are ICIMOD products and are not loaded here without written permission.
            Until then, every lake&apos;s pre-2000 baseline area, dam type, and PDGL status default
            to &quot;unknown&quot;.
          </li>
          <li>
            <strong>Not a replacement for the official inventory.</strong> DHM&apos;s own 5-yearly
            glacier/lake inventory is the authoritative source. This pipeline exists to fill the
            gap between those updates with lightweight weekly monitoring — see the{" "}
            <a href="/about">about page</a>.
          </li>
        </ul>
      </main>
    </div>
  );
}
