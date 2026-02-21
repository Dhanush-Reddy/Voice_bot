"use client";

/**
 * DashboardSidebar — the persistent left-hand navigation.
 *
 * Design: Glassmorphic dark sidebar with active state indicators.
 * Follows the Edesy/Vani pattern with grouped navigation sections.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";

interface NavItem {
    label: string;
    href: string;
    icon: React.ReactNode;
}

interface NavSection {
    title?: string;
    items: NavItem[];
}

const MicIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
    </svg>
);

const GridIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
    </svg>
);

const AgentsIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
    </svg>
);

const PhoneIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
    </svg>
);

const BookIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
    </svg>
);

const ChartIcon = () => (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
);

const NAV_SECTIONS: NavSection[] = [
    {
        items: [
            { label: "Dashboard", href: "/dashboard", icon: <GridIcon /> },
        ],
    },
    {
        title: "MANAGE",
        items: [
            { label: "Agents", href: "/dashboard/agents", icon: <AgentsIcon /> },
            { label: "Call History", href: "/dashboard/calls", icon: <PhoneIcon /> },
            { label: "Knowledge Base", href: "/dashboard/knowledge", icon: <BookIcon /> },
        ],
    },
    {
        title: "INSIGHTS",
        items: [
            { label: "Analytics", href: "/dashboard/analytics", icon: <ChartIcon /> },
        ],
    },
];

export function DashboardSidebar() {
    const pathname = usePathname();
    const { data: session } = useSession();

    const isActive = (href: string) => {
        if (href === "/dashboard") return pathname === "/dashboard";
        return pathname.startsWith(href);
    };

    return (
        <aside className="fixed left-0 top-0 h-full w-64 bg-[#0d0d14] border-r border-white/5 flex flex-col z-40">
            {/* Logo */}
            <div className="flex items-center gap-3 px-6 py-5 border-b border-white/5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center shadow-lg shadow-violet-500/25">
                    <MicIcon />
                </div>
                <div>
                    <span className="text-sm font-bold text-white tracking-wide">Voice AI</span>
                    <p className="text-[10px] text-slate-500 uppercase tracking-widest">Agency Platform</p>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
                {NAV_SECTIONS.map((section, sIdx) => (
                    <div key={sIdx}>
                        {section.title && (
                            <p className="px-3 mb-2 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
                                {section.title}
                            </p>
                        )}
                        <ul className="space-y-1">
                            {section.items.map((item) => (
                                <li key={item.href}>
                                    <Link
                                        href={item.href}
                                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                                            isActive(item.href)
                                                ? "bg-violet-500/15 text-violet-300 shadow-sm"
                                                : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                                        }`}
                                    >
                                        <span className={isActive(item.href) ? "text-violet-400" : "text-slate-500"}>
                                            {item.icon}
                                        </span>
                                        {item.label}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                ))}
            </nav>

            {/* Footer — link back to the voice widget and Sign Out */}
            <div className="px-3 py-4 border-t border-white/5 flex flex-col gap-2">
                <Link
                    href="/"
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all"
                >
                    <MicIcon />
                    Voice Widget
                </Link>

                {session?.user && (
                    <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between px-2">
                        <div className="flex items-center gap-2 overflow-hidden">
                            {session.user.image ? (
                                <img src={session.user.image} alt="Avatar" className="w-8 h-8 rounded-full bg-slate-800" />
                            ) : (
                                <div className="w-8 h-8 rounded-full bg-violet-600 flex items-center justify-center text-xs font-bold text-white">
                                    {session.user.name?.charAt(0) || "U"}
                                </div>
                            )}
                            <div className="flex flex-col truncate">
                                <span className="text-xs font-medium text-slate-200 truncate">{session.user.name}</span>
                                <span className="text-[10px] text-slate-500 truncate">{session.user.email}</span>
                            </div>
                        </div>
                        <button
                            onClick={() => signOut({ callbackUrl: '/' })}
                            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-all ml-2"
                            title="Sign Out"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
                            </svg>
                        </button>
                    </div>
                )}
            </div>
        </aside>
    );
}
