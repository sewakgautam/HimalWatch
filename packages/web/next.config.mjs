/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static-first per CLAUDE.md: no server-rendered pages for public data.
  // Every route in packages/web pre-renders to a static file served
  // directly by Firebase Hosting.
  output: "export",
  images: {
    // next/image's optimization API needs a running server — unavailable
    // under `output: 'export'`.
    unoptimized: true,
  },
  trailingSlash: true,
};

export default nextConfig;
