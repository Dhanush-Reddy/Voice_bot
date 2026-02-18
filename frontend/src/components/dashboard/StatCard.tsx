"use client";

/**
 * Reusable StatCard component for the dashboard overview.
 * Displays a metric with a label, value, and optional trend indicator.
 */

interface StatCardProps {
    label: string;
    value: string | number;
    icon: React.ReactNode;
    trend?: string;
    trendUp?: boolean;
    accentColor?: string;
}

export function StatCard({
    label,
    value,
    icon,
    trend,
    trendUp,
    accentColor = "violet",
}: StatCardProps) {
    const accentMap: Record<string, string> = {
        violet: "from-violet-500/20 to-violet-600/5 border-violet-500/20 text-violet-400",
        blue: "from-blue-500/20 to-blue-600/5 border-blue-500/20 text-blue-400",
        green: "from-emerald-500/20 to-emerald-600/5 border-emerald-500/20 text-emerald-400",
        orange: "from-orange-500/20 to-orange-600/5 border-orange-500/20 text-orange-400",
    };

    const accent = accentMap[accentColor] || accentMap.violet;

    return (
        <div className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-6 ${accent}`}>
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">
                        {label}
                    </p>
                    <p className="text-3xl font-bold text-white">{value}</p>
                    {trend && (
                        <p className={`mt-1 text-xs ${trendUp ? "text-emerald-400" : "text-red-400"}`}>
                            {trendUp ? "↑" : "↓"} {trend}
                        </p>
                    )}
                </div>
                <div className="opacity-80">{icon}</div>
            </div>
        </div>
    );
}
