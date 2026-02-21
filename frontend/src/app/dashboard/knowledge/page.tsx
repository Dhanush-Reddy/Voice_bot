"use client";

/**
 * Knowledge Base Page — /dashboard/knowledge
 *
 * Sprint 5: Upload PDFs and text files to train agents on business-specific
 * documents. Documents are chunked, embedded via Gemini, and used for RAG
 * context injection during live calls.
 */

import { useEffect, useState, useCallback, useRef } from "react";

const BACKEND_URL = "/api/backend";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Agent {
    id: string;
    name: string;
}

interface KnowledgeDocument {
    id: string;
    agent_id: string;
    filename: string;
    content_type: string;
    chunk_count: number;
    size_bytes: number;
    created_at?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

function FileIcon({ type }: { type: string }) {
    const isPdf = type === "application/pdf" || type.includes("pdf");
    return (
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold ${isPdf ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"}`}>
            {isPdf ? "PDF" : "TXT"}
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function KnowledgePage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedAgentId, setSelectedAgentId] = useState<string>("");
    const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [uploadSuccess, setUploadSuccess] = useState("");
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Load agents
    useEffect(() => {
        fetch(`${BACKEND_URL}/agents`)
            .then((r) => r.json())
            .then((data) => {
                setAgents(data);
                if (data.length > 0) setSelectedAgentId(data[0].id);
            })
            .catch(() => { });
    }, []);

    // Load documents when agent changes
    const fetchDocuments = useCallback(async () => {
        if (!selectedAgentId) return;
        setLoading(true);
        try {
            const res = await fetch(`${BACKEND_URL}/agents/${selectedAgentId}/knowledge`);
            if (res.ok) setDocuments(await res.json());
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, [selectedAgentId]);

    useEffect(() => {
        fetchDocuments();
    }, [fetchDocuments]);

    const handleUpload = async (file: File) => {
        if (!selectedAgentId) return;
        setUploading(true);
        setUploadError("");
        setUploadSuccess("");

        const form = new FormData();
        form.append("file", file);

        try {
            const res = await fetch(`${BACKEND_URL}/agents/${selectedAgentId}/knowledge`, {
                method: "POST",
                body: form,
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Upload failed");
            }
            const doc: KnowledgeDocument = await res.json();
            setDocuments((prev) => [doc, ...prev]);
            setUploadSuccess(`✅ "${doc.filename}" uploaded — ${doc.chunk_count} chunks indexed`);
            setTimeout(() => setUploadSuccess(""), 5000);
        } catch (e: unknown) {
            setUploadError(e instanceof Error ? e.message : "Upload failed");
        } finally {
            setUploading(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleUpload(file);
        e.target.value = "";
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) handleUpload(file);
    };

    const handleDelete = async (docId: string) => {
        if (!confirm("Delete this document? This cannot be undone.")) return;
        setDeletingId(docId);
        try {
            await fetch(`${BACKEND_URL}/knowledge/${docId}`, { method: "DELETE" });
            setDocuments((prev) => prev.filter((d) => d.id !== docId));
        } catch {
            alert("Failed to delete document.");
        } finally {
            setDeletingId(null);
        }
    };

    const totalChunks = documents.reduce((s, d) => s + d.chunk_count, 0);
    const totalSize = documents.reduce((s, d) => s + d.size_bytes, 0);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Knowledge Base</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Upload documents to train your agents with business-specific knowledge.
                    </p>
                </div>
                {/* Agent selector */}
                <select
                    value={selectedAgentId}
                    onChange={(e) => setSelectedAgentId(e.target.value)}
                    className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-300 focus:outline-none focus:border-violet-500/50 transition-colors"
                >
                    {agents.length === 0 && <option value="">No agents</option>}
                    {agents.map((a) => (
                        <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                </select>
            </div>

            {/* Stats */}
            {documents.length > 0 && (
                <div className="grid grid-cols-3 gap-4">
                    {[
                        { label: "Documents", value: documents.length, icon: "📄" },
                        { label: "Total Chunks", value: totalChunks, icon: "🧩" },
                        { label: "Total Size", value: formatBytes(totalSize), icon: "💾" },
                    ].map((s) => (
                        <div key={s.label} className="rounded-2xl bg-white/[0.03] border border-white/5 p-4">
                            <div className="text-xl mb-1">{s.icon}</div>
                            <div className="text-2xl font-bold text-white">{s.value}</div>
                            <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Upload zone */}
            <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative rounded-2xl border-2 border-dashed p-10 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all ${dragOver
                        ? "border-violet-500 bg-violet-500/5"
                        : "border-white/10 hover:border-violet-500/50 hover:bg-white/[0.02]"
                    } ${uploading ? "pointer-events-none opacity-60" : ""}`}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.txt,.md"
                    className="hidden"
                    onChange={handleFileChange}
                />
                {uploading ? (
                    <>
                        <div className="w-10 h-10 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
                        <p className="text-sm text-slate-400">Uploading and indexing…</p>
                    </>
                ) : (
                    <>
                        <div className="w-14 h-14 rounded-2xl bg-violet-500/10 flex items-center justify-center">
                            <svg className="w-7 h-7 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                            </svg>
                        </div>
                        <div className="text-center">
                            <p className="text-sm font-medium text-white">Drop a file here or click to browse</p>
                            <p className="text-xs text-slate-500 mt-1">Supports PDF, TXT, and Markdown files</p>
                        </div>
                    </>
                )}
            </div>

            {/* Feedback */}
            {uploadError && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{uploadError}</div>
            )}
            {uploadSuccess && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">{uploadSuccess}</div>
            )}

            {/* Document list */}
            <div className="space-y-2">
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Indexed Documents</h2>
                {loading ? (
                    <div className="space-y-2">
                        {[1, 2].map((i) => (
                            <div key={i} className="h-16 rounded-xl bg-white/[0.02] border border-white/5 animate-pulse" />
                        ))}
                    </div>
                ) : documents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center rounded-2xl border border-white/5 bg-white/[0.01]">
                        <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center mb-3">
                            <svg className="w-6 h-6 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                            </svg>
                        </div>
                        <p className="text-sm text-slate-500">No documents yet. Upload one above to get started.</p>
                    </div>
                ) : (
                    <div className="rounded-2xl border border-white/5 overflow-hidden divide-y divide-white/[0.04]">
                        {documents.map((doc) => (
                            <div key={doc.id} className="flex items-center gap-4 px-5 py-4 hover:bg-white/[0.02] transition-colors group">
                                <FileIcon type={doc.content_type} />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-white truncate">{doc.filename}</p>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {doc.chunk_count} chunks · {formatBytes(doc.size_bytes)} · {formatDate(doc.created_at)}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={() => handleDelete(doc.id)}
                                        disabled={deletingId === doc.id}
                                        className="p-1.5 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-colors"
                                        aria-label="Delete document"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* RAG info callout */}
            <div className="rounded-2xl bg-violet-500/5 border border-violet-500/20 p-5">
                <h3 className="text-sm font-semibold text-violet-300 mb-2">🧠 How RAG Works</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                    When a user asks a question during a call, the agent searches your uploaded documents for relevant context
                    using semantic similarity (Gemini text-embedding-004). The top matching passages are injected into the
                    agent&apos;s context window before generating a response — giving it accurate, business-specific answers.
                </p>
            </div>
        </div>
    );
}
