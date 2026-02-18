/**
 * Layout for /dashboard/agents/[id]
 *
 * This is a SERVER component (no "use client") so it can export
 * generateStaticParams() — required by Next.js output: export mode.
 *
 * Returning [] means no pages are pre-rendered at build time.
 * Client-side SPA routing handles navigation via the
 * /* → /index.html redirect in netlify.toml.
 */

export function generateStaticParams() {
    return [];
}

export default function AgentEditorLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <>{children}</>;
}
