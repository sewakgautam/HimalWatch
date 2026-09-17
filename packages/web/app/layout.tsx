import type { Metadata } from "next";
import { Noto_Sans_Devanagari } from "next/font/google";
import localFont from "next/font/local";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});
// Nepali headers (हिमताल र हिमनदी अनुगमन) per spec §6 — Geist has no
// Devanagari glyphs.
const notoDevanagari = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  variable: "--font-noto-devanagari",
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "HimalWatch — हिमताल र हिमनदी अनुगमन",
  description:
    "Weekly Sentinel-2 monitoring of Nepal's glaciers and glacial lakes — complementary to the official government inventory.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${notoDevanagari.variable} antialiased`}
      >
        <NuqsAdapter>{children}</NuqsAdapter>
      </body>
    </html>
  );
}
