import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                primary: {
                    50: "#eef2ff",
                    100: "#e0e7ff",
                    200: "#c7d2fe",
                    300: "#a5b4fc",
                    400: "#818cf8",
                    500: "#6366f1",
                    600: "#4f46e5",
                    700: "#4338ca",
                    800: "#3730a3",
                    900: "#312e81",
                    950: "#1e1b4b",
                },
            },
            fontFamily: {
                sans: ["Inter", "system-ui", "sans-serif"],
            },
            animation: {
                "pulse-ring": "pulse-ring 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                "glow": "glow 2s ease-in-out infinite alternate",
            },
            keyframes: {
                "pulse-ring": {
                    "0%": { transform: "scale(0.9)", opacity: "1" },
                    "50%": { transform: "scale(1.1)", opacity: "0.5" },
                    "100%": { transform: "scale(0.9)", opacity: "1" },
                },
                glow: {
                    "0%": { boxShadow: "0 0 20px rgba(99, 102, 241, 0.3)" },
                    "100%": { boxShadow: "0 0 40px rgba(99, 102, 241, 0.6)" },
                },
            },
        },
    },
    plugins: [],
};

export default config;
