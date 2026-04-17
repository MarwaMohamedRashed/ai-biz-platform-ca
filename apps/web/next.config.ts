import createNextIntlPlugin from 'next-intl/plugin'
import type { NextConfig } from 'next'

const withNextIntl = createNextIntlPlugin('./i18n/request.ts')

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname
  },
  allowedDevOrigins: ['127.0.0.1']
}

export default withNextIntl(nextConfig)