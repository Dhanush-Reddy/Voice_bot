"use client";

import { useState, useCallback, useEffect } from "react";
import VoiceAssistant from "@/components/VoiceAssistant";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";
// NOTE: Using "" will use Netlify proxy /api/token. 
// Using absolute URL (e.g. Cloud Run) is faster.

export default function Home() {
    const [connectionState, setConnectionState] = useState<
        "idle" | "connecting" | "connected"
    >("idle");
    const [token, setToken] = useState<string>("");
    const [livekitUrl, setLivekitUrl] = useState<string>("");
    const [error, setError] = useState<string>("");

    // PRE-FETCH TOKEN & CONNECT ON MOUNT (Instant-On Optimization)
    useEffect(() => {
        const prefetch = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/token?participant_name=User`);
                if (!res.ok) throw new Error("Pre-fetch failed");
                const data = await res.json();
                setToken(data.token);
                setLivekitUrl(data.url);
                console.log("⚡ [PRO] Session pre-warmed & ready for instant connect");
            } catch (err) {
                console.error("Failed to pre-warm session:", err);
            }
        };
        prefetch();
    }, []);

    const handleConnect = useCallback(async () => {
        setConnectionState("connected");
        console.log("🚀 [PRO] Instant connect triggered");
    }, []);

    const handleDisconnect = useCallback(() => {
        setToken("");
        setLivekitUrl("");
        setConnectionState("idle");
        // Optionally reload to get a new pre-warmed session
        window.location.reload();
    }, []);

    return (
        <main className="relative flex min-h-screen flex-col items-center justify-center px-4">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-8 py-6">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
                        <svg
                            className="w-4 h-4 text-white"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                            />
                        </svg>
                    </div>
                    <span className="text-sm font-semibold tracking-wide text-slate-300">
                        Voice AI
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span
                        className={`status-dot ${connectionState === "connected" ? "connected" : "disconnected"
                            }`}
                    />
                    <span className="text-xs text-slate-400 uppercase tracking-wider">
                        {connectionState === "connected" ? "Live" : "Offline"}
                    </span>
                </div>
            </div>

            {/* Main content */}
            {connectionState === "connected" && token && livekitUrl ? (
                <VoiceAssistant
                    token={token}
                    url={livekitUrl}
                    onDisconnect={handleDisconnect}
                />
            ) : (
                <div className="glass-card p-12 flex flex-col items-center gap-8 max-w-md w-full text-center">
                    {/* Idle orb */}
                    <div className="ai-orb idle" />

                    <div className="space-y-3">
                        <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-300 to-primary-500 bg-clip-text text-transparent">
                            Voice AI Assistant
                        </h1>
                        <p className="text-sm text-slate-400 leading-relaxed max-w-xs">
                            Tap below to connect and start a real-time voice conversation with your AI assistant.
                        </p>
                    </div>

                    <button
                        id="connect-button"
                        className="btn-connect"
                        onClick={handleConnect}
                        disabled={connectionState === "connecting"}
                    >
                        {connectionState === "connecting" ? (
                            <span className="flex items-center gap-2">
                                <svg
                                    className="animate-spin h-4 w-4"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                >
                                    <circle
                                        className="opacity-25"
                                        cx="12"
                                        cy="12"
                                        r="10"
                                        stroke="currentColor"
                                        strokeWidth="4"
                                    />
                                    <path
                                        className="opacity-75"
                                        fill="currentColor"
                                        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                                    />
                                </svg>
                                Connecting…
                            </span>
                        ) : (
                            "Tap to Connect"
                        )}
                    </button>

                    {error && (
                        <p className="text-sm text-red-400 bg-red-400/10 rounded-xl px-4 py-2">
                            {error}
                        </p>
                    )}
                </div>
            )}

            {/* Footer */}
            <p className="absolute bottom-6 text-xs text-slate-600">
                Powered by Gemini 2.0 Flash · LiveKit · Pipecat
            </p>
        </main>
    );
}
