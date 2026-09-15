"use client";

interface YearSliderProps {
  years: number[]; // descending, e.g. [2025, 2024, ...]
  selected: number | null; // null = "latest" (no year filter applied)
  onChange: (year: number | null) => void;
}

export function YearSlider({ years, selected, onChange }: YearSliderProps) {
  if (years.length === 0) return null;
  const oldest = years[years.length - 1];
  const newest = years[0];
  const value = selected ?? newest;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-black/10 bg-white/95 px-4 py-2 shadow-md backdrop-blur">
      <span className="text-xs font-medium text-navy/70">{oldest}</span>
      <input
        type="range"
        min={oldest}
        max={newest}
        step={1}
        value={value}
        onChange={(e) => {
          const year = Number(e.target.value);
          onChange(year === newest ? null : year);
        }}
        className="w-40 accent-navy"
        aria-label="Extraction year"
      />
      <span className="text-xs font-medium text-navy/70">{newest}</span>
      <span className="ml-2 rounded bg-navy px-2 py-0.5 text-xs font-semibold text-white">
        {selected === null ? `${newest} (latest)` : selected}
      </span>
    </div>
  );
}
