import type { IndexEntry } from "@himalwatch/schema";
import fs from "node:fs";
import path from "node:path";

/**
 * Reads data/index.json directly off disk — used only from
 * generateStaticParams and the detail page Server Components, which run
 * at build time under `output: 'export'` (there's no server at runtime
 * to re-read this from, so every path this feeds must be pre-rendered).
 * The client-side map/filter UI uses lib/data.ts's fetch-based hooks
 * instead; this file is deliberately never imported from a 'use client'
 * component.
 */
let cached: IndexEntry[] | null = null;

export function readIndexAtBuildTime(): IndexEntry[] {
  if (cached) return cached;
  const indexPath = path.join(process.cwd(), "..", "..", "data", "index.json");
  const raw = fs.readFileSync(indexPath, "utf-8");
  cached = JSON.parse(raw) as IndexEntry[];
  return cached;
}
