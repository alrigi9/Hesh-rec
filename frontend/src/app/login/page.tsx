"use client";

export const dynamic = "force-dynamic";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  AudioWaveform, 
  ShieldCheck, 
  Lock, 
  Mail, 
  ArrowRight, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle,
  Loader2,
  Info
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabaseClient";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const infoMsg = searchParams.get("msg");
  const { signIn, signUp, user } = useAuth();

  const [mode, setMode] = useState<"signin" | "signup">(infoMsg ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // If already logged in, offer quick jump to dashboard
  if (user) {
    return (
      <div className="min-h-screen bg-[#0c0d0e] flex items-center justify-center p-6 text-[#f0f2f5]">
        <div className="max-w-md w-full p-8 rounded-2xl bg-[#141517] border border-[#232529] text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-[#3ec98a]/10 border border-[#3ec98a]/20 flex items-center justify-center text-[#3ec98a] mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-[#f0f2f5] font-heading">
            Already Signed In
          </h2>
          <p className="text-xs text-[#8b909a]">
            You are logged in as <span className="text-[#f0f2f5] font-mono">{user.email}</span>.
          </p>
          <Button
            onClick={() => router.push("/")}
            className="w-full h-10 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs font-medium"
          >
            Go to Studio Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const handleOAuthSignIn = async (provider: "google" | "github") => {
    try {
      setOauthLoading(provider);
      setErrorMsg(null);
      const redirectTo = typeof window !== "undefined" ? `${window.location.origin}/` : "https://recmap.tech/";
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo,
        },
      });
      if (error) {
        setErrorMsg(error.message);
        setOauthLoading(null);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to initiate single sign-on provider.");
      setOauthLoading(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMsg("Please enter both email and password.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      if (mode === "signin") {
        const { error } = await signIn(email, password);
        if (error) {
          setErrorMsg(error.message || "Failed to sign in. Please verify credentials.");
        } else {
          router.push("/");
        }
      } else {
        const { error, needsEmailConfirmation } = await signUp(email, password);
        if (error) {
          setErrorMsg(error.message || "Failed to create account.");
        } else if (needsEmailConfirmation) {
          setSuccessMsg("Account created! Please check your email inbox to verify your account.");
        } else {
          setSuccessMsg("Account created successfully! Redirecting...");
          setTimeout(() => router.push("/"), 1000);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Authentication error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0c0d0e] flex flex-col justify-center items-center px-6 py-12 text-[#f0f2f5]">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-md space-y-6"
      >
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <Link href="/" className="inline-flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] shadow-sm">
              <AudioWaveform className="w-5 h-5" />
            </div>
            <span className="text-xl font-bold tracking-tight text-[#f0f2f5] font-heading">
              Hesh Rec
            </span>
          </Link>
          <p className="text-xs text-[#8b909a]">
            SOC 2 Compliant Speech & Meeting Intelligence Platform
          </p>
        </div>

        {/* Auth Card */}
        <div className="p-8 rounded-2xl bg-[#141517] border border-[#232529] space-y-5 shadow-xl">
          {/* Info Banner when redirected from Upload */}
          {infoMsg && (
            <div className="p-3 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/30 flex items-start gap-2.5 text-xs text-[#f0f2f5] shadow-sm">
              <Sparkles className="w-4 h-4 text-[#ff5c47] shrink-0 mt-0.5" />
              <span>{infoMsg}</span>
            </div>
          )}

          {/* Mode Switcher Tabs */}
          <div className="grid grid-cols-2 p-1 rounded-full bg-[#18191c] border border-[#232529] text-xs">
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setErrorMsg(null);
              }}
              className={`py-1.5 rounded-full font-medium transition-all ${
                mode === "signin"
                  ? "bg-[#ff5c47] text-white shadow-sm"
                  : "text-[#8b909a] hover:text-[#f0f2f5]"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setErrorMsg(null);
              }}
              className={`py-1.5 rounded-full font-medium transition-all ${
                mode === "signup"
                  ? "bg-[#ff5c47] text-white shadow-sm"
                  : "text-[#8b909a] hover:text-[#f0f2f5]"
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error Alert */}
          {errorMsg && (
            <div className="p-3 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-start gap-2.5 text-xs text-[#ff5c47]">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Success Alert */}
          {successMsg && (
            <div className="p-3 rounded-xl bg-[#3ec98a]/10 border border-[#3ec98a]/20 flex items-start gap-2.5 text-xs text-[#3ec98a]">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Single Sign-On (OAuth) Buttons */}
          <div className="space-y-2.5">
            <button
              type="button"
              disabled={Boolean(oauthLoading) || loading}
              onClick={() => handleOAuthSignIn("google")}
              className="w-full h-10 px-4 rounded-xl bg-[#18191c] hover:bg-[#202227] border border-[#232529] hover:border-[#2e3238] text-xs font-medium text-[#f0f2f5] flex items-center justify-center gap-2.5 transition-all shadow-sm disabled:opacity-50"
            >
              {oauthLoading === "google" ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#ff5c47]" />
              ) : (
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
              )}
              <span>Continue with Google</span>
            </button>

            <button
              type="button"
              disabled={Boolean(oauthLoading) || loading}
              onClick={() => handleOAuthSignIn("github")}
              className="w-full h-10 px-4 rounded-xl bg-[#18191c] hover:bg-[#202227] border border-[#232529] hover:border-[#2e3238] text-xs font-medium text-[#f0f2f5] flex items-center justify-center gap-2.5 transition-all shadow-sm disabled:opacity-50"
            >
              {oauthLoading === "github" ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#ff5c47]" />
              ) : (
                <svg className="w-4 h-4 shrink-0 fill-current text-[#f0f2f5]" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
              )}
              <span>Continue with GitHub</span>
            </button>
          </div>

          {/* Divider */}
          <div className="relative flex items-center justify-center my-4">
            <div className="border-t border-[#232529] w-full" />
            <span className="bg-[#141517] px-3 text-[10px] uppercase font-semibold text-[#8b909a] tracking-wider absolute">
              Or continue with email
            </span>
          </div>

          {/* Email / Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4 pt-1">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#8b909a] uppercase tracking-wider">
                Work Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#8b909a] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full h-10 pl-10 pr-4 bg-[#18191c] border border-[#232529] rounded-xl text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors shadow-inner"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#8b909a] uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#8b909a] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full h-10 pl-10 pr-4 bg-[#18191c] border border-[#232529] rounded-xl text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors shadow-inner"
                />
              </div>
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                disabled={loading || Boolean(oauthLoading)}
                className="w-full h-10 rounded-full bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-lg shadow-[#ff5c47]/20 flex items-center justify-center gap-2 transition-all"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                <span>{mode === "signin" ? "Sign In to Studio" : "Start 300 Mins Free"}</span>
                {!loading && <ArrowRight className="w-3.5 h-3.5" />}
              </Button>
            </div>
          </form>

          {/* Quota Banner */}
          <div className="p-3.5 rounded-xl bg-[#18191c] border border-[#232529] flex items-center justify-between text-xs text-[#8b909a]">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#ff5c47]" />
              <span>Includes 300 free audio minutes/month</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-[#3ec98a]">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>SOC 2</span>
            </div>
          </div>
        </div>

        {/* Back Link */}
        <div className="text-center">
          <Link
            href="/"
            className="text-xs text-[#8b909a] hover:text-[#f0f2f5] transition-colors"
          >
            ← Back to Public Dashboard
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0c0d0e] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-[#ff5c47] animate-spin" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
