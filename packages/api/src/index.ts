import { initializeApp } from "firebase-admin/app";

/**
 * QA annotation endpoints only. Every public read of glacier/lake data is
 * a static file served by Firebase Hosting (packages/web's static
 * export) — nothing here ever backs a public data path. See CLAUDE.md's
 * non-negotiables: "Do not switch to Firestore for lake/glacier data even
 * if it seems simpler."
 *
 * Not deployed yet. Functions land here once the QA annotation flow
 * (reviewer signs in, confirms/corrects a low-confidence extraction) is
 * designed — that hasn't happened in Sessions 1–5.
 */
initializeApp();
