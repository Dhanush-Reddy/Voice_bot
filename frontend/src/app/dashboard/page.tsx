"use client";

/**
 * Dashboard Overview Page — /dashboard
 * Compact, information-dense layout with real data from the backend.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { StatCard } from "@/components/StatCard";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface Agent {
    id: string;
    name: string;
    is_active: boolean;
    language: string;
    model: string;
}

interface CallLog {
    id: string;
    agent_id: string;
    status: string;
    outcome?: string;
    duration_seconds: number;
    created_at?: string;
}

interface HealthData {
    status: string;
    pool?: { active: number; idle: number };
    calls?: { total: number; completed: number; failed: number };
}



export default function DashboardPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [calls, setCalls] = useState<CallLog[]>([]);
    const [health, setHealth] = useState<HealthData | null>(null);
    const [loading, setLoading] = useState(true);
    const [backendDown, setBackendDown] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [agentsRes, callsRes, healthRes] = await Promise.all([
                    fetch(`${BACKEND_URL}/api/agents`),
                    fetch(`${BACKEND_URL}/api/calls?limit=50`),
                    fetch(`${BACKEND_URL}/api/health`),
                ]);
                if (!agentsRes.ok) throw new Error("backend down");
                setAgents(await agentsRes.json());
                if (callsRes.ok) setCalls(await callsRes.json());
                if (healthRes.ok) setHealth(await healthRes.json());
                setBackendDown(false);
            } catch (err) {
                console.error("Failed to fetch dashboard data:", err);
                setBackendDown(true);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    const activeAgents = agents.filter((a) => a.is_active).length;
    const successCalls = calls.filter((c) => c.outcome === "success").length;
    const successRate = calls.length > 0 ? Math.round((successCalls / calls.length) * 100) : 0;
    const totalMinutes = Math.round(calls.reduce((s, c) => s + c.duration_seconds, 0) / 60);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                    <p className="text-sm text-slate-500 mt-0.5">Overview of your AI calling agency platform.</p>
                </div>
                <Link
                    href="/dashboard/agents/new"
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold transition-colors"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    New Agent
                </Link>
            </div>

            {/* Backend down banner */}
            {!loading && backendDown && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm">
                    <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                    </svg>
                    <span><strong>Backend offline.</strong> Run <code className="bg-white/10 px-1.5 py-0.5 rounded text-xs">uvicorn api.routes:app --reload --port 8000</code> in the backend folder.</span>
                </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    label="Total Agents"
                    value={loading ? "—" : agents.length}
                    sub={loading ? "" : `${activeAgents} active`}
                    href="/dashboard/agents"
                    color="bg-violet-500/10"
                    icon={<svg className="w-5 h-5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" /></svg>}
                />
                <StatCard
                    label="Total Calls"
                    value={loading ? "—" : calls.length}
                    sub={loading ? "" : `${successRate}% success rate`}
                    href="/dashboard/calls"
                    color="bg-blue-500/10"
                    icon={<svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" /></svg>}
                />
                <StatCard
                    label="Minutes Used"
                    value={loading ? "—" : totalMinutes}
                    sub="across all calls"
                    color="bg-emerald-500/10"
                    icon={<svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
                />
                <StatCard
                    label="Pool Status"
                    value={loading ? "—" : health ? `${health.pool?.idle ?? 0} idle` : "—"}
                    sub={health ? `${health.pool?.active ?? 0} active bots` : "backend offline"}
                    color="bg-orange-500/10"
                    icon={<svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z" /></svg>}
                />
            </div>

            {/* Two column: Recent Agents + Recent Calls */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Recent Agents */}
                <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-sm font-semibold text-white">Recent Agents</h2>
                        <Link href="/dashboard/agents" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">View all →</Link>
                    </div>
                    {loading ? (
                        <div className="space-y-2">
                            {[1,2,3].map(i => <div key={i} className="h-12 rounded-xl bg-white/[0.02] animate-pulse" />)}
                        </div>
                    ) : agents.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-10 text-center">
                            <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center mb-3">
                                <svg className="w-5 h-5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
                            </div>
                            <p className="text-sm text-slate-500">No agents yet</p>
                            <Link href="/dashboard/agents/new" className="mt-2 text-xs text-violet-400 hover:text-violet-300 transition-colors">Create your first agent →</Link>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {agents.slice(0, 5).map((agent) => (
                                <Link key={agent.id} href={`/dashboard/agents/${agent.id}`}
                                    className="flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/[0.04] transition-colors group">
                                    <div className="flex items-center gap-3">
                                        <div className="w-7 h-7 rounded-lg bg-violet-500/10 flex items-center justify-center flex-shrink-0">
                                            <svg className="w-3.5 h-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5" /></svg>
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white">{agent.name}</p>
                                            <p className="text-xs text-slate-500">{agent.language}</p>
                                        </div>
                                    </div>
                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${agent.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-500"}`}>
                                        {agent.is_active ? "Active" : "Inactive"}
                                    </span>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>

                {/* Recent Calls */}
                <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-sm font-semibold text-white">Recent Calls</h2>
                        <Link href="/dashboard/calls" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">View all →</Link>
                    </div>
                    {loading ? (
                        <div className="space-y-2">
                            {[1,2,3].map(i => <div key={i} className="h-12 rounded-xl bg-white/[0.02] animate-pulse" />)}
                        </div>
                    ) : calls.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-10 text-center">
                            <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center mb-3">
                                <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" /></svg>
                            </div>
                            <p className="text-sm text-slate-500">No calls yet</p>
                            <p className="text-xs text-slate-600 mt-1">Calls will appear here after your first session</p>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {calls.slice(0, 5).map((call) => {
                                const mins = Math.floor(call.duration_seconds / 60);
                                const secs = call.duration_seconds % 60;
                                return (
                                    <div key={call.id} className="flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/[0.04] transition-colors">
                                        <div>
                                            <p className="text-sm font-medium text-white">{call.agent_id.slice(0, 12)}…</p>
                                            <p className="text-xs text-slate-500">{mins}:{secs.toString().padStart(2, "0")} · {call.created_at ? new Date(call.created_at).toLocaleDateString() : "—"}</p>
                                        </div>
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                                            call.outcome === "success" ? "bg-emerald-500/10 text-emerald-400" :
                                            call.status === "failed" ? "bg-red-500/10 text-red-400" :
                                            "bg-slate-500/10 text-slate-400"
                                        }`}>
                                            {call.outcome || call.status}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>

            {/* Quick links */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                    { label: "Knowledge Base", href: "/dashboard/knowledge", icon: "📚", desc: "Upload documents" },
                    { label: "Analytics", href: "/dashboard/analytics", icon: "📊", desc: "View insights" },
                    { label: "Call History", href: "/dashboard/calls", icon: "📞", desc: "Browse transcripts" },
                    { label: "New Agent", href: "/dashboard/agents/new", icon: "🤖", desc: "Configure agent" },
                ].map((item) => (
                    <Link key={item.href} href={item.href}
                        className="flex flex-col gap-1 p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/10 transition-all">
                        <span className="text-xl">{item.icon}</span>
                        <p className="text-sm font-medium text-white">{item.label}</p>
                        <p className="text-xs text-slate-500">{item.desc}</p>
                    </Link>
                ))}
            </div>
        </div>
    );
}
