/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    images: {
        unoptimized: true,
    },
    env: {
        NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
        NEXT_PUBLIC_LIVEKIT_URL: process.env.LIVEKIT_URL || "",
    },
};

module.exports = nextConfig;
