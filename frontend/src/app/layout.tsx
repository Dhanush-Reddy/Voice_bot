import type { Metadata } from "next";
import "./globals.css";
import AuthProvider from "@/components/AuthProvider";

export const metadata: Metadata = {
    title: "Voice AI Assistant",
    description:
        "Real-time human-like voice AI assistant powered by Gemini and LiveKit",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark" suppressHydrationWarning>
            <body className="bg-gradient-animated min-h-screen antialiased">
                <AuthProvider>
                    <div className="noise-overlay" aria-hidden="true" />
                    {children}
                </AuthProvider>
            </body>
        </html>
    );
}
