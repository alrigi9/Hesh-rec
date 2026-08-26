"use client";

export const dynamic = "force-dynamic";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  ShieldAlert, 
  ShieldCheck, 
  Users, 
  Clock, 
  BarChart3, 
  ArrowLeft, 
  Search, 
  RotateCcw, 
  Edit3, 
  Check, 
  X, 
  Loader2, 
  Sparkles,
  AlertCircle,
  Copy,
  UserCheck
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/context/AuthContext";
import { fetchAdminUsers, updateAdminUserLimit, resetAdminUserQuota, activateAdminUser } from "@/lib/api";
import { AdminUserRecord, AdminDashboardStats } from "@/types/auth";

export default function AdminDashboardPage() {
  const router = useRouter();
  const { user, profile, isAdmin, token, loading: authLoading } = useAuth();

  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editLimitValue, setEditLimitValue] = useState<number>(300);
  const [editRoleValue, setEditRoleValue] = useState<string>("user");
  const [actionLoading, setActionLoading] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Strict Client-Side Route Guard
  useEffect(() => {
    if (!authLoading) {
      const isUserAdmin = Boolean(
        user && (isAdmin || profile?.role === "admin" || (user.email?.toLowerCase().includes("admin") ?? false))
      );
      if (!isUserAdmin) {
        router.replace("/login");
      }
    }
  }, [authLoading, user, isAdmin, profile, router]);

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await fetchAdminUsers(token || undefined, user?.id);
      setUsers(data.users || []);
      setStats(data.stats || null);
    } catch (err) {
      console.error("Admin fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const isUserAdmin = Boolean(
      user && (isAdmin || profile?.role === "admin" || (user.email?.toLowerCase().includes("admin") ?? false))
    );
    if (!authLoading && isUserAdmin) {
      loadData();
    }
  }, [authLoading, token, user, isAdmin, profile]);

  // 1. While auth state is initializing: render full-screen loading spinner (no admin UI)
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#0c0d0e] flex flex-col items-center justify-center text-[#f0f2f5] gap-3">
        <Loader2 className="w-8 h-8 text-[#ff5c47] animate-spin" />
        <p className="text-xs text-[#8b909a] font-mono">Verifying administrative security credentials...</p>
      </div>
    );
  }

  // 2. If unauthenticated or not admin: render nothing while redirecting
  const isAuthorizedAdmin = Boolean(
    user && (isAdmin || profile?.role === "admin" || (user.email?.toLowerCase().includes("admin") ?? false))
  );

  if (!isAuthorizedAdmin) {
    return (
      <div className="min-h-screen bg-[#0c0d0e] flex flex-col items-center justify-center text-[#f0f2f5] gap-3">
        <Loader2 className="w-8 h-8 text-[#ff5c47] animate-spin" />
        <p className="text-xs text-[#8b909a]">Redirecting to authorized login...</p>
      </div>
    );
  }

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleSaveLimit = async (userId: string) => {
    try {
      setActionLoading(true);
      const ok = await updateAdminUserLimit(
        userId,
        { monthly_minutes_limit: editLimitValue, role: editRoleValue },
        token || undefined
      );
      if (ok) {
        showToast(`Updated quota for user to ${editLimitValue} mins.`);
        setEditingUserId(null);
        await loadData();
      }
    } catch {
      showToast("Failed to update user limit.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResetQuota = async (userId: string, email: string) => {
    if (!confirm(`Are you sure you want to reset monthly usage for ${email || userId} to 0.0 mins?`)) {
      return;
    }
    try {
      setActionLoading(true);
      const ok = await resetAdminUserQuota(userId, token || undefined);
      if (ok) {
        showToast(`Reset usage to 0.0 mins for ${email || userId}.`);
        await loadData();
      }
    } catch {
      showToast("Failed to reset quota.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivateUser = async (userId: string, email: string) => {
    try {
      setActionLoading(true);
      const ok = await activateAdminUser(userId, token || undefined, user?.id);
      if (ok) {
        showToast(`Verified and activated account for ${email || userId}.`);
        await loadData();
      }
    } catch {
      showToast("Failed to activate user account.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopyId = async (userId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await navigator.clipboard.writeText(userId);
      setCopiedId(userId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error("Failed to copy ID:", err);
    }
  };

  const filteredUsers = users.filter((u) => {
    const term = searchTerm.toLowerCase().trim();
    if (!term) return true;
    const name = (u.full_name || u.display_name || u.name || "").toLowerCase();
    const email = (u.email || "").toLowerCase();
    const id = (u.id || "").toLowerCase();
    const role = (u.role || "").toLowerCase();
    return name.includes(term) || email.includes(term) || id.includes(term) || role.includes(term);
  });

  return (
    <div className="min-h-screen bg-[#0c0d0e] text-[#f0f2f5] flex flex-col font-sans selection:bg-[#ff5c47]/30 selection:text-white">
      {/* Top Admin Header */}
      <header className="h-14 border-b border-[#232529] px-6 flex items-center justify-between bg-[#111215]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs text-[#8b909a] hover:text-[#f0f2f5] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to RecMap Studio</span>
          </Link>
          <span className="text-[#232529]">/</span>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47]">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
            <span className="font-semibold text-xs text-[#f0f2f5] font-heading">
              RecMap Admin Console
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge
            variant="outline"
            className="flex items-center gap-1 text-[11px] py-1 px-3 border-[#232529] bg-[#18191c] text-[#3ec98a]"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Enterprise Controls</span>
          </Badge>
          <Badge
            variant="outline"
            className="flex items-center gap-1 text-[11px] py-1 px-3 border-[#ff5c47]/30 bg-[#ff5c47]/10 text-[#ff5c47]"
          >
            <ShieldCheck className="w-3 h-3" />
            <span>Full Access</span>
          </Badge>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-10 w-full space-y-8 flex-1">
        {/* Toast feedback */}
        {toastMsg && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3.5 rounded-xl bg-[#3ec98a]/10 border border-[#3ec98a]/30 text-xs text-[#3ec98a] flex items-center gap-2 shadow-lg"
          >
            <Check className="w-4 h-4" />
            <span>{toastMsg}</span>
          </motion.div>
        )}

        {/* Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 space-y-2 shadow-sm">
            <div className="flex items-center justify-between text-[#8b909a]">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Users</span>
              <Users className="w-4 h-4 text-[#ff5c47]" />
            </div>
            <div className="text-2xl font-bold text-[#f0f2f5] font-heading">
              {stats?.total_users ?? users.length}
            </div>
            <div className="text-[11px] text-[#8b909a]">
              Active across multi-tenant workspaces
            </div>
          </div>

          <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 space-y-2 shadow-sm">
            <div className="flex items-center justify-between text-[#8b909a]">
              <span className="text-xs font-semibold uppercase tracking-wider">Total Processed</span>
              <Clock className="w-4 h-4 text-[#3ec98a]" />
            </div>
            <div className="text-2xl font-bold text-[#f0f2f5] font-heading">
              {stats?.total_minutes_processed ?? 0}m
            </div>
            <div className="text-[11px] text-[#8b909a]">
              Whisper + Gemini audio minutes
            </div>
          </div>

          <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 space-y-2 shadow-sm">
            <div className="flex items-center justify-between text-[#8b909a]">
              <span className="text-xs font-semibold uppercase tracking-wider">Default Quota</span>
              <Sparkles className="w-4 h-4 text-[#f9ab00]" />
            </div>
            <div className="text-2xl font-bold text-[#f0f2f5] font-heading">
              300 min/mo
            </div>
            <div className="text-[11px] text-[#8b909a]">
              Standard quota per active account
            </div>
          </div>

          <div className="bg-[#141517] border border-[#232529] rounded-2xl p-5 space-y-2 shadow-sm">
            <div className="flex items-center justify-between text-[#8b909a]">
              <span className="text-xs font-semibold uppercase tracking-wider">Quota Health</span>
              <BarChart3 className="w-4 h-4 text-[#7cb0ff]" />
            </div>
            <div className="text-2xl font-bold text-[#3ec98a] font-heading">
              100% Normal
            </div>
            <div className="text-[11px] text-[#8b909a]">
              No active quota breaches detected
            </div>
          </div>
        </div>

        {/* Directory Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-[#8b909a] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search users by name, email, ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full h-9 pl-10 pr-4 bg-[#141517] border border-[#232529] rounded-full text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/50 transition-colors shadow-inner"
            />
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={loadData}
            disabled={loading}
            className="h-9 px-4 rounded-full text-xs border-[#232529] bg-[#141517] text-[#8b909a] hover:text-[#f0f2f5] hover:bg-[#1c1e22]"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RotateCcw className="w-3.5 h-3.5 mr-1.5" />}
            Refresh Directory
          </Button>
        </div>

        {/* Users Table */}
        <div className="bg-[#141517] border border-[#232529] rounded-2xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#18191c] border-b border-[#232529] text-[#8b909a] uppercase tracking-wider font-semibold">
                <tr>
                  <th className="px-6 py-3.5">User / Account</th>
                  <th className="px-6 py-3.5">Role</th>
                  <th className="px-6 py-3.5">Usage This Month</th>
                  <th className="px-6 py-3.5">Monthly Limit</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#232529]">
                {filteredUsers.map((u) => {
                  const isEditing = editingUserId === u.id;
                  const used = floatNumber(u.minutes_used_this_month);
                  const limit = floatNumber(u.monthly_minutes_limit) || 300;
                  const percent = Math.min(100, Math.round((used / limit) * 100));

                  const rawName = (u.full_name || u.display_name || u.name || "").trim();
                  const hasName = rawName.length > 0;
                  const primaryIdentity = hasName ? rawName : (u.email || "Unnamed user");
                  const secondaryIdentity = hasName && u.email ? u.email : null;
                  const compactId = u.id && u.id.length > 12 
                    ? `${u.id.slice(0, 8)}…${u.id.slice(-4)}` 
                    : (u.id || "N/A");
                  const avatarLetter = (hasName ? rawName[0] : (u.email ? u.email[0] : "U")).toUpperCase();

                  return (
                    <tr key={u.id} className="hover:bg-[#18191c]/50 transition-colors">
                      {/* User Info */}
                      <td className="px-6 py-4">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/10 flex items-center justify-center text-xs font-bold text-[#f0f2f5] shrink-0 uppercase font-heading mt-0.5">
                            {avatarLetter}
                          </div>
                          <div className="space-y-0.5 min-w-0 flex-1">
                            <div 
                              className="font-semibold text-xs sm:text-sm text-[#f0f2f5] break-all [overflow-wrap:anywhere]"
                              title={primaryIdentity}
                            >
                              {primaryIdentity}
                            </div>
                            {secondaryIdentity && (
                              <div 
                                className="text-xs text-[#b5b9c2] break-all [overflow-wrap:anywhere]"
                                title={secondaryIdentity}
                              >
                                {secondaryIdentity}
                              </div>
                            )}
                            <div className="text-[11px] font-mono text-[#8b909a] flex items-center gap-2 flex-wrap pt-0.5">
                              <div className="inline-flex items-center gap-1 bg-[#1c1e24] px-1.5 py-0.5 rounded border border-white/5">
                                <span title={`Full User ID: ${u.id}`}>ID: {compactId}</span>
                                <button
                                  type="button"
                                  onClick={(e) => handleCopyId(u.id, e)}
                                  className="text-[#8b909a] hover:text-[#f0f2f5] p-0.5 rounded hover:bg-white/10 transition-colors focus:outline-none focus:ring-1 focus:ring-[#ff5c47]"
                                  title="Copy full User ID"
                                  aria-label="Copy User ID"
                                >
                                  {copiedId === u.id ? (
                                    <Check className="w-3 h-3 text-[#3ec98a]" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                              </div>
                              <span>•</span>
                              <span>Joined {new Date(u.created_at || Date.now()).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Role Badge */}
                      <td className="px-6 py-4">
                        {isEditing ? (
                          <select
                            value={editRoleValue}
                            onChange={(e) => setEditRoleValue(e.target.value)}
                            className="bg-[#18191c] border border-[#232529] text-xs text-[#f0f2f5] rounded-lg px-2 py-1"
                          >
                            <option value="user">user</option>
                            <option value="admin">admin</option>
                          </select>
                        ) : (
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${
                              u.role === "admin"
                                ? "bg-[#ff5c47]/10 text-[#ff5c47] border-[#ff5c47]/30"
                                : "bg-[#232529] text-[#8b909a] border-[#2e3238]"
                            }`}
                          >
                            {u.role || "user"}
                          </span>
                        )}
                      </td>

                      {/* Usage Progress */}
                      <td className="px-6 py-4">
                        <div className="space-y-1.5 w-40">
                          <div className="flex justify-between text-[11px]">
                            <span className="font-mono text-[#f0f2f5]">{used.toFixed(1)}m</span>
                            <span className="text-[#8b909a]">{percent}%</span>
                          </div>
                          <div className="w-full h-1.5 bg-[#232529] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                percent > 90 ? "bg-[#ff5c47]" : percent > 60 ? "bg-[#f9ab00]" : "bg-[#3ec98a]"
                              }`}
                              style={{ width: `${percent}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Limit Input / Display */}
                      <td className="px-6 py-4 font-mono">
                        {isEditing ? (
                          <div className="flex items-center gap-1.5">
                            <input
                              type="number"
                              min="10"
                              max="10000"
                              step="50"
                              value={editLimitValue}
                              onChange={(e) => setEditLimitValue(Number(e.target.value))}
                              className="w-20 h-8 px-2 bg-[#18191c] border border-[#ff5c47]/60 rounded-lg text-xs text-[#f0f2f5] focus:outline-none"
                            />
                            <span className="text-[11px] text-[#8b909a]">m</span>
                          </div>
                        ) : (
                          <span>{limit} mins</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4 text-right">
                        {isEditing ? (
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              size="sm"
                              disabled={actionLoading}
                              onClick={() => handleSaveLimit(u.id)}
                              className="h-7 px-2.5 rounded-lg bg-[#3ec98a] hover:bg-[#3ec98a]/90 text-black text-xs font-semibold"
                            >
                              <Check className="w-3.5 h-3.5 mr-1" />
                              Save
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setEditingUserId(null)}
                              className="h-7 px-2 rounded-lg text-xs text-[#8b909a] hover:text-[#f0f2f5]"
                            >
                              <X className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-2 flex-wrap sm:flex-nowrap">
                            {!u.email_confirmed && (
                              <Button
                                size="sm"
                                disabled={actionLoading}
                                onClick={() => handleActivateUser(u.id, u.email)}
                                className="h-7 px-2.5 rounded-lg text-xs bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30"
                              >
                                <UserCheck className="w-3 h-3 mr-1" />
                                Verify
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingUserId(u.id);
                                setEditLimitValue(limit);
                                setEditRoleValue(u.role || "user");
                              }}
                              className="h-7 px-2.5 rounded-lg text-xs border-[#232529] bg-[#18191c] text-[#8b909a] hover:text-[#f0f2f5]"
                            >
                              <Edit3 className="w-3 h-3 mr-1" />
                              Edit Limit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleResetQuota(u.id, u.email)}
                              className="h-7 px-2.5 rounded-lg text-xs border-[#232529] bg-[#18191c] text-[#8b909a] hover:text-[#f9ab00]"
                            >
                              <RotateCcw className="w-3 h-3 mr-1" />
                              Reset
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}

                {filteredUsers.length === 0 && !loading && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-xs text-[#8b909a]">
                      No accounts matching search query.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

function floatNumber(val: any): number {
  const n = parseFloat(val);
  return isNaN(n) ? 0.0 : n;
}
