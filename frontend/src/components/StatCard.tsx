"use client";

import Link from "next/link";
import React from "react";

interface StatCardProps {
    label: string;
    value: string | number;
    sub?: string;
    icon: React.ReactNode;
    color: string;
    href?: string;
}

export function StatCard({
    label,
    value,
    sub,
    icon,
    color,
    href,
}: StatCardProps) {
    const content = (
        <div className={`rounded-2xl border border-white/5 bg-white/[0.03] p-5 flex items-center gap-4 transition-all ${href ? "hover:bg-white/[0.06] hover:border-white/10 cursor-pointer" : ""}`}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
                {icon}
            </div>
            <div className="min-w-0">
                <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
                <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
                {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
            </div>
        </div>
    );
    return href ? <Link href={href}>{content}</Link> : content;
}
