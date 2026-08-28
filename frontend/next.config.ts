import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next.js blocks cross-origin requests to dev-only assets by default, which
  // breaks the dev server when the app is reached through a remote proxy domain
  // (e.g. a cloud GPU pod on *.proxy.runpod.net). Whitelist that here; dev-only,
  // no effect on production builds.
  allowedDevOrigins: ['*.proxy.runpod.net'],
  experimental: {
    serverActions: {
      bodySizeLimit: '100mb',
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;