/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lint is run separately (npm run lint); don't fail the production build on it.
  eslint: { ignoreDuringBuilds: true },
  // Produce a slim standalone server bundle for the Docker image.
  output: "standalone",
};

module.exports = nextConfig;
