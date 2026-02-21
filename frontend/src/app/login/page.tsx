"use client";

import { signIn, useSession } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

type Tab = "signin" | "signup";

function LoginContent() {
    const { status } = useSession();
    const router = useRouter();
    const searchParams = useSearchParams();

    const [tab, setTab] = useState<Tab>("signin");

    // Surface NextAuth OAuth errors (e.g. OAuthAccountNotLinked)
    const oauthError = searchParams.get("error");
    const oauthErrorMsg = oauthError
        ? oauthError === "OAuthAccountNotLinked"
            ? "This email is already registered with a different sign-in method."
            : "Google sign-in failed. Please try again or use email/password."
        : null;

    // ── Sign-in state ────────────────────────────────────────────────────────
    const [signInEmail, setSignInEmail] = useState("");
    const [signInPassword, setSignInPassword] = useState("");
    const [signInError, setSignInError] = useState("");
    const [signInLoading, setSignInLoading] = useState(false);
    const [showSignInPassword, setShowSignInPassword] = useState(false);

    // ── Sign-up state ────────────────────────────────────────────────────────
    const [name, setName] = useState("");
    const [signUpEmail, setSignUpEmail] = useState("");
    const [signUpPassword, setSignUpPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [phone, setPhone] = useState("");
    const [company, setCompany] = useState("");
    const [signUpError, setSignUpError] = useState("");
    const [signUpLoading, setSignUpLoading] = useState(false);
    const [showSignUpPassword, setShowSignUpPassword] = useState(false);

    // ── OAuth loading ────────────────────────────────────────────────────────
    const [oauthLoading, setOauthLoading] = useState(false);

    // Redirect if already logged in
    useEffect(() => {
        if (status === "authenticated") router.push("/dashboard");
    }, [status, router]);

    if (status === "loading" || status === "authenticated") {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-950">
                <div className="w-8 h-8 rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
            </div>
        );
    }

    // ── Handlers ─────────────────────────────────────────────────────────────

    const handleGoogleSignIn = async () => {
        setOauthLoading(true);
        await signIn("google", { callbackUrl: "/dashboard" });
    };

    const handleSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        setSignInError("");
        if (!signInEmail || !signInPassword) {
            setSignInError("Please fill in all fields.");
            return;
        }
        setSignInLoading(true);
        const result = await signIn("credentials", {
            email: signInEmail,
            password: signInPassword,
            redirect: false,
        });
        setSignInLoading(false);
        if (result?.error) {
            setSignInError("Invalid email or password.");
        } else {
            router.push("/dashboard");
        }
    };

    const handleSignUp = async (e: React.FormEvent) => {
        e.preventDefault();
        setSignUpError("");

        if (!name || !signUpEmail || !signUpPassword || !confirmPassword) {
            setSignUpError("Please fill in all required fields.");
            return;
        }
        if (signUpPassword.length < 8) {
            setSignUpError("Password must be at least 8 characters.");
            return;
        }
        if (signUpPassword !== confirmPassword) {
            setSignUpError("Passwords do not match.");
            return;
        }

        setSignUpLoading(true);
        try {
            const res = await fetch("/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name,
                    email: signUpEmail,
                    password: signUpPassword,
                    phone,
                    company,
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                setSignUpError(data.error || "Registration failed.");
                setSignUpLoading(false);
                return;
            }

            // Auto sign-in after successful registration
            const result = await signIn("credentials", {
                email: signUpEmail,
                password: signUpPassword,
                redirect: false,
            });

            setSignUpLoading(false);
            if (result?.error) {
                setSignUpError("Account created but sign-in failed. Please sign in manually.");
                setTab("signin");
            } else {
                router.push("/dashboard");
            }
        } catch {
            setSignUpLoading(false);
            setSignUpError("Something went wrong. Please try again.");
        }
    };

    // ── Shared UI pieces ──────────────────────────────────────────────────────

    const EyeIcon = ({ show }: { show: boolean }) =>
        show ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
            </svg>
        ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
            </svg>
        );

    const inputCls =
        "w-full bg-slate-800/60 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all duration-200";

    const labelCls = "block text-xs font-medium text-slate-400 mb-1.5";

    const GoogleButton = () => (
        <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={oauthLoading}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white hover:bg-slate-100 text-slate-900 font-medium rounded-xl transition-all duration-200 hover:shadow-lg hover:shadow-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
        >
            {oauthLoading ? (
                <div className="w-5 h-5 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" />
            ) : (
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
            )}
            {oauthLoading ? "Signing in…" : "Continue with Google"}
        </button>
    );

    const Divider = () => (
        <div className="flex items-center gap-3 my-5">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs text-slate-500">or</span>
            <div className="h-px flex-1 bg-white/10" />
        </div>
    );

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-950 py-8">
            {/* Grid background */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
            {/* Glow */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[500px] bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 w-full max-w-md mx-4">
                <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">

                    {/* Logo */}
                    <div className="flex items-center justify-center mb-6">
                        <div className="w-12 h-12 rounded-2xl bg-primary-500/20 border border-primary-500/30 flex items-center justify-center">
                            <svg className="w-6 h-6 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                                    d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                            </svg>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex bg-slate-800/60 rounded-xl p-1 mb-6">
                        {(["signin", "signup"] as Tab[]).map((t) => (
                            <button
                                key={t}
                                onClick={() => setTab(t)}
                                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                                    tab === t
                                        ? "bg-primary-500 text-white shadow"
                                        : "text-slate-400 hover:text-white"
                                }`}
                            >
                                {t === "signin" ? "Sign In" : "Sign Up"}
                            </button>
                        ))}
                    </div>

                    {/* OAuth error banner (e.g. after Google sign-in failure) */}
                    {oauthErrorMsg && (
                        <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4 text-center">
                            {oauthErrorMsg}
                        </p>
                    )}

                    {/* ── SIGN IN ──────────────────────────────────────────────── */}
                    {tab === "signin" && (
                        <>
                            <GoogleButton />
                            <Divider />

                            <form onSubmit={handleSignIn} className="space-y-4" noValidate>
                                <div>
                                    <label className={labelCls} htmlFor="si-email">Email</label>
                                    <input
                                        id="si-email"
                                        type="email"
                                        autoComplete="email"
                                        placeholder="you@example.com"
                                        value={signInEmail}
                                        onChange={(e) => setSignInEmail(e.target.value)}
                                        className={inputCls}
                                    />
                                </div>

                                <div>
                                    <label className={labelCls} htmlFor="si-password">Password</label>
                                    <div className="relative">
                                        <input
                                            id="si-password"
                                            type={showSignInPassword ? "text" : "password"}
                                            autoComplete="current-password"
                                            placeholder="••••••••"
                                            value={signInPassword}
                                            onChange={(e) => setSignInPassword(e.target.value)}
                                            className={`${inputCls} pr-10`}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowSignInPassword((v) => !v)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                                        >
                                            <EyeIcon show={showSignInPassword} />
                                        </button>
                                    </div>
                                </div>

                                {signInError && (
                                    <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                        {signInError}
                                    </p>
                                )}

                                <button
                                    id="signin-btn"
                                    type="submit"
                                    disabled={signInLoading}
                                    className="w-full py-3 bg-primary-600 hover:bg-primary-500 text-white font-medium rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                                >
                                    {signInLoading ? (
                                        <div className="w-5 h-5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                                    ) : (
                                        "Sign In"
                                    )}
                                </button>
                            </form>
                        </>
                    )}

                    {/* ── SIGN UP ──────────────────────────────────────────────── */}
                    {tab === "signup" && (
                        <>
                            <GoogleButton />
                            <Divider />

                            <form onSubmit={handleSignUp} className="space-y-4" noValidate>
                                {/* Row: Name */}
                                <div>
                                    <label className={labelCls} htmlFor="su-name">
                                        Full Name <span className="text-red-400">*</span>
                                    </label>
                                    <input
                                        id="su-name"
                                        type="text"
                                        autoComplete="name"
                                        placeholder="Jane Smith"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        className={inputCls}
                                    />
                                </div>

                                {/* Row: Email */}
                                <div>
                                    <label className={labelCls} htmlFor="su-email">
                                        Email <span className="text-red-400">*</span>
                                    </label>
                                    <input
                                        id="su-email"
                                        type="email"
                                        autoComplete="email"
                                        placeholder="you@example.com"
                                        value={signUpEmail}
                                        onChange={(e) => setSignUpEmail(e.target.value)}
                                        className={inputCls}
                                    />
                                </div>

                                {/* Row: Password + Confirm */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className={labelCls} htmlFor="su-password">
                                            Password <span className="text-red-400">*</span>
                                        </label>
                                        <div className="relative">
                                            <input
                                                id="su-password"
                                                type={showSignUpPassword ? "text" : "password"}
                                                autoComplete="new-password"
                                                placeholder="Min 8 chars"
                                                value={signUpPassword}
                                                onChange={(e) => setSignUpPassword(e.target.value)}
                                                className={`${inputCls} pr-8`}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowSignUpPassword((v) => !v)}
                                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                                            >
                                                <EyeIcon show={showSignUpPassword} />
                                            </button>
                                        </div>
                                    </div>

                                    <div>
                                        <label className={labelCls} htmlFor="su-confirm">
                                            Confirm <span className="text-red-400">*</span>
                                        </label>
                                        <input
                                            id="su-confirm"
                                            type="password"
                                            autoComplete="new-password"
                                            placeholder="Repeat password"
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            className={inputCls}
                                        />
                                    </div>
                                </div>

                                {/* Row: Phone + Company (optional) */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className={labelCls} htmlFor="su-phone">Phone</label>
                                        <input
                                            id="su-phone"
                                            type="tel"
                                            autoComplete="tel"
                                            placeholder="+1 555 000 0000"
                                            value={phone}
                                            onChange={(e) => setPhone(e.target.value)}
                                            className={inputCls}
                                        />
                                    </div>
                                    <div>
                                        <label className={labelCls} htmlFor="su-company">Company</label>
                                        <input
                                            id="su-company"
                                            type="text"
                                            autoComplete="organization"
                                            placeholder="Acme Inc."
                                            value={company}
                                            onChange={(e) => setCompany(e.target.value)}
                                            className={inputCls}
                                        />
                                    </div>
                                </div>

                                {signUpError && (
                                    <p className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                        {signUpError}
                                    </p>
                                )}

                                <button
                                    id="signup-btn"
                                    type="submit"
                                    disabled={signUpLoading}
                                    className="w-full py-3 bg-primary-600 hover:bg-primary-500 text-white font-medium rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                                >
                                    {signUpLoading ? (
                                        <div className="w-5 h-5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                                    ) : (
                                        "Create Account"
                                    )}
                                </button>
                            </form>
                        </>
                    )}

                    {/* Footer */}
                    <p className="text-center text-slate-500 text-xs mt-6 leading-relaxed">
                        By continuing, you agree to our terms of service.<br />
                        Your data is securely stored in Google Cloud.
                    </p>
                </div>

                <p className="text-center text-slate-600 text-xs mt-6">
                    Powered by Gemini Live API · LiveKit
                </p>
            </div>
        </div>
    );
}

export default function LoginPage() {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-screen items-center justify-center bg-slate-950">
                    <div className="w-8 h-8 rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
                </div>
            }
        >
            <LoginContent />
        </Suspense>
    );
}
