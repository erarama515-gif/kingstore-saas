/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.BUILD_STANDALONE === "1" ? "standalone" : undefined,
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    // In dev, proxy /api to the Flask backend so the browser doesn't see
    // CORS at all. In prod, nginx does the same proxying.
    return [
      {
        source: "/api/:path*",
        destination:
          (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000") + "/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
