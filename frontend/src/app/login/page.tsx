"use client";

export const dynamic = "force-dynamic";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
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
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { signIn, signUp, user } = useAuth();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
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

  const handleDemoAdmin = async () => {
    setEmail("admin@heshrec.com");
    setPassword("heshrec2026!");
    setMode("signin");
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
        <div className="p-8 rounded-2xl bg-[#141517] border border-[#232529] space-y-6 shadow-xl">
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

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
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
                disabled={loading}
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
