import type { Metadata } from "next";
import { Header } from "../../components/Header";

export const metadata: Metadata = { title: "About — HimalWatch" };

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-offwhite">
      <Header />
      <main className="prose prose-slate mx-auto max-w-2xl px-4 py-10 prose-h2:text-navy prose-h1:text-navy">
        <h1>About HimalWatch</h1>
        <p>
          HimalWatch is a free, public monitoring portal for Nepal&apos;s high-altitude
          cryosphere — roughly 3,800 glaciers and 2,070 glacial lakes. A weekly pipeline pulls
          Sentinel-2 imagery and rebuilds a static bundle that this site serves directly, at $0/mo
          running cost.
        </p>

        <h2>Relationship to FP272</h2>
        <p>
          <a
            href="https://www.greenclimate.fund/sites/default/files/document/funding-proposal-fp272.pdf"
            target="_blank"
            rel="noreferrer"
          >
            FP272
          </a>{" "}
          is a $50M UNDP/Green Climate Fund project (2025–2032) funding the official glacier and
          glacial-lake inventory for Nepal, run together with the Department of Hydrology and
          Meteorology (DHM). That inventory is authoritative and refreshes on a multi-year cycle.
        </p>
        <p>
          HimalWatch is <strong>complementary</strong>, not competing: it fills the gap between
          those official updates with lightweight, automated weekly observation. It is never
          framed as an alternative to DHM or ICIMOD data, and it does not redistribute ICIMOD data
          without written permission — see the{" "}
          <a href="/methodology">methodology page</a> for exactly what that means for the dataset
          you&apos;re looking at today.
        </p>

        <h2>Data sources</h2>
        <ul>
          <li>Sentinel-2 L2A imagery, via the Copernicus Data Space Ecosystem.</li>
          <li>
            Glacier baseline: Randolph Glacier Inventory 6.0, Region 15 (South Asia East), via the
            public GLIMS/OGGM mirror.
          </li>
          <li>Administrative boundaries: geoBoundaries (provinces, districts).</li>
          <li>
            Glacial lake baseline (pre-2000 area, dam type, PDGL status): pending written
            permission from ICIMOD — currently unset for every lake in this dataset.
          </li>
        </ul>

        <h2>Attribution</h2>
        <p>
          Built with open data and open-source tools: MapLibre GL, PMTiles, the Randolph Glacier
          Inventory consortium, and geoBoundaries.
        </p>
      </main>
    </div>
  );
}
