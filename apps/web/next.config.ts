import createNextIntlPlugin from "next-intl/plugin"
import type { NextConfig } from "next"

const withNextIntl = createNextIntlPlugin("./i18n/request.ts")

const nextConfig: NextConfig = {
  // Required by the production Dockerfile (copies .next/standalone).
  output: "standalone",
}

export default withNextIntl(nextConfig)
