import type { NextConfig } from "next";

const API_ORIGIN = "http://127.0.0.1:4000";

const nextConfig: NextConfig = {
  // Workspace packages ship TypeScript source — let Next compile them.
  transpilePackages: ["@captionx/shared"],
  async rewrites() {
    return [
      {
        // Browser-facing proxy: the dashboard calls same-origin /api/* and the
        // Next.js server forwards it to the Hono API inside the sandbox.
        // This keeps the browser independent of the API host/port (works in
        // the preview environment where the browser is not the sandbox).
        source: "/api/:path*",
        destination: `${API_ORIGIN}/:path*`,
      },
    ];
  },
};

export default nextConfig;
