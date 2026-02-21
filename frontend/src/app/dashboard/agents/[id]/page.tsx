"use client";

/**
 * Agent Editor Page — /dashboard/agents/[id]  (Sprint 2 — Advanced Builder)
 *
 * Tabs:
 *   Overview  — Name, System Instructions with variable-injection toolbar
 *   Voice & AI — Voice picker, Model, Language, Temperature, Cost Estimator
 *   Behavior   — Success outcomes, handoff number, first-message config
 *
 * Templates — one-click pre-fill for common use-cases (Real Estate, Sales, Support)
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";

const BACKEND_URL = "/api/backend";

// ─── Constants ────────────────────────────────────────────────────────────────

const VARIABLES = [
    { token: "{{user_name}}", label: "User Name" },
    { token: "{{business_name}}", label: "Business Name" },
    { token: "{{phone_number}}", label: "Phone Number" },
    { token: "{{date}}", label: "Today's Date" },
    { token: "{{time}}", label: "Current Time" },
];

const TEMPLATES = [
    {
        id: "real_estate",
        label: "🏠 Real Estate",
        name: "Real Estate Agent",
        voice_id: "Kore",
        language: "en-US",
        system_prompt:
            "You are a professional real estate assistant for {{business_name}}. " +
            "Your goal is to qualify leads by asking about their budget, preferred location, " +
            "and timeline. Keep responses concise — this is a voice call. " +
            "If the lead is interested, offer to book a site visit.",
    },
    {
        id: "sales",
        label: "💼 Sales",
        name: "Sales Assistant",
        voice_id: "Fenrir",
        language: "en-US",
        system_prompt:
            "You are an enthusiastic sales representative for {{business_name}}. " +
            "Introduce yourself as an AI assistant. Ask open-ended questions to understand " +
            "the prospect's pain points. Highlight key product benefits and handle objections " +
            "confidently. End by offering a free demo or consultation.",
    },
    {
        id: "support",
        label: "🎧 Support",
        name: "Customer Support",
        voice_id: "Leda",
        language: "en-US",
        system_prompt:
            "You are a friendly customer support agent for {{business_name}}. " +
            "Listen carefully to the customer's issue, empathize, and provide clear solutions. " +
            "If you cannot resolve the issue, offer to escalate to a human agent. " +
            "Always confirm the customer is satisfied before ending the call.",
    },
    {
        id: "hindi_sales",
        label: "🇮🇳 Hindi Sales",
        name: "Hindi Sales Agent",
        voice_id: "Aoede",
        language: "hi-IN",
        system_prompt:
            "Aap {{business_name}} ke liye ek professional sales representative hain. " +
            "Apna parichay dein aur prospect ki zarooratein samjhein. " +
            "Hamare product ke fayde batayein aur demo book karne ki offer karein.",
    },
];

const OUTCOME_PRESETS = [
    "Appointment Booked",
    "Interested — Follow Up",
    "Not Interested",
    "Wrong Number",
    "Voicemail Left",
    "Call Back Requested",
];

// ─── Types ────────────────────────────────────────────────────────────────────

type Tab = "overview" | "voice" | "behavior";

interface VoiceOption {
    id: string;
    description: string;
    sample_url?: string;
}

interface ModelOption {
    id: string;
    label: string;
    cost: number;
}

interface LanguageOption {
    id: string;
    label: string;
}

interface AgentForm {
    name: string;
    system_prompt: string;
    voice_id: string;
    model: string;
    language: string;
    is_active: boolean;
    temperature: number;
    success_outcomes: string[];
    handoff_number: string;
    first_message: string;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function AgentEditorPage() {
    const params = useParams();
    const router = useRouter();
    const agentId = params?.id as string;
    const isNew = agentId === "new";

    const [activeTab, setActiveTab] = useState<Tab>("overview");
    const [form, setForm] = useState<AgentForm>({
        name: "",
        system_prompt: "",
        voice_id: "Aoede",
        model: "gemini-2.0-flash-live-001",
        language: "en-US",
        is_active: true,
        temperature: 0.7,
        success_outcomes: ["Appointment Booked"],
        handoff_number: "",
        first_message: "",
    });
    const [loading, setLoading] = useState(!isNew);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [showTemplates, setShowTemplates] = useState(isNew);
    const [promptRef, setPromptRef] = useState<HTMLTextAreaElement | null>(null);
    const [outcomeInput, setOutcomeInput] = useState("");

    const [voices, setVoices] = useState<VoiceOption[]>([]);
    const [models, setModels] = useState<ModelOption[]>([]);
    const [languages, setLanguages] = useState<LanguageOption[]>([]);
    const [playingId, setPlayingId] = useState<string | null>(null);
    const [audio, setAudio] = useState<HTMLAudioElement | null>(null);

    // ── Fetch Options ─────────────────────────────────────────────────────────
    useEffect(() => {
        const fetchOptions = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/config/options`);
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                const data = await res.json();
                setVoices(data.voices);
                setModels(data.models);
                setLanguages(data.languages);
            } catch (err) {
                console.error("Failed to load configuration options from:", `${BACKEND_URL}/api/config/options`, err);
                setError("Failed to load configuration options (Voices, AI Model, etc.). Please check your backend connection.");
            }
        };
        fetchOptions();
    }, []);

    // ── Voice Preview ─────────────────────────────────────────────────────────
    const playSample = (id: string, url?: string) => {
        if (!url) return;

        if (playingId === id) {
            audio?.pause();
            setPlayingId(null);
            return;
        }

        if (audio) {
            audio.pause();
        }

        const newAudio = new Audio(url);
        newAudio.play().catch(e => {
            console.error("Playback failed:", e);
            setPlayingId(null);
        });

        setAudio(newAudio);
        setPlayingId(id);

        newAudio.onerror = (e) => {
            console.error("Audio error:", e);
            setPlayingId(null);
        };

        newAudio.onended = () => {
            setPlayingId(null);
        };
    };

    // ── Fetch existing agent ──────────────────────────────────────────────────
    useEffect(() => {
        if (isNew) return;
        const fetchAgent = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/agents/${agentId}`);
                if (!res.ok) throw new Error("Agent not found");
                const data = await res.json();
                setForm({
                    name: data.name,
                    system_prompt: data.system_prompt,
                    voice_id: data.voice_id,
                    model: data.model,
                    language: data.language,
                    is_active: data.is_active,
                    temperature: data.temperature ?? 0.7,
                    success_outcomes: data.success_outcomes ?? ["Appointment Booked"],
                    handoff_number: data.handoff_number ?? "",
                    first_message: data.first_message ?? "",
                });
            } catch {
                setError("Could not load agent.");
            } finally {
                setLoading(false);
            }
        };
        fetchAgent();
    }, [agentId, isNew]);

    // ── Variable injection ────────────────────────────────────────────────────
    const injectVariable = useCallback((token: string) => {
        if (!promptRef) return;
        const start = promptRef.selectionStart ?? form.system_prompt.length;
        const end = promptRef.selectionEnd ?? start;
        const next =
            form.system_prompt.slice(0, start) +
            token +
            form.system_prompt.slice(end);
        setForm((f) => ({ ...f, system_prompt: next }));
        // Restore cursor after token
        setTimeout(() => {
            promptRef.focus();
            promptRef.setSelectionRange(start + token.length, start + token.length);
        }, 0);
    }, [promptRef, form.system_prompt]);

    // ── Apply template ────────────────────────────────────────────────────────
    const applyTemplate = (t: typeof TEMPLATES[0]) => {
        setForm((f) => ({
            ...f,
            name: t.name,
            system_prompt: t.system_prompt,
            voice_id: t.voice_id,
            language: t.language,
        }));
        setShowTemplates(false);
    };

    // ── Outcome tag helpers ───────────────────────────────────────────────────
    const addOutcome = (label: string) => {
        if (!label.trim() || form.success_outcomes.includes(label)) return;
        setForm((f) => ({ ...f, success_outcomes: [...f.success_outcomes, label] }));
        setOutcomeInput("");
    };
    const removeOutcome = (label: string) =>
        setForm((f) => ({ ...f, success_outcomes: f.success_outcomes.filter((o) => o !== label) }));

    // ── Save ──────────────────────────────────────────────────────────────────
    const handleSave = async () => {
        setSaving(true);
        setError("");
        try {
            const url = isNew ? `${BACKEND_URL}/agents` : `${BACKEND_URL}/agents/${agentId}`;
            const method = isNew ? "POST" : "PATCH";
            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(form),
            });
            if (!res.ok) throw new Error("Save failed");
            router.push("/dashboard/agents");
        } catch {
            setError("Failed to save agent. Please try again.");
        } finally {
            setSaving(false);
        }
    };

    // ── Cost estimator ────────────────────────────────────────────────────────
    const selectedModel = models.find((m) => m.id === form.model) ?? models[0] ?? { cost: 0, label: "Unknown" };
    const costPerMin = selectedModel.cost;

    // ── Tabs config ───────────────────────────────────────────────────────────
    const TABS: { id: Tab; label: string }[] = [
        { id: "overview", label: "Overview" },
        { id: "voice", label: "Voice & AI" },
        { id: "behavior", label: "Behavior" },
    ];

    // ── Loading skeleton ──────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="space-y-4 max-w-2xl">
                <div className="h-8 w-48 rounded-lg bg-white/5 animate-pulse" />
                <div className="h-64 rounded-2xl bg-white/[0.02] border border-white/5 animate-pulse" />
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────────────
    return (
        <div className="max-w-2xl space-y-6">

            {/* ── Header ── */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => router.back()}
                    className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all"
                >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
                    </svg>
                </button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold text-white">
                        {isNew ? "New Agent" : form.name || "Edit Agent"}
                    </h1>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {isNew ? "Configure your new AI voice agent." : `ID: ${agentId}`}
                    </p>
                </div>
                {/* Active toggle in header */}
                <button
                    onClick={() => setForm({ ...form, is_active: !form.is_active })}
                    className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${form.is_active ? "bg-violet-600" : "bg-white/10"}`}
                    title={form.is_active ? "Active" : "Inactive"}
                >
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${form.is_active ? "translate-x-5" : "translate-x-0"}`} />
                </button>
            </div>

            {/* ── Template Picker (new agents only) ── */}
            {showTemplates && (
                <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-5 space-y-3">
                    <div className="flex items-center justify-between">
                        <p className="text-sm font-semibold text-violet-300">⚡ Start from a Template</p>
                        <button
                            onClick={() => setShowTemplates(false)}
                            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
                        >
                            Skip
                        </button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        {TEMPLATES.map((t) => (
                            <button
                                key={t.id}
                                onClick={() => applyTemplate(t)}
                                className="text-left px-4 py-3 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/40 hover:bg-violet-500/10 transition-all"
                            >
                                <p className="text-sm font-medium text-white">{t.label}</p>
                                <p className="text-xs text-slate-500 mt-0.5">{t.name}</p>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Tabs ── */}
            <div className="flex gap-1 p-1 rounded-xl bg-white/[0.03] border border-white/5 w-fit">
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                                ? "bg-violet-600 text-white shadow-sm"
                                : "text-slate-400 hover:text-slate-200"
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ── Tab Content ── */}
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-6 space-y-6">

                {/* ── OVERVIEW TAB ── */}
                {activeTab === "overview" && (
                    <>
                        {/* Agent Name */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                Agent Name
                            </label>
                            <input
                                type="text"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                placeholder="e.g. Sales Assistant"
                                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                            />
                        </div>

                        {/* First Message */}
                        <div className="space-y-2">
                            <label
                                htmlFor="opening-message"
                                className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
                            >
                                Opening Message
                            </label>
                            <p className="text-xs text-slate-600">
                                What the agent says first when a call connects. Leave blank to let the AI decide.
                            </p>
                            <input
                                id="opening-message"
                                type="text"
                                value={form.first_message}
                                onChange={(e) => setForm({ ...form, first_message: e.target.value })}
                                placeholder={`e.g. "Hello! I'm calling from Acme Corp. Is this {{user_name}}?"`}
                                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                            />
                        </div>

                        {/* System Instructions */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                    System Instructions
                                </label>
                                <span className="text-xs text-slate-600">
                                    {form.system_prompt.length} chars
                                </span>
                            </div>

                            {/* Variable Injection Toolbar */}
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[10px] text-slate-600 uppercase tracking-wider mr-1">Insert:</span>
                                {VARIABLES.map((v) => (
                                    <button
                                        key={v.token}
                                        onClick={() => injectVariable(v.token)}
                                        className="text-[10px] px-2 py-1 rounded-md bg-violet-500/10 text-violet-400 hover:bg-violet-500/20 border border-violet-500/20 font-mono transition-colors"
                                    >
                                        {v.token}
                                    </button>
                                ))}
                            </div>

                            <textarea
                                ref={(el) => setPromptRef(el)}
                                value={form.system_prompt}
                                onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                                rows={12}
                                placeholder="You are a helpful sales assistant for {{business_name}}. Your goal is to qualify leads and book demo calls..."
                                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm font-mono leading-relaxed focus:outline-none focus:border-violet-500/50 transition-colors resize-none"
                            />
                        </div>
                    </>
                )}

                {/* ── VOICE & AI TAB ── */}
                {activeTab === "voice" && (
                    <>
                        {/* Voice Picker */}
                        <div className="space-y-3">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                Voice
                            </label>
                            <div className="grid grid-cols-2 gap-2">
                                {voices.map((v) => (
                                    <div
                                        key={v.id}
                                        className={`relative group flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all border ${form.voice_id === v.id
                                                ? "bg-violet-600/20 border-violet-500/50 text-white"
                                                : "bg-white/[0.02] border-white/5 text-slate-400 hover:border-white/15 hover:text-slate-200"
                                            }`}
                                    >
                                        <button
                                            onClick={() => setForm({ ...form, voice_id: v.id })}
                                            className="flex-1 flex items-center gap-3"
                                        >
                                            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${form.voice_id === v.id ? "bg-violet-400" : "bg-slate-600"}`} />
                                            <div>
                                                <p className="text-sm font-medium">{v.id}</p>
                                                <p className="text-[10px] text-slate-500">{v.description}</p>
                                            </div>
                                        </button>

                                        {v.sample_url && (
                                            <button
                                                onClick={() => playSample(v.id, v.sample_url)}
                                                className={`p-1.5 rounded-lg transition-all ${playingId === v.id
                                                        ? "bg-violet-500 text-white"
                                                        : "bg-white/5 text-slate-500 hover:text-white hover:bg-white/10"
                                                    }`}
                                                title="Play Sample"
                                            >
                                                {playingId === v.id ? (
                                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                                        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                                                    </svg>
                                                ) : (
                                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                                        <path d="M8 5v14l11-7z" />
                                                    </svg>
                                                )}
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Model */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                AI Model
                            </label>
                            <div className="space-y-2">
                                {models.map((m) => (
                                    <button
                                        key={m.id}
                                        onClick={() => setForm({ ...form, model: m.id })}
                                        className={`w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all ${form.model === m.id
                                                ? "bg-violet-600/20 border-violet-500/50"
                                                : "bg-white/[0.02] border-white/5 hover:border-white/15"
                                            }`}
                                    >
                                        <span className={`text-sm font-medium ${form.model === m.id ? "text-white" : "text-slate-400"}`}>
                                            {m.label}
                                        </span>
                                        <span className="text-xs text-slate-500 font-mono">
                                            ₹{m.cost}/min
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Temperature */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                    Creativity (Temperature)
                                </label>
                                <span className="text-sm font-mono text-violet-400">{form.temperature.toFixed(1)}</span>
                            </div>
                            <input
                                type="range"
                                min={0}
                                max={1}
                                step={0.1}
                                value={form.temperature}
                                onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                                className="w-full accent-violet-500"
                            />
                            <div className="flex justify-between text-[10px] text-slate-600">
                                <span>Precise & Consistent</span>
                                <span>Creative & Varied</span>
                            </div>
                        </div>

                        {/* Language */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                Primary Language
                            </label>
                            <div className="grid grid-cols-2 gap-2">
                                {languages.map((l) => (
                                    <button
                                        key={l.id}
                                        onClick={() => setForm({ ...form, language: l.id })}
                                        className={`px-4 py-2.5 rounded-xl text-sm text-left transition-all border ${form.language === l.id
                                                ? "bg-violet-600/20 border-violet-500/50 text-white"
                                                : "bg-white/[0.02] border-white/5 text-slate-400 hover:border-white/15"
                                            }`}
                                    >
                                        {l.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Cost Estimator */}
                        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 space-y-2">
                            <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                                💰 Cost Estimator
                            </p>
                            <div className="grid grid-cols-3 gap-3 text-center">
                                {[100, 500, 1000].map((mins) => (
                                    <div key={mins} className="rounded-lg bg-white/5 p-3">
                                        <p className="text-lg font-bold text-white">
                                            ₹{(mins * costPerMin).toFixed(0)}
                                        </p>
                                        <p className="text-[10px] text-slate-500">{mins} mins</p>
                                    </div>
                                ))}
                            </div>
                            <p className="text-[10px] text-slate-600 text-center">
                                Estimated cost at ₹{costPerMin}/min with {selectedModel.label}
                            </p>
                        </div>
                    </>
                )}

                {/* ── BEHAVIOR TAB ── */}
                {activeTab === "behavior" && (
                    <>
                        {/* Success Outcomes */}
                        <div className="space-y-3">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                Success Outcome Tags
                            </label>
                            <p className="text-xs text-slate-600">
                                Define what counts as a successful call. These tags will be used for analytics.
                            </p>

                            {/* Current tags */}
                            <div className="flex flex-wrap gap-2">
                                {form.success_outcomes.map((o) => (
                                    <span
                                        key={o}
                                        className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                                    >
                                        {o}
                                        <button
                                            onClick={() => removeOutcome(o)}
                                            className="text-emerald-600 hover:text-emerald-300 transition-colors"
                                        >
                                            ×
                                        </button>
                                    </span>
                                ))}
                            </div>

                            {/* Preset chips */}
                            <div className="flex flex-wrap gap-1.5">
                                {OUTCOME_PRESETS.filter((p) => !form.success_outcomes.includes(p)).map((p) => (
                                    <button
                                        key={p}
                                        onClick={() => addOutcome(p)}
                                        className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-400 hover:border-emerald-500/30 hover:text-emerald-400 transition-all"
                                    >
                                        + {p}
                                    </button>
                                ))}
                            </div>

                            {/* Custom input */}
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={outcomeInput}
                                    onChange={(e) => setOutcomeInput(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && addOutcome(outcomeInput)}
                                    placeholder="Custom outcome… (press Enter)"
                                    className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                                />
                                <button
                                    onClick={() => addOutcome(outcomeInput)}
                                    className="px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:border-white/20 text-sm transition-all"
                                >
                                    Add
                                </button>
                            </div>
                        </div>

                        {/* Handoff Number */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                                Human Handoff Number
                            </label>
                            <p className="text-xs text-slate-600">
                                If the caller asks to speak to a human, transfer to this number.
                            </p>
                            <input
                                type="tel"
                                value={form.handoff_number}
                                onChange={(e) => setForm({ ...form, handoff_number: e.target.value })}
                                placeholder="+91 98765 43210"
                                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-600 text-sm focus:outline-none focus:border-violet-500/50 transition-colors"
                            />
                        </div>

                        {/* Active Toggle */}
                        <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/5">
                            <div>
                                <p className="text-sm font-medium text-white">Agent Active</p>
                                <p className="text-xs text-slate-500">Inactive agents cannot receive calls.</p>
                            </div>
                            <button
                                onClick={() => setForm({ ...form, is_active: !form.is_active })}
                                className={`relative w-11 h-6 rounded-full transition-colors ${form.is_active ? "bg-violet-600" : "bg-white/10"}`}
                            >
                                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${form.is_active ? "translate-x-5" : "translate-x-0"}`} />
                            </button>
                        </div>
                    </>
                )}
            </div>

            {/* ── Error ── */}
            {error && (
                <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                    {error}
                </p>
            )}

            {/* ── Footer Actions ── */}
            <div className="flex items-center justify-between">
                {!showTemplates && isNew && (
                    <button
                        onClick={() => setShowTemplates(true)}
                        className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
                    >
                        ← Use a template
                    </button>
                )}
                <div className="ml-auto">
                    <button
                        onClick={handleSave}
                        disabled={saving || !form.name || !form.system_prompt}
                        className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-semibold text-white transition-colors"
                    >
                        {saving ? "Saving…" : isNew ? "Create Agent" : "Save Changes"}
                    </button>
                </div>
            </div>
        </div>
    );
}
