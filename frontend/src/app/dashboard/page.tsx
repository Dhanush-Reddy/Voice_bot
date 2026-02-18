"use client";

/**
 * Dashboard Overview Page — /dashboard
 *
 * Shows high-level metrics (total calls, agents, minutes) and quick links.
 * Data is fetched from the backend API.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { StatCard } from "@/components/dashboard/StatCard";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface Agent {
    id: string;
    name: string;
    is_active: boolean;
    language: string;
}

export default function DashboardPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/agents`);
                if (res.ok) {
                    const data = await res.json();
                    setAgents(data);
                }
            } catch (err) {
                console.error("Failed to fetch agents:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const activeAgents = agents.filter((a) => a.is_active).length;

    return (
        <div className="space-y-8">
            {/* Page Header */}
            <div>
                <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                <p className="text-sm text-slate-500 mt-1">
                    Overview of your AI calling agency platform.
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                <StatCard
                    label="Total Agents"
                    value={loading ? "—" : agents.length}
                    accentColor="violet"
                    icon={
                        <svg className="w-8 h-8 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                        </svg>
                    }
                />
                <StatCard
                    label="Active Agents"
                    value={loading ? "—" : activeAgents}
                    accentColor="green"
                    icon={
                        <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    }
                />
                <StatCard
                    label="Total Calls"
                    value="—"
                    accentColor="blue"
                    icon={
                        <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                        </svg>
                    }
                />
                <StatCard
                    label="Minutes Used"
                    value="—"
                    accentColor="orange"
                    icon={
                        <svg className="w-8 h-8 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    }
                />
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Link
                    href="/dashboard/agents"
                    className="group flex items-center gap-4 p-5 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-violet-500/30 transition-all duration-200"
                >
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center group-hover:bg-violet-500/20 transition-colors">
                        <svg className="w-5 h-5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-white">Create New Agent</p>
                        <p className="text-xs text-slate-500">Configure a new AI voice agent</p>
                    </div>
                </Link>

                <Link
                    href="/dashboard/calls"
                    className="group flex items-center gap-4 p-5 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-blue-500/30 transition-all duration-200"
                >
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
                        <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-white">View Call History</p>
                        <p className="text-xs text-slate-500">Browse transcripts and outcomes</p>
                    </div>
                </Link>
            </div>

            {/* Recent Agents */}
            {!loading && agents.length > 0 && (
                <div>
                    <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
                        Recent Agents
                    </h2>
                    <div className="space-y-2">
                        {agents.slice(0, 5).map((agent) => (
                            <Link
                                key={agent.id}
                                href={`/dashboard/agents/${agent.id}`}
                                className="flex items-center justify-between p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
                                        <svg className="w-4 h-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5" />
                                        </svg>
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-white">{agent.name}</p>
                                        <p className="text-xs text-slate-500">{agent.language}</p>
                                    </div>
                                </div>
                                <span className={`text-xs px-2 py-1 rounded-full font-medium ${agent.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-500"}`}>
                                    {agent.is_active ? "Active" : "Inactive"}
                                </span>
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
