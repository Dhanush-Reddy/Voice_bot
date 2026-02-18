"use client";

/**
 * Call History Page — /dashboard/calls
 *
 * Displays a searchable table of all past calls with outcome badges.
 * Sprint 4 will add: transcript drawer and audio playback.
 */

import { useEffect, useState } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface CallLog {
    id: string;
    agent_id: string;
    room_name: string;
    status: string;
    outcome?: string;
    duration_seconds: number;
    created_at?: string;
}

const OUTCOME_STYLES: Record<string, string> = {
    success: "bg-emerald-500/10 text-emerald-400",
    not_interested: "bg-red-500/10 text-red-400",
    no_answer: "bg-orange-500/10 text-orange-400",
    completed: "bg-blue-500/10 text-blue-400",
    failed: "bg-red-500/10 text-red-400",
};

function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDate(dateStr?: string): string {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
    });
}

export default function CallHistoryPage() {
    const [calls, setCalls] = useState<CallLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");

    useEffect(() => {
        const fetchCalls = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/calls`);
                if (!res.ok) throw new Error("Failed to load calls");
                setCalls(await res.json());
            } catch {
                setError("Could not load call history.");
            } finally {
                setLoading(false);
            }
        };
        fetchCalls();
    }, []);

    const filtered = calls.filter(
        (c) =>
            c.room_name.toLowerCase().includes(search.toLowerCase()) ||
            c.agent_id.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Call History</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Review past calls, transcripts, and outcomes.
                    </p>
                </div>
            </div>

            {/* Search */}
            <div className="relative">
                <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <input
                    type="text"
                    placeholder="Search by room name or agent ID…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                />
            </div>

            {/* Table */}
            {loading ? (
                <div className="space-y-2">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-14 rounded-xl bg-white/[0.02] border border-white/5 animate-pulse" />
                    ))}
                </div>
            ) : error ? (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                    {error}
                </div>
            ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center mb-4">
                        <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">No calls yet</h3>
                    <p className="text-sm text-slate-500 max-w-xs">
                        Call logs will appear here after your agents complete their first conversations.
                    </p>
                </div>
            ) : (
                <div className="rounded-2xl border border-white/5 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/5 bg-white/[0.02]">
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Room</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Agent</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Duration</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.03]">
                            {filtered.map((call) => (
                                <tr key={call.id} className="hover:bg-white/[0.02] transition-colors">
                                    <td className="px-5 py-4 text-white font-mono text-xs">{call.room_name}</td>
                                    <td className="px-5 py-4 text-slate-400 font-mono text-xs">{call.agent_id.slice(0, 8)}…</td>
                                    <td className="px-5 py-4">
                                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${OUTCOME_STYLES[call.outcome || call.status] || "bg-slate-500/10 text-slate-400"}`}>
                                            {call.outcome || call.status}
                                        </span>
                                    </td>
                                    <td className="px-5 py-4 text-slate-400">{formatDuration(call.duration_seconds)}</td>
                                    <td className="px-5 py-4 text-slate-500 text-xs">{formatDate(call.created_at)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
