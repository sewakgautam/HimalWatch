import type { z } from "zod";
import type {
  AlertSchema,
  AreaGeometrySchema,
  BasinIdSchema,
  BasinSchema,
  ConfidenceSchema,
  DamTypeSchema,
  GlacierIndexEntrySchema,
  GlacierSchema,
  GlacierSnapshotSchema,
  GlofRiskSchema,
  IndexEntrySchema,
  LakeIndexEntrySchema,
  LakeSchema,
  LakeSnapshotSchema,
  ManifestSchema,
  OutburstEventSchema,
  PointGeometrySchema,
  PositionSchema,
  SnapshotSchema,
  SubjectTypeSchema,
} from "./zod.js";

export type Position = z.infer<typeof PositionSchema>;
export type PointGeometry = z.infer<typeof PointGeometrySchema>;
export type AreaGeometry = z.infer<typeof AreaGeometrySchema>;

export type Confidence = z.infer<typeof ConfidenceSchema>;
export type BasinId = z.infer<typeof BasinIdSchema>;
export type SubjectType = z.infer<typeof SubjectTypeSchema>;

export type Glacier = z.infer<typeof GlacierSchema>;

export type DamType = z.infer<typeof DamTypeSchema>;
export type GlofRisk = z.infer<typeof GlofRiskSchema>;
export type OutburstEvent = z.infer<typeof OutburstEventSchema>;
export type Lake = z.infer<typeof LakeSchema>;

export type GlacierSnapshot = z.infer<typeof GlacierSnapshotSchema>;
export type LakeSnapshot = z.infer<typeof LakeSnapshotSchema>;
export type Snapshot = z.infer<typeof SnapshotSchema>;

export type Basin = z.infer<typeof BasinSchema>;

export type GlacierIndexEntry = z.infer<typeof GlacierIndexEntrySchema>;
export type LakeIndexEntry = z.infer<typeof LakeIndexEntrySchema>;
export type IndexEntry = z.infer<typeof IndexEntrySchema>;

export type Alert = z.infer<typeof AlertSchema>;

export type Manifest = z.infer<typeof ManifestSchema>;
