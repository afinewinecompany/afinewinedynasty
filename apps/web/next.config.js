/** @type {import('next').NextConfig} */
const nextConfig = {
  // Note: 'standalone' mode removed for Railway NIXPACKS compatibility
  // NIXPACKS installs full node_modules, so we can use 'npm start'
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
};

module.exports = nextConfig;