"use client";

export const dynamic = "force-dynamic";

import React, { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Script from "next/script";
import { motion } from "framer-motion";
import { 
  AudioWaveform, 
  ShieldCheck, 
  Lock, 
  Mail, 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  Monitor 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabaseClient";

declare global {
  interface Window {
    google?: any;
  }
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const infoMsg = searchParams.get("msg");
  const { signIn, signUp, signInWithGoogleIdToken, user } = useAuth();

  const [mode, setMode] = useState<"signin" | "signup">(infoMsg ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

  // Initialize Google Identity Services (GIS)
  const setupGoogleIdentity = () => {
    if (typeof window !== "undefined" && window.google?.accounts?.id && googleClientId) {
      try {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          ux_mode: "popup",
          context: "signin",
          auto_select: false,
          cancel_on_tap_outside: true,
          callback: async (response: { credential: string }) => {
            if (response?.credential) {
              setOauthLoading("google");
              setErrorMsg(null);
              try {
                const { error } = await signInWithGoogleIdToken(response.credential);
                if (error) {
                  setErrorMsg(error.message || "Google authentication failed.");
                  setOauthLoading(null);
                } else {
                  router.push("/");
                }
              } catch (err: any) {
                setErrorMsg(err.message || "Failed to authenticate with Google ID token.");
                setOauthLoading(null);
              }
            }
          },
        });

        const hiddenContainer = document.getElementById("google-hidden-btn-container");
        if (hiddenContainer) {
          hiddenContainer.innerHTML = "";
          window.google.accounts.id.renderButton(hiddenContainer, {
            type: "standard",
            theme: "outline",
            size: "large",
            text: "signin_with",
            shape: "rectangular",
          });
        }
      } catch (err) {
        console.warn("Google Identity Services note:", err);
      }
    }
  };

  useEffect(() => {
    setupGoogleIdentity();
  }, [googleClientId]);

  if (user) {
    return (
      <div className="min-h-screen bg-[#0d0e11] flex items-center justify-center p-6 text-[#f3f4f6]">
        <div className="max-w-md w-full p-6 rounded-xl bg-[#131418] border border-[#22242a] text-center space-y-4 shadow-lg">
          <div className="w-10 h-10 rounded-lg bg-[#10b981]/10 border border-[#10b981]/20 flex items-center justify-center text-[#10b981] mx-auto">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <h2 className="text-base font-semibold text-[#f3f4f6]">
            Already Signed In
          </h2>
          <p className="text-xs text-[#9ca3af]">
            You are currently logged in as <span className="text-[#f3f4f6] font-mono">{user.email}</span>.
          </p>
          <Button
            onClick={() => router.push("/")}
            className="w-full h-8 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white text-xs font-medium"
          >
            Open Workspace
          </Button>
        </div>
      </div>
    );
  }

  const handleGoogleSignIn = async () => {
    setErrorMsg(null);
    setOauthLoading("google");

    if (googleClientId && typeof window !== "undefined" && window.google?.accounts?.id) {
      try {
        const hiddenContainer = document.getElementById("google-hidden-btn-container");
        const btn = hiddenContainer?.querySelector('div[role="button"]') as HTMLElement | null;
        if (btn) {
          btn.click();
          setTimeout(() => setOauthLoading(null), 3000);
          return;
        }

        window.google.accounts.id.prompt((notification: any) => {
          if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
            handleOAuthSignIn("google");
          }
        });
      } catch (err) {
        console.warn("Google prompt error:", err);
        handleOAuthSignIn("google");
      }
    } else {
      handleOAuthSignIn("google");
    }
  };

  const handleOAuthSignIn = async (provider: "google" | "github") => {
    try {
      setOauthLoading(provider);
      setErrorMsg(null);
      const redirectTo = typeof window !== "undefined" ? `${window.location.origin}/` : "https://recmap.tech/";
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo,
          queryParams: provider === "google" ? {
            access_type: "offline",
            prompt: "consent",
          } : undefined,
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
          setSuccessMsg("Account created! Please check your inbox to verify your email address.");
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
    <>
      <Script 
        src="https://accounts.google.com/gsi/client?hl=en" 
        strategy="afterInteractive"
        onLoad={setupGoogleIdentity}
      />

      <div className="min-h-screen bg-[#0d0e11] flex flex-col justify-center items-center px-4 py-12 text-[#f3f4f6]">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="w-full max-w-sm space-y-5"
        >
          {/* Brand Header */}
          <div className="text-center space-y-1.5">
            <Link href="/" className="inline-flex items-center gap-2">
              <div className="w-8 h-8 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
                <AudioWaveform className="w-4 h-4" />
              </div>
              <span className="text-lg font-semibold tracking-tight text-[#f3f4f6]">
                RecMap
              </span>
            </Link>
            <p className="text-xs text-[#9ca3af]">
              Meeting Intelligence & Synthesis Platform
            </p>
          </div>

          {/* Auth Card */}
          <div className="p-6 rounded-xl bg-[#131418] border border-[#22242a] space-y-4 shadow-lg">
            {infoMsg && (
              <div className="p-2.5 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 text-xs text-[#f3f4f6]">
                {infoMsg}
              </div>
            )}

            {/* Mode Switcher */}
            <div className="flex bg-[#18191f] p-1 rounded-md border border-[#22242a]">
              <button
                type="button"
                onClick={() => {
                  setMode("signin");
                  setErrorMsg(null);
                  setSuccessMsg(null);
                }}
                className={`flex-1 py-1 text-xs font-medium rounded transition-colors ${
                  mode === "signin"
                    ? "bg-[#22242a] text-[#f3f4f6]"
                    : "text-[#9ca3af] hover:text-[#f3f4f6]"
                }`}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode("signup");
                  setErrorMsg(null);
                  setSuccessMsg(null);
                }}
                className={`flex-1 py-1 text-xs font-medium rounded transition-colors ${
                  mode === "signup"
                    ? "bg-[#22242a] text-[#f3f4f6]"
                    : "text-[#9ca3af] hover:text-[#f3f4f6]"
                }`}
              >
                Create Account
              </button>
            </div>

            {errorMsg && (
              <div className="p-2.5 rounded-md bg-[#ef4444]/10 border border-[#ef4444]/20 text-xs text-[#ef4444] flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {successMsg && (
              <div className="p-2.5 rounded-md bg-[#10b981]/10 border border-[#10b981]/20 text-xs text-[#10b981] flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* OAuth Buttons */}
            <div className="space-y-2">
              <button
                type="button"
                disabled={Boolean(oauthLoading) || loading}
                onClick={handleGoogleSignIn}
                className="w-full h-8 px-3 rounded-md bg-[#18191f] hover:bg-[#1e2027] border border-[#22242a] text-xs font-medium text-[#f3f4f6] flex items-center justify-center relative transition-colors disabled:opacity-50 cursor-pointer"
              >
                {oauthLoading === "google" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#ff5c47]" />
                ) : (
                  <>
                    <div className="absolute left-3 flex items-center justify-center w-3.5 h-3.5">
                      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                      </svg>
                    </div>
                    <span>Continue with Google</span>
                  </>
                )}
              </button>

              <button
                type="button"
                disabled={Boolean(oauthLoading) || loading}
                onClick={() => handleOAuthSignIn("github")}
                className="w-full h-8 px-3 rounded-md bg-[#18191f] hover:bg-[#1e2027] border border-[#22242a] text-xs font-medium text-[#f3f4f6] flex items-center justify-center relative transition-colors disabled:opacity-50 cursor-pointer"
              >
                {oauthLoading === "github" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#ff5c47]" />
                ) : (
                  <>
                    <div className="absolute left-3 flex items-center justify-center w-3.5 h-3.5">
                      <svg className="w-3.5 h-3.5 fill-current text-[#f3f4f6]" viewBox="0 0 24 24">
                        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                      </svg>
                    </div>
                    <span>Continue with GitHub</span>
                  </>
                )}
              </button>
            </div>

            <div id="google-hidden-btn-container" style={{ display: "none" }} aria-hidden="true" />

            <div className="relative flex items-center justify-center my-3">
              <div className="border-t border-[#22242a] w-full" />
              <span className="bg-[#131418] px-2 text-[10px] uppercase font-medium text-[#9ca3af] absolute">
                Or with email
              </span>
            </div>

            {/* Email / Password Form */}
            <form onSubmit={handleSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-[#9ca3af]">
                  Email
                </label>
                <div className="relative">
                  <Mail className="w-3.5 h-3.5 text-[#9ca3af] absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    placeholder="name@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full h-8 pl-8 pr-3 bg-[#18191f] border border-[#22242a] rounded-md text-xs text-[#f3f4f6] placeholder-[#9ca3af] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-[#9ca3af]">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-3.5 h-3.5 text-[#9ca3af] absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    required
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full h-8 pl-8 pr-3 bg-[#18191f] border border-[#22242a] rounded-md text-xs text-[#f3f4f6] placeholder-[#9ca3af] focus:outline-none focus:border-[#ff5c47]/50 transition-colors"
                  />
                </div>
              </div>

              <div className="pt-1">
                <Button
                  type="submit"
                  disabled={loading || Boolean(oauthLoading)}
                  className="w-full h-8 rounded-md bg-[#ff5c47] hover:bg-[#ff5c47]/90 text-white font-medium text-xs shadow-sm flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                >
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{mode === "signin" ? "Sign In" : "Create Account"}</span>
                  {!loading && <ArrowRight className="w-3 h-3" />}
                </Button>
              </div>
            </form>
          </div>

          <div className="flex items-center justify-between text-xs text-[#9ca3af] px-1">
            <Link
              href="/"
              className="hover:text-[#f3f4f6] transition-colors"
            >
              ← Back to workspace
            </Link>
            <Link
              href="/download"
              className="inline-flex items-center gap-1 text-[#ff5c47] hover:underline"
            >
              <Monitor className="w-3 h-3" />
              <span>Desktop App</span>
            </Link>
          </div>
        </motion.div>
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0d0e11] flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-[#ff5c47] animate-spin" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
