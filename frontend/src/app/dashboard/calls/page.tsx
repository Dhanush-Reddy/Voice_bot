"use client";

/**
 * Call History Page — /dashboard/calls  (Sprint 4)
 *
 * Features:
 *  - Searchable, filterable DataTable (status + outcome dropdowns)
 *  - Sliding transcript drawer with dialogue bubbles
 *  - Delete call log with confirmation
 *  - Stat summary cards (total, success rate, avg duration)
 */

import { useEffect, useState, useCallback } from "react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

// ─── Types ────────────────────────────────────────────────────────────────────

interface TranscriptMessage {
    role: "agent" | "user";
    content: string;
    timestamp?: string;
}

interface CallLog {
    id: string;
    agent_id: string;
    agent_name?: string;
    room_name: string;
    status: string;
    outcome?: string;
    duration_seconds: number;
    participant_count?: number;
    transcript?: TranscriptMessage[];
    recording_url?: string;
    created_at?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
    completed: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
    failed: "bg-red-500/10 text-red-400 border border-red-500/20",
    no_answer: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
};

const OUTCOME_STYLES: Record<string, string> = {
    success: "bg-violet-500/10 text-violet-400 border border-violet-500/20",
    not_interested: "bg-slate-500/10 text-slate-400 border border-slate-500/20",
    no_answer: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
    completed: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
    failed: "bg-red-500/10 text-red-400 border border-red-500/20",
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

// ─── Transcript Drawer ────────────────────────────────────────────────────────

function TranscriptDrawer({
    call,
    onClose,
}: {
    call: CallLog | null;
    onClose: () => void;
}) {
    if (!call) return null;

    const messages = call.transcript || [];

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity"
                onClick={onClose}
            />

            {/* Drawer */}
            <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-[#0f1117] border-l border-white/10 z-50 flex flex-col shadow-2xl">
                {/* Header */}
                <div className="flex items-start justify-between p-6 border-b border-white/10">
                    <div>
                        <h2 className="text-lg font-bold text-white">Call Transcript</h2>
                        <p className="text-xs text-slate-500 mt-1 font-mono">{call.room_name}</p>
                        <div className="flex items-center gap-2 mt-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[call.status] || "bg-slate-500/10 text-slate-400"}`}>
                                {call.status}
                            </span>
                            {call.outcome && (
                                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${OUTCOME_STYLES[call.outcome] || "bg-slate-500/10 text-slate-400"}`}>
                                    {call.outcome}
                                </span>
                            )}
                            <span className="text-xs text-slate-500">
                                {formatDuration(call.duration_seconds)} · {formatDate(call.created_at)}
                            </span>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                        aria-label="Close transcript"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center">
                            <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center mb-3">
                                <svg className="w-6 h-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                                </svg>
                            </div>
                            <p className="text-sm text-slate-500">No transcript available for this call.</p>
                        </div>
                    ) : (
                        messages.map((msg, i) => {
                            const isAgent = msg.role === "agent";
                            return (
                                <div key={i} className={`flex gap-3 ${isAgent ? "" : "flex-row-reverse"}`}>
                                    {/* Avatar */}
                                    <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${isAgent ? "bg-violet-500/20 text-violet-400" : "bg-blue-500/20 text-blue-400"}`}>
                                        {isAgent ? "AI" : "U"}
                                    </div>
                                    {/* Bubble */}
                                    <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${isAgent ? "bg-white/5 text-slate-200 rounded-tl-sm" : "bg-violet-600/20 text-violet-100 rounded-tr-sm"}`}>
                                        {msg.content}
                                        {msg.timestamp && (
                                            <p className="text-[10px] text-slate-500 mt-1">{msg.timestamp}</p>
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer */}
                {call.recording_url && (
                    <div className="p-4 border-t border-white/10">
                        <a
                            href={call.recording_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 w-full px-4 py-2.5 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-sm font-medium transition-colors"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                            </svg>
                            Play Recording
                        </a>
                    </div>
                )}
            </div>
        </>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CallHistoryPage() {
    const [calls, setCalls] = useState<CallLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("");
    const [outcomeFilter, setOutcomeFilter] = useState("");
    const [selectedCall, setSelectedCall] = useState<CallLog | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    const fetchCalls = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams();
            if (statusFilter) params.set("status", statusFilter);
            if (outcomeFilter) params.set("outcome", outcomeFilter);
            const res = await fetch(`${BACKEND_URL}/api/calls?${params}`);
            if (!res.ok) throw new Error("Failed to load calls");
            setCalls(await res.json());
        } catch {
            setError("Could not load call history.");
        } finally {
            setLoading(false);
        }
    }, [statusFilter, outcomeFilter]);

    useEffect(() => {
        fetchCalls();
    }, [fetchCalls]);

    const handleDelete = async (callId: string) => {
        if (!confirm("Delete this call log? This cannot be undone.")) return;
        setDeletingId(callId);
        try {
            await fetch(`${BACKEND_URL}/api/calls/${callId}`, { method: "DELETE" });
            setCalls((prev) => prev.filter((c) => c.id !== callId));
            if (selectedCall?.id === callId) setSelectedCall(null);
        } catch {
            alert("Failed to delete call log.");
        } finally {
            setDeletingId(null);
        }
    };

    const handleRowClick = async (call: CallLog) => {
        // Fetch full call (with transcript) on click
        try {
            const res = await fetch(`${BACKEND_URL}/api/calls/${call.id}`);
            if (res.ok) setSelectedCall(await res.json());
            else setSelectedCall(call);
        } catch {
            setSelectedCall(call);
        }
    };

    const filtered = calls.filter(
        (c) =>
            c.room_name.toLowerCase().includes(search.toLowerCase()) ||
            (c.agent_name || c.agent_id).toLowerCase().includes(search.toLowerCase())
    );

    // Stats
    const total = calls.length;
    const successful = calls.filter((c) => c.outcome === "success").length;
    const successRate = total > 0 ? Math.round((successful / total) * 100) : 0;
    const avgDuration =
        total > 0
            ? Math.round(calls.reduce((s, c) => s + c.duration_seconds, 0) / total)
            : 0;

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
                <button
                    onClick={fetchCalls}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white text-sm transition-colors border border-white/10"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                    </svg>
                    Refresh
                </button>
            </div>

            {/* Stat Cards */}
            {!loading && total > 0 && (
                <div className="grid grid-cols-3 gap-4">
                    {[
                        { label: "Total Calls", value: total, icon: "📞" },
                        { label: "Success Rate", value: `${successRate}%`, icon: "✅" },
                        { label: "Avg Duration", value: formatDuration(avgDuration), icon: "⏱️" },
                    ].map((stat) => (
                        <div key={stat.label} className="rounded-2xl bg-white/[0.03] border border-white/5 p-4">
                            <div className="text-xl mb-1">{stat.icon}</div>
                            <div className="text-2xl font-bold text-white">{stat.value}</div>
                            <div className="text-xs text-slate-500 mt-0.5">{stat.label}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Filters */}
            <div className="flex gap-3 flex-wrap">
                {/* Search */}
                <div className="relative flex-1 min-w-[200px]">
                    <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                    </svg>
                    <input
                        type="text"
                        placeholder="Search by room or agent…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                    />
                </div>

                {/* Status filter */}
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-300 focus:outline-none focus:border-violet-500/50 transition-colors"
                >
                    <option value="">All Statuses</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="no_answer">No Answer</option>
                </select>

                {/* Outcome filter */}
                <select
                    value={outcomeFilter}
                    onChange={(e) => setOutcomeFilter(e.target.value)}
                    className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-300 focus:outline-none focus:border-violet-500/50 transition-colors"
                >
                    <option value="">All Outcomes</option>
                    <option value="success">Success</option>
                    <option value="not_interested">Not Interested</option>
                    <option value="no_answer">No Answer</option>
                </select>
            </div>

            {/* Table */}
            {loading ? (
                <div className="space-y-2">
                    {[1, 2, 3, 4, 5].map((i) => (
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
                    <h3 className="text-lg font-semibold text-white mb-2">No calls found</h3>
                    <p className="text-sm text-slate-500 max-w-xs">
                        {search || statusFilter || outcomeFilter
                            ? "Try adjusting your filters."
                            : "Call logs will appear here after your agents complete their first conversations."}
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
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Outcome</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Duration</th>
                                <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
                                <th className="px-5 py-3" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.03]">
                            {filtered.map((call) => (
                                <tr
                                    key={call.id}
                                    onClick={() => handleRowClick(call)}
                                    className="hover:bg-white/[0.02] transition-colors cursor-pointer group"
                                >
                                    <td className="px-5 py-4 text-white font-mono text-xs">{call.room_name}</td>
                                    <td className="px-5 py-4 text-slate-400 text-xs">
                                        {call.agent_name || (
                                            <span className="font-mono">{call.agent_id.slice(0, 8)}…</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4">
                                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[call.status] || "bg-slate-500/10 text-slate-400"}`}>
                                            {call.status}
                                        </span>
                                    </td>
                                    <td className="px-5 py-4">
                                        {call.outcome ? (
                                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${OUTCOME_STYLES[call.outcome] || "bg-slate-500/10 text-slate-400"}`}>
                                                {call.outcome}
                                            </span>
                                        ) : (
                                            <span className="text-slate-600 text-xs">—</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 text-slate-400 tabular-nums">{formatDuration(call.duration_seconds)}</td>
                                    <td className="px-5 py-4 text-slate-500 text-xs">{formatDate(call.created_at)}</td>
                                    <td className="px-5 py-4">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(call.id); }}
                                            disabled={deletingId === call.id}
                                            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-all"
                                            aria-label="Delete call"
                                        >
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                                <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                            </svg>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Transcript Drawer */}
            {selectedCall && (
                <TranscriptDrawer
                    call={selectedCall}
                    onClose={() => setSelectedCall(null)}
                />
            )}
        </div>
    );
}
