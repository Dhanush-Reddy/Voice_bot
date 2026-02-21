"use client";

/**
 * Analytics Dashboard — /dashboard/analytics
 *
 * Sprint 6: High-level charts and business intelligence.
 *
 * Charts (pure CSS/SVG — no external chart library needed):
 *  - Calls per day (7-day bar chart)
 *  - Outcome distribution (donut chart)
 *  - Top agents by call volume
 *  - Avg duration trend
 */

import { useEffect, useState } from "react";

const BACKEND_URL = "/api/backend";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CallLog {
    id: string;
    agent_id: string;
    agent_name?: string;
    status: string;
    outcome?: string;
    duration_seconds: number;
    created_at?: string;
}

interface DayBucket {
    label: string;
    count: number;
}

interface AgentStat {
    agent_id: string;
    name: string;
    calls: number;
    success: number;
    avgDuration: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDuration(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
}

function getLast7Days(): string[] {
    const days = [];
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        days.push(d.toISOString().split("T")[0]);
    }
    return days;
}

function dayLabel(iso: string): string {
    return new Date(iso).toLocaleDateString("en-IN", { weekday: "short" });
}

// ─── Mini Bar Chart ───────────────────────────────────────────────────────────

function BarChart({ data }: { data: DayBucket[] }) {
    const max = Math.max(...data.map((d) => d.count), 1);
    return (
        <div className="flex items-end gap-2 h-32">
            {data.map((d) => (
                <div key={d.label} className="flex-1 flex flex-col items-center gap-1">
                    <div className="w-full flex items-end justify-center" style={{ height: "100px" }}>
                        <div
                            className="w-full rounded-t-md bg-violet-500/60 hover:bg-violet-500 transition-all"
                            style={{ height: `${Math.max((d.count / max) * 100, d.count > 0 ? 8 : 2)}px` }}
                            title={`${d.count} calls`}
                        />
                    </div>
                    <span className="text-[10px] text-slate-500">{d.label}</span>
                    <span className="text-[10px] text-slate-400 font-medium">{d.count}</span>
                </div>
            ))}
        </div>
    );
}

// ─── Donut Chart ──────────────────────────────────────────────────────────────

