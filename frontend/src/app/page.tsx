"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
    const router = useRouter();

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const agentId = params.get("agent_id");
        if (agentId) {
            router.push(`/try?agent_id=${agentId}`);
        } else {
            router.push("/dashboard");
        }
    }, [router]);
    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950">
            <div className="flex flex-col items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary-500/20 flex items-center justify-center animate-pulse">
                    <div className="w-6 h-6 rounded-lg bg-primary-500" />
                </div>
                <p className="text-slate-400 text-sm animate-pulse">Loading dashboard...</p>
            </div>
        </div>
    );
}
