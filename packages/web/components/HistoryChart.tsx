"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useSubjectHistory } from "../lib/data";

interface HistoryChartProps {
  id: string;
  type: "glacier" | "lake";
  color: string;
}

export function HistoryChart({ id, type, color }: HistoryChartProps) {
  const { history, isLoading } = useSubjectHistory(id, type);

  if (isLoading) return <p className="text-sm text-navy/50">Loading history…</p>;
  if (history.length < 2) {
    return (
      <p className="text-sm text-navy/50">
        Only one extraction year on record so far — a trend line needs at least two.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={history}>
        <CartesianGrid strokeDasharray="3 3" stroke="#00000010" />
        <XAxis dataKey="year" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} width={50} label={{ value: "km²", angle: -90, dx: -10 }} />
        <Tooltip formatter={(v) => `${Number(v).toFixed(3)} km²`} />
        <Line type="monotone" dataKey="area_km2" stroke={color} strokeWidth={2} dot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
