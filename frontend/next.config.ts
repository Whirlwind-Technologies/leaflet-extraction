import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker
  output: "standalone",

  // Enable server actions
  experimental: {
    serverActions: {
      bodySizeLimit: "100mb",
    },
  },

  // Disable React strict mode to avoid double-rendering issues in dev
  reactStrictMode: false,
  
  // Proxy API requests to backend in development
  // Note: This excludes /api/export which has its own Next.js route handler
  async rewrites() {
    return [
      {
        // Proxy v1 API calls to backend
        source: "/api/v1/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
  
  // Image optimization for external images
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
      {
        protocol: "http",
        hostname: "localhost",
      },
      {
        protocol: "http",
        hostname: "127.0.0.1",
      },
      {
        // MinIO in docker network
        protocol: "http",
        hostname: "minio",
      },
    ],
  },
  
  // Logging configuration
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;