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
  // Explicitly define public runtime environment variables for Railway
  env: {
    NEXT_PUBLIC_GOOGLE_CLIENT_ID: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
    NEXT_PUBLIC_GOOGLE_REDIRECT_URI: process.env.NEXT_PUBLIC_GOOGLE_REDIRECT_URI,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
};

module.exports = nextConfig;