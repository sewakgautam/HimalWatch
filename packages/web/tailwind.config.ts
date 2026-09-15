import typography from "@tailwindcss/typography";
import type { Config } from "tailwindcss";

// Palette per docs/HIMALWATCH_SPEC.md §6 — deep navy header, off-white
// background, teal for glaciers, purple for lakes, red reserved for PDGL
// lakes (the one visual cue that stays on regardless of filter state).
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        navy: "#1a2e3b",
        offwhite: "#f5f5f0",
        glacier: "#2a9d8f",
        lake: "#7b6fd8",
        pdgl: "#d84a4a",
      },
      fontFamily: {
        devanagari: ["var(--font-noto-devanagari)", "sans-serif"],
      },
    },
  },
  plugins: [typography],
};
export default config;
