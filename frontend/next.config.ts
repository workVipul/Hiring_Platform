import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next-webpack",
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
