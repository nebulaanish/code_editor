import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  // Enable React strict mode
  reactStrictMode: true,
  // Configure images if needed
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
