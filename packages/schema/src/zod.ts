import { z } from "zod";

/**
 * Every schema here mirrors docs/HIMALWATCH_SPEC.md §2 in the repo root.
 * This file is the single source of truth both the Python pipeline's
 * output and the web client's expectations are checked against — if a
 * field changes, it changes here first, then in the spec doc, then in the
 * pipeline's `toMap`/`fromMap`-equivalent serialization.
 */

// ---- Shared primitives -----------------------------------------------

/** GeoJSON position: [lng, lat] or [lng, lat, alt]. EPSG:4326 throughout. */
export const PositionSchema = z.tuple([z.number(), z.number()]).rest(z.number());

export const PointGeometrySchema = z.object({
  type: z.literal("Point"),
  coordinates: PositionSchema,
});

export const PolygonGeometrySchema = z.object({
  type: z.literal("Polygon"),
  coordinates: z.array(z.array(PositionSchema)),
});

export const MultiPolygonGeometrySchema = z.object({
  type: z.literal("MultiPolygon"),
  coordinates: z.array(z.array(z.array(PositionSchema))),
});

/** Glacier/lake outlines are always Polygon or MultiPolygon. */
export const AreaGeometrySchema = z.union([
  PolygonGeometrySchema,
  MultiPolygonGeometrySchema,
]);

export const ConfidenceSchema = z.enum(["high", "medium", "low"]);

export const BasinIdSchema = z.enum(["koshi", "gandaki", "karnali", "mahakali"]);

export const SubjectTypeSchema = z.enum(["glacier", "lake"]);

// ---- Glacier (spec §2.1) ------------------------------------------------

export const GlacierSchema = z.object({
  id: z.string(),
  rgi_id: z.string(),
  name: z.string().nullable(),
  geom: AreaGeometrySchema,
  basin: BasinIdSchema,
  sub_basin: z.string().nullable(),
  province: z.string(),
  district: z.string(),
  elevation_min_m: z.number().nullable(),
  elevation_max_m: z.number().nullable(),
  elevation_mean_m: z.number().nullable(),
  area_current_km2: z.number().nonnegative(),
  area_2000_km2: z.number().nonnegative(),
  area_change_pct_since_2000: z.number(),
  debris_covered: z.boolean(),
  sla_current_m: z.number().nullable(),
  terminus_point: PointGeometrySchema.nullable(),
  associated_lake_ids: z.array(z.string()),
  confidence: ConfidenceSchema,
  year: z.number().int(),
  updated_at: z.string().datetime(),
});

// ---- Lake (spec §2.2) ---------------------------------------------------

export const DamTypeSchema = z.enum(["moraine", "ice", "bedrock", "unknown"]);

/**
 * Never set to anything but "unassessed" by the automated pipeline — see
 * CLAUDE.md's non-negotiables. A real value only ever comes from a
 * human-reviewed QA annotation, never an extraction heuristic.
 */
export const GlofRiskSchema = z.enum(["low", "medium", "high", "unassessed"]);

export const OutburstEventSchema = z.object({
  year: z.number().int(),
  note: z.string(),
});

export const LakeSchema = z.object({
  id: z.string(),
  icimod_id: z.string().nullable(),
  name: z.string().nullable(),
  geom: AreaGeometrySchema,
  basin: BasinIdSchema,
  sub_basin: z.string().nullable(),
  province: z.string(),
  district: z.string(),
  elevation_m: z.number(),
  area_current_km2: z.number().nonnegative(),
  area_2000_km2: z.number().nonnegative().nullable(),
  area_change_pct_since_2000: z.number().nullable(),
  dam_type: DamTypeSchema,
  glof_risk: GlofRiskSchema,
  is_pdgl: z.boolean(),
  parent_glacier_id: z.string().nullable(),
  outburst_history: z.array(OutburstEventSchema),
  downstream_population: z.number().int().nonnegative().nullable(),
  confidence: ConfidenceSchema,
  year: z.number().int(),
  updated_at: z.string().datetime(),
});

// ---- Snapshots (spec §2.3) -----------------------------------------------

const SnapshotBaseSchema = z.object({
  subject_id: z.string(),
  year: z.number().int(),
  area_km2: z.number().nonnegative(),
  confidence: ConfidenceSchema,
  cloud_pct: z.number().min(0).max(100),
});

export const GlacierSnapshotSchema = SnapshotBaseSchema.extend({
  subject_type: z.literal("glacier"),
  elevation_mean_m: z.number().nullable(),
});

export const LakeSnapshotSchema = SnapshotBaseSchema.extend({
  subject_type: z.literal("lake"),
  elevation_m: z.number().nullable(),
});

export const SnapshotSchema = z.discriminatedUnion("subject_type", [
  GlacierSnapshotSchema,
  LakeSnapshotSchema,
]);

// ---- Basin (spec §2.4) ----------------------------------------------------

export const BasinSchema = z.object({
  id: BasinIdSchema,
  name: z.string(),
  name_ne: z.string(),
  geom: AreaGeometrySchema,
});

// ---- IndexEntry (spec §2.5) -----------------------------------------------
// Every field from Glacier/Lake except `geom` and `terminus_point`, plus a
// `type` discriminator and a `centroid` for label placement / flyTo.

export const GlacierIndexEntrySchema = GlacierSchema.omit({
  geom: true,
  terminus_point: true,
}).extend({
  type: z.literal("glacier"),
  centroid: PositionSchema,
});

export const LakeIndexEntrySchema = LakeSchema.omit({ geom: true }).extend({
  type: z.literal("lake"),
  centroid: PositionSchema,
});

export const IndexEntrySchema = z.discriminatedUnion("type", [
  GlacierIndexEntrySchema,
  LakeIndexEntrySchema,
]);

// ---- Alert (spec §2.6) -----------------------------------------------------
// Reserved for Phase 2+. Never a path to auto-populating Lake.glof_risk —
// an Alert is a prompt for human QA review, not a public risk claim.

export const AlertKindSchema = z.enum([
  "rapid_area_change",
  "new_feature",
  "low_confidence_review",
]);

export const AlertSeveritySchema = z.enum(["info", "warning"]);

export const AlertSchema = z.object({
  id: z.string(),
  subject_id: z.string(),
  subject_type: SubjectTypeSchema,
  kind: AlertKindSchema,
  severity: AlertSeveritySchema,
  message: z.string(),
  year: z.number().int(),
  created_at: z.string().datetime(),
});

// ---- Manifest (build output metadata, referenced in the pipeline's
// static bundle builder — not a spec §2 subject, but shared shape) -------

export const ManifestSchema = z.object({
  version: z.string(),
  generated_at: z.string().datetime(),
  commit_sha: z.string(),
  counts_by_basin: z.record(BasinIdSchema, z.object({ glaciers: z.number().int(), lakes: z.number().int() })),
  subjects_by_year: z.record(z.string(), z.number().int()),
});
