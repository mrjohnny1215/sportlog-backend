/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NOTE: We intentionally do NOT use rewrites to proxy /api to the backend.
  // Vercel blocks rewrites whose destination is an external domain (e.g. a
  // Cloudflare/tunnel URL), surfacing DNS_HOSTNAME_RESOLVE_FAILED. Instead the
  // browser calls the backend directly via the absolute NEXT_PUBLIC_API_BASE_URL
  // (the tunnel is HTTPS, so there is no Mixed-Content block). The FastAPI
  // backend already sends `Access-Control-Allow-Origin: *`, so CORS is fine.
};

module.exports = nextConfig;
