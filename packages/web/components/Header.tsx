import Link from "next/link";

export function Header() {
  return (
    <header className="flex items-center justify-between bg-navy px-4 py-3 text-white">
      <Link href="/" className="flex flex-col leading-tight">
        <span className="text-lg font-semibold">HimalWatch</span>
        <span className="font-devanagari text-xs text-white/70">
          हिमताल र हिमनदी अनुगमन
        </span>
      </Link>
      <nav className="flex gap-4 text-sm text-white/80">
        <Link href="/methodology" className="hover:text-white">
          Methodology
        </Link>
        <Link href="/about" className="hover:text-white">
          About
        </Link>
      </nav>
    </header>
  );
}
