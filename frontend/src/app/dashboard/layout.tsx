/**
 * Dashboard layout — wraps all /dashboard/* pages with the sidebar.
 * This is a Next.js App Router layout component.
 */

import type { Metadata } from "next";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";

export const metadata: Metadata = {
    title: "Agency Dashboard | Voice AI",
    description: "Manage your AI voice agents, view call history, and analytics.",
};

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen bg-[#0a0a0f]">
            <DashboardSidebar />
            <main className="flex-1 ml-64 p-8 overflow-y-auto">
                {children}
            </main>
        </div>
    );
}
