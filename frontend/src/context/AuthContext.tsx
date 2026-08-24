"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { User, Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import { UserProfile } from "@/types/auth";
import { fetchUserProfile } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: UserProfile | null;
  loading: boolean;
  token: string | null;
  isAdmin: boolean;
  signIn: (email: string, pass: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, pass: string) => Promise<{ error: Error | null; needsEmailConfirmation?: boolean }>;
  signInWithGoogleIdToken: (idToken: string) => Promise<{ error: Error | null; data?: any }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const token = session?.access_token || null;
  const isAdmin = profile?.role === "admin" || (user?.email?.toLowerCase().includes("admin") ?? false);

  const cleanOAuthHash = () => {
    if (
      typeof window !== "undefined" &&
      window.location.hash &&
      (window.location.hash.includes("access_token") || window.location.hash.includes("refresh_token") || window.location.hash.includes("error_description"))
    ) {
      try {
        window.history.replaceState(null, "", window.location.pathname);
      } catch (err) {
        console.error("Error cleaning URL hash:", err);
      }
    }
  };

  const loadProfile = async (u: User | null, s: Session | null) => {
    if (!u) {
      // Default guest/demo profile
      setProfile({
        id: "guest",
        email: "guest@heshrec.com",
        role: "user",
        monthly_minutes_limit: 300.0,
        minutes_used_this_month: 0.0,
        minutes_remaining: 300.0,
        percent_used: 0.0,
        can_upload: true,
      });
      return;
    }

    try {
      const p = await fetchUserProfile(s?.access_token, u.id);
      setProfile(p);
    } catch {
      setProfile({
        id: u.id,
        email: u.email || "",
        role: u.email?.toLowerCase().includes("admin") ? "admin" : "user",
        monthly_minutes_limit: 300.0,
        minutes_used_this_month: 0.0,
        minutes_remaining: 300.0,
        percent_used: 0.0,
        can_upload: true,
      });
    }
  };

  useEffect(() => {
    let mounted = true;

    // Clean hash on immediate mount if token is present
    cleanOAuthHash();

    // Get initial session
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (!mounted) return;
      if (initialSession) cleanOAuthHash();
      setSession(initialSession);
      setUser(initialSession?.user ?? null);
      loadProfile(initialSession?.user ?? null, initialSession).finally(() => {
        if (mounted) setLoading(false);
      });
    });

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, currentSession) => {
        if (!mounted) return;
        if (currentSession) cleanOAuthHash();
        setSession(currentSession);
        setUser(currentSession?.user ?? null);
        loadProfile(currentSession?.user ?? null, currentSession);
      }
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = async (email: string, pass: string) => {
    const { error, data } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password: pass,
    });
    if (!error && data.user) {
      setUser(data.user);
      setSession(data.session);
      await loadProfile(data.user, data.session);
    }
    return { error };
  };

  const signUp = async (email: string, pass: string) => {
    const { error, data } = await supabase.auth.signUp({
      email: email.trim(),
      password: pass,
    });
    if (!error && data.user) {
      setUser(data.user);
      setSession(data.session);
      await loadProfile(data.user, data.session);
      return { 
        error: null, 
        needsEmailConfirmation: !data.session 
      };
    }
    return { error, needsEmailConfirmation: false };
  };

  const signInWithGoogleIdToken = async (idToken: string) => {
    const { data, error } = await supabase.auth.signInWithIdToken({
      provider: "google",
      token: idToken,
    });
    if (!error && data.user) {
      setUser(data.user);
      setSession(data.session);
      await loadProfile(data.user, data.session);
    }
    return { error, data };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    loadProfile(null, null);
  };

  const refreshProfile = async () => {
    await loadProfile(user, session);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        loading,
        token,
        isAdmin,
        signIn,
        signUp,
        signInWithGoogleIdToken,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
