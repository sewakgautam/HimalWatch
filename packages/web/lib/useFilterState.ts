"use client";

import {
  parseAsArrayOf,
  parseAsBoolean,
  parseAsFloat,
  parseAsInteger,
  parseAsString,
  useQueryStates,
} from "nuqs";
import { useMemo } from "react";
import { EMPTY_FILTERS, type FilterState } from "./filters";

/**
 * URL-encodes every filter in FilterState (spec §3: "URL-encoded state so
 * filter combinations are shareable") via nuqs. Array filters are
 * comma-separated (`?province=Koshi,Bagmati`); everything else is a
 * plain query param. Absent from the URL = the EMPTY_FILTERS default,
 * not undefined, so callers never need an extra null-check layer beyond
 * what FilterState already models.
 */
export function useFilterState() {
  const [state, setState] = useQueryStates(
    {
      province: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.province),
      basin: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.basin),
      district: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.district),
      elevMin: parseAsFloat,
      elevMax: parseAsFloat,
      areaMin: parseAsFloat,
      areaMax: parseAsFloat,
      year: parseAsInteger,
      changeMin: parseAsFloat,
      changeMax: parseAsFloat,
      confidence: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.confidence),
      q: parseAsString.withDefault(EMPTY_FILTERS.q),
      glofRisk: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.glofRisk),
      damType: parseAsArrayOf(parseAsString).withDefault(EMPTY_FILTERS.damType),
      pdglOnly: parseAsBoolean.withDefault(EMPTY_FILTERS.pdglOnly),
      hasOutburst: parseAsBoolean.withDefault(EMPTY_FILTERS.hasOutburst),
      debrisCovered: parseAsBoolean.withDefault(EMPTY_FILTERS.debrisCovered),
      hasLakes: parseAsBoolean.withDefault(EMPTY_FILTERS.hasLakes),
    },
    { history: "replace" }
  );

  // nuqs gives back `number | null` for the numeric parsers already, so
  // this cast just asserts the object's shape matches FilterState exactly
  // (every key present, defaults applied) rather than transforming
  // anything.
  const filters = state as FilterState;

  const setFilters = useMemo(() => setState, [setState]);

  return { filters, setFilters };
}
