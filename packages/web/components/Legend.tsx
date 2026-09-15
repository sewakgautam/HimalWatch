export function Legend() {
  const rows: { color: string; label: string }[] = [
    { color: "#2a9d8f", label: "Glacier" },
    { color: "#7b6fd8", label: "Glacial lake" },
    { color: "#d84a4a", label: "PDGL (potentially dangerous)" },
  ];
  return (
    <div className="rounded-lg border border-black/10 bg-white/95 px-3 py-2 text-xs shadow-md backdrop-blur">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center gap-2 py-0.5">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: row.color }}
            aria-hidden
          />
          <span className="text-navy">{row.label}</span>
        </div>
      ))}
    </div>
  );
}
