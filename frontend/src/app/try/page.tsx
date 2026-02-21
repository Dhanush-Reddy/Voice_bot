"use client";

import { useState, useCallback, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";

const VoiceAssistant = dynamic(() => import("@/components/VoiceAssistant"), {
    ssr: false,
    loading: () => <div className="animate-pulse text-slate-400">Loading Assistant...</div>
});

const BACKEND_URL = "/api/backend";

function TryNowContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const agentId = searchParams.get("agent_id");

    const [connectionState, setConnectionState] = useState<
        "idle" | "connecting" | "connected"
    >("idle");
    const [token, setToken] = useState<string>("");
    const [livekitUrl, setLivekitUrl] = useState<string>("");
    const [error, setError] = useState<string>("");

    // PRE-FETCH TOKEN & CONNECT ON MOUNT (Instant-On Optimization)
    useEffect(() => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

        const prefetch = async () => {
            try {
                const url = agentId
                    ? `${BACKEND_URL}/token?participant_name=User&agent_id=${agentId}`
                    : `${BACKEND_URL}/token?participant_name=User`;

                const res = await fetch(url, { signal: controller.signal });
                clearTimeout(timeoutId);

                if (!res.ok) throw new Error("Pre-fetch failed");
                const data = await res.json();
                setToken(data.token);
                setLivekitUrl(data.url);
                console.log("⚡ [PRO] Session pre-warmed & ready for instant connect");
            } catch (err) {
                if (err instanceof Error && err.name === 'AbortError') {
                    console.error("❌ [PRO] Session pre-warm timed out");
                    setError("Initialization timed out. Check your connection.");
                } else {
                    console.error("❌ [PRO] Failed to pre-warm session:", err);
                    setError("Failed to initialize session. Is the backend running?");
                }
            }
        };
        prefetch();
        return () => controller.abort();
    }, [agentId]);

    const handleConnect = useCallback(async () => {
        setConnectionState("connecting");
        console.log("🚀 [PRO] Connecting to session...");

        // Brief delay to allow UI state to update before mounting VoiceAssistant
        setTimeout(() => {
            setConnectionState("connected");
            console.log("✅ [PRO] Connected to session");
        }, 500);
    }, []);

    const handleDisconnect = useCallback(() => {
        setToken("");
        setLivekitUrl("");
        setConnectionState("idle");
        // Reload or redirect back to dashboard
        router.push("/dashboard/agents");
    }, [router]);

    return (
        <main className="relative flex min-h-screen flex-col items-center justify-center px-4 bg-slate-950">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-8 py-6">
                <Link href="/dashboard/agents" className="flex items-center gap-2 text-xs text-slate-400 hover:text-white transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    Back to Agents
                </Link>
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
                <div className="glass-card p-12 flex flex-col items-center gap-8 max-w-md w-full text-center bg-white/[0.02] border border-white/5 rounded-3xl">
                    {/* Idle orb */}
                    <div className="ai-orb idle" />

                    <div className="space-y-3">
                        <h1 className="text-2xl font-bold bg-gradient-to-r from-primary-300 to-primary-500 bg-clip-text text-transparent">
                            Try Your Agent
                        </h1>
                        <p className="text-sm text-slate-400 leading-relaxed max-w-xs">
                            {agentId ? `Testing agent ID: ${agentId}` : "Connecting to default agent..."}
                        </p>
                    </div>

                    <button
                        id="connect-button"
                        className="w-full py-4 rounded-2xl bg-violet-600 hover:bg-violet-500 text-white font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-violet-600/20"
                        onClick={handleConnect}
                        disabled={connectionState === "connecting" || (!token && !error)}
                    >
                        {!token && !error ? (
                            <span className="flex items-center justify-center gap-2">
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                                </svg>
                                Preparing Assistant...
                            </span>
                        ) : connectionState === "connecting" ? (
                            "Connecting…"
                        ) : (
                            "Start Conversation"
                        )}
                    </button>

                    {error && (
                        <p className="text-sm text-red-400 bg-red-400/10 rounded-xl px-4 py-2 border border-red-500/20">
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

export default function TryPage() {
    return (
        <Suspense fallback={
            <div className="flex min-h-screen items-center justify-center bg-slate-950">
                <div className="animate-pulse text-slate-400">Loading optimizer...</div>
            </div>
        }>
            <TryNowContent />
        </Suspense>
    );
}
