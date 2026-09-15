"use client";

import type { IndexEntry } from "@himalwatch/schema";
import {
  addProtocol,
  Map as MapLibreMap,
  NavigationControl,
  type FilterSpecification,
  type MapLayerMouseEvent,
} from "maplibre-gl";
import { Protocol } from "pmtiles";
import { useEffect, useRef } from "react";

// CARTO's Positron style — a free, no-API-key vector basemap. Chosen over
// MapTiler's hosted styles specifically because those need an account +
// key; this portal has no server-side secret to hide one behind even if
// it did (static export, no backend). See spec §6.
const BASEMAP_STYLE_URL = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

interface MapViewProps {
  visibleIds: Set<string> | null; // null = show everything (no filter active)
  onSelectFeature: (entry: IndexEntry | null) => void;
  indexById: Map<string, IndexEntry>;
}

let protocolRegistered = false;

export function MapView({ visibleIds, onSelectFeature, indexById }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  // The click handler is registered once, inside the map-creation effect
  // below (deliberately `[]`-deps, so the map itself isn't torn down and
  // rebuilt on every render). `indexById` is a fresh Map on every render
  // once /data/index.json loads, though — reading it via a ref (updated
  // every render) instead of closing over the prop directly avoids a
  // stale closure that would otherwise permanently hold whatever
  // (possibly still-empty) Map existed at the moment style.load fired.
  const indexByIdRef = useRef(indexById);
  indexByIdRef.current = indexById;

  useEffect(() => {
    if (!protocolRegistered) {
      const protocol = new Protocol();
      addProtocol("pmtiles", protocol.tile);
      protocolRegistered = true;
    }
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: BASEMAP_STYLE_URL,
      center: [84.5, 28.4], // roughly central Nepal
      zoom: 6.2,
      maxBounds: [
        [78, 25],
        [90, 32],
      ],
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    // Exposed for e2e tests (see e2e/map.spec.ts), which need to project
    // a known feature's lng/lat to a screen pixel to click it reliably —
    // clicking blind coordinates on a WebGL canvas isn't a stable test.
    // Read-only in practice (nothing else reads this global); harmless
    // on a public, unauthenticated map.
    (window as unknown as { __himalwatchMap?: MapLibreMap }).__himalwatchMap = map;
    map.on("error", (e) => console.error("[MapView] maplibre error", e.error));

    // 'style.load' (style JSON + sprite + glyphs ready), not 'load' (which
    // also waits for every one of the basemap's own tiles to finish
    // downloading) — our overlay sources/layers don't need the basemap's
    // tiles to be done loading first, and gating on 'load' made our own
    // glacier/lake data wait on an unrelated third party's tile latency.
    map.on("style.load", () => {
      // pmtiles's protocol handler expects a full URL (its own scheme
      // included) after the "pmtiles://" prefix, not a bare path — see
      // https://github.com/protomaps/PMTiles's maplibre usage example.
      const origin = window.location.origin;
      map.addSource("glaciers", {
        type: "vector",
        url: `pmtiles://${origin}/data/tiles/nepal-glaciers.pmtiles`,
      });
      map.addSource("lakes", {
        type: "vector",
        url: `pmtiles://${origin}/data/tiles/nepal-lakes.pmtiles`,
      });

      map.addLayer({
        id: "glaciers-fill",
        type: "fill",
        source: "glaciers",
        "source-layer": "glacier",
        paint: { "fill-color": "#2a9d8f", "fill-opacity": 0.55 },
      });
      map.addLayer({
        id: "glaciers-outline",
        type: "line",
        source: "glaciers",
        "source-layer": "glacier",
        paint: { "line-color": "#1f746a", "line-width": 1 },
      });

      // PDGL lakes render red regardless of the glof_risk filter state —
      // that's the one visual cue that's always on (spec §6).
      map.addLayer({
        id: "lakes-fill",
        type: "fill",
        source: "lakes",
        "source-layer": "lake",
        paint: {
          "fill-color": ["case", ["get", "is_pdgl"], "#d84a4a", "#7b6fd8"],
          "fill-opacity": 0.65,
        },
      });
      map.addLayer({
        id: "lakes-outline",
        type: "line",
        source: "lakes",
        "source-layer": "lake",
        paint: {
          "line-color": ["case", ["get", "is_pdgl"], "#a83333", "#5b4fb8"],
          "line-width": 1,
        },
      });

      const handleClick = (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const id = feature.properties?.id as string | undefined;
        const entry = id ? indexByIdRef.current.get(id) : undefined;
        onSelectFeature(entry ?? null);
      };

      for (const layerId of ["glaciers-fill", "lakes-fill"]) {
        map.on("click", layerId, handleClick);
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
        });
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // indexById/onSelectFeature are stable-enough for the map's lifetime
    // (recreated only if the index itself changes) — re-running this
    // whole effect on every render would tear down and rebuild the map.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Applies the current filter as a visibility filter on both layers —
  // `null` means "no filter active", so every feature shows.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const filterExpr =
        visibleIds === null
          ? null
          : (["in", ["get", "id"], ["literal", Array.from(visibleIds)]] as unknown as FilterSpecification);
      for (const layerId of ["glaciers-fill", "glaciers-outline", "lakes-fill", "lakes-outline"]) {
        if (map.getLayer(layerId)) {
          map.setFilter(layerId, filterExpr);
        }
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("style.load", apply);
  }, [visibleIds]);

  return <div ref={containerRef} className="h-full w-full" />;
}
