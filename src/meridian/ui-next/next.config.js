/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // API requests will be proxied to Python backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8502/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
