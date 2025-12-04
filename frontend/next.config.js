/** @type {import('next').NextConfig} */
const path = require('path')

const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || `http://localhost:${process.env.API_PORT || '3102'}`,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || `ws://localhost:${process.env.API_PORT || '3102'}/ws`,
    // Pass DEBUG flag to frontend (only NEXT_PUBLIC_* vars are available in browser)
    NEXT_PUBLIC_DEBUG: process.env.DEBUG || process.env.NEXT_PUBLIC_DEBUG || 'false',
  },
  webpack: (config) => {
    config.resolve = config.resolve || {}
    config.resolve.alias = config.resolve.alias || {}
    config.resolve.alias['@'] = path.join(__dirname, 'src')
    return config
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || `http://localhost:${process.env.API_PORT || '3102'}`
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