function DonutChart({ slices }: { slices: { label: string; value: number; color: string }[] }) {
    const total = slices.reduce((s, x) => s + x.value, 0);
    if (total === 0) {
        return (
            <div className="flex items-center justify-center h-32 text-slate-600 text-sm">No data</div>
        );
    }

    let offset = 0;
    const r = 40;
    const cx = 60;
    const cy = 60;
    const circumference = 2 * Math.PI * r;

    return (
        <div className="flex items-center gap-6">
            <svg width="120" height="120" viewBox="0 0 120 120">
                {slices.map((slice) => {
                    const pct = slice.value / total;
                    const dash = pct * circumference;
                    const gap = circumference - dash;
                    const rotation = offset * 360 - 90;
                    offset += pct;
                    return (
                        <circle
                            key={slice.label}
                            cx={cx}
                            cy={cy}
                            r={r}
                            fill="none"
                            stroke={slice.color}
                            strokeWidth="18"
                            strokeDasharray={`${dash} ${gap}`}
                            transform={`rotate(${rotation} ${cx} ${cy})`}
                            className="transition-all"
                        />
                    );
                })}
                <text x={cx} y={cy - 4} textAnchor="middle" className="fill-white text-xs font-bold" fontSize="14">{total}</text>
                <text x={cx} y={cy + 12} textAnchor="middle" className="fill-slate-500" fontSize="9">total</text>
            </svg>
            <div className="space-y-2">
                {slices.map((s) => (
                    <div key={s.label} className="flex items-center gap-2 text-xs">
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: s.color }} />
                        <span className="text-slate-400">{s.label}</span>
                        <span className="text-white font-medium ml-auto pl-4">{s.value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
    const [calls, setCalls] = useState<CallLog[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${BACKEND_URL}/calls?limit=500`)
            .then((r) => r.json())
            .then(setCalls)
            .catch(() => { })
            .finally(() => setLoading(false));
    }, []);

    // ── Calls per day (last 7 days) ──────────────────────────────────────────
    const days = getLast7Days();
    const callsPerDay: DayBucket[] = days.map((day) => ({
        label: dayLabel(day),
        count: calls.filter((c) => (c.created_at || "").startsWith(day)).length,
    }));

    // ── Outcome distribution ─────────────────────────────────────────────────
    const outcomeMap: Record<string, number> = {};
    calls.forEach((c) => {
        const key = c.outcome || c.status || "unknown";
        outcomeMap[key] = (outcomeMap[key] || 0) + 1;
    });
    const OUTCOME_COLORS: Record<string, string> = {
        success: "#8b5cf6",
        not_interested: "#64748b",
        no_answer: "#f59e0b",
        completed: "#3b82f6",
        failed: "#ef4444",
        unknown: "#374151",
    };
    const outcomeSlices = Object.entries(outcomeMap).map(([label, value]) => ({
        label,
        value,
        color: OUTCOME_COLORS[label] || "#6b7280",
    }));

    // ── Top agents ───────────────────────────────────────────────────────────
    const agentMap: Record<string, AgentStat> = {};
    calls.forEach((c) => {
        if (!agentMap[c.agent_id]) {
            agentMap[c.agent_id] = {
                agent_id: c.agent_id,
                name: c.agent_name || c.agent_id.slice(0, 8) + "…",
                calls: 0,
                success: 0,
                avgDuration: 0,
            };
        }
        agentMap[c.agent_id].calls++;
        if (c.outcome === "success") agentMap[c.agent_id].success++;
        agentMap[c.agent_id].avgDuration += c.duration_seconds;
    });
    const topAgents = Object.values(agentMap)
        .map((a) => ({ ...a, avgDuration: a.calls > 0 ? Math.round(a.avgDuration / a.calls) : 0 }))
        .sort((a, b) => b.calls - a.calls)
        .slice(0, 5);

    // ── Summary stats ────────────────────────────────────────────────────────
    const total = calls.length;
    const successful = calls.filter((c) => c.outcome === "success").length;
    const successRate = total > 0 ? Math.round((successful / total) * 100) : 0;
    const avgDuration = total > 0 ? Math.round(calls.reduce((s, c) => s + c.duration_seconds, 0) / total) : 0;
    const todayCalls = callsPerDay[callsPerDay.length - 1]?.count || 0;

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-8 w-48 rounded-lg bg-white/5 animate-pulse" />
                <div className="grid grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => <div key={i} className="h-24 rounded-2xl bg-white/[0.02] animate-pulse" />)}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-white">Analytics</h1>
                <p className="text-sm text-slate-500 mt-1">Business intelligence across all your agents and calls.</p>
            </div>

            {/* KPI cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                    { label: "Total Calls", value: total, icon: "📞", sub: "all time" },
                    { label: "Today", value: todayCalls, icon: "📅", sub: "calls today" },
                    { label: "Success Rate", value: `${successRate}%`, icon: "✅", sub: `${successful} successful` },
                    { label: "Avg Duration", value: formatDuration(avgDuration), icon: "⏱️", sub: "per call" },
                ].map((kpi) => (
                    <div key={kpi.label} className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
                        <div className="text-2xl mb-2">{kpi.icon}</div>
                        <div className="text-3xl font-bold text-white">{kpi.value}</div>
                        <div className="text-xs text-slate-500 mt-1">{kpi.label}</div>
                        <div className="text-[10px] text-slate-600 mt-0.5">{kpi.sub}</div>
                    </div>
                ))}
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Calls per day */}
                <div className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
                    <h2 className="text-sm font-semibold text-white mb-4">Calls — Last 7 Days</h2>
                    {total === 0 ? (
                        <div className="flex items-center justify-center h-32 text-slate-600 text-sm">No call data yet</div>
                    ) : (
                        <BarChart data={callsPerDay} />
                    )}
                </div>

                {/* Outcome distribution */}
                <div className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
                    <h2 className="text-sm font-semibold text-white mb-4">Outcome Distribution</h2>
                    <DonutChart slices={outcomeSlices} />
                </div>
            </div>

            {/* Top agents table */}
            <div className="rounded-2xl bg-white/[0.03] border border-white/5 p-5">
                <h2 className="text-sm font-semibold text-white mb-4">Top Agents by Call Volume</h2>
                {topAgents.length === 0 ? (
                    <p className="text-sm text-slate-600 text-center py-8">No agent data yet.</p>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/5">
                                <th className="text-left pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Agent</th>
                                <th className="text-right pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Calls</th>
                                <th className="text-right pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Success</th>
                                <th className="text-right pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Avg Duration</th>
                                <th className="text-right pb-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Rate</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.03]">
                            {topAgents.map((a) => {
                                const rate = a.calls > 0 ? Math.round((a.success / a.calls) * 100) : 0;
                                return (
                                    <tr key={a.agent_id} className="hover:bg-white/[0.02] transition-colors">
                                        <td className="py-3 text-white font-medium">{a.name}</td>
                                        <td className="py-3 text-right text-slate-300 tabular-nums">{a.calls}</td>
                                        <td className="py-3 text-right text-emerald-400 tabular-nums">{a.success}</td>
                                        <td className="py-3 text-right text-slate-400 tabular-nums">{formatDuration(a.avgDuration)}</td>
                                        <td className="py-3 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full bg-violet-500"
                                                        style={{ width: `${rate}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs text-slate-400 tabular-nums w-8 text-right">{rate}%</span>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
