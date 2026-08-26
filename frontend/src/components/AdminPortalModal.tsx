"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  Users, 
  Clock, 
  Search, 
  RotateCcw, 
  Zap, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  RefreshCw,
  X,
  SlidersHorizontal,
  Activity,
  BarChart3,
  Check,
  Copy,
  UserCheck
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  fetchAdminUsers, 
  updateAdminUserLimit, 
  resetAdminUserQuota, 
  activateAdminUser 
} from "@/lib/api";
import { AdminUserRecord, AdminDashboardStats } from "@/types/auth";
import { useAuth } from "@/context/AuthContext";

interface AdminPortalModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AdminPortalModal({ isOpen, onClose }: AdminPortalModalProps) {
  const { user, token, refreshProfile } = useAuth();
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [sliderValues, setSliderValues] = useState<Record<string, number>>({});
  const [savedLimits, setSavedLimits] = useState<Record<string, number>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, "saving" | "saved" | "idle">>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchAdminUsers(token || undefined, user?.id);
      setUsers(data.users || []);
      setStats(data.stats || null);
      
      const initialLimits: Record<string, number> = {};
      (data.users || []).forEach((u) => {
        const lim = u.monthly_minutes_limit ?? 300;
        initialLimits[u.id] = lim;
      });
      setSliderValues(initialLimits);
      setSavedLimits(initialLimits);
    } catch (err) {
      console.error("Error loading admin users:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  const handleSliderChange = (userId: string, newValue: number) => {
    setSliderValues((prev) => ({ ...prev, [userId]: newValue }));
  };

  // Explicit confirmation button handler (prevents accidental auto-saving)
  const handleSliderCommit = async (userId: string) => {
    const newLimit = sliderValues[userId] ?? 300;
    setSaveStatus((prev) => ({ ...prev, [userId]: "saving" }));
    setActionLoadingId(`save-${userId}`);
    try {
      await updateAdminUserLimit(
        userId,
        { monthly_minutes_limit: newLimit },
        token || undefined,
        user?.id
      );
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, monthly_minutes_limit: newLimit } : u))
      );
      setSavedLimits((prev) => ({ ...prev, [userId]: newLimit }));
      setSaveStatus((prev) => ({ ...prev, [userId]: "saved" }));
      setTimeout(() => {
        setSaveStatus((prev) => ({ ...prev, [userId]: "idle" }));
      }, 2000);
      // Immediately refresh auth context so sidebar and header update dynamically
      refreshProfile();
    } catch (err) {
      console.error("Failed to update user limit:", err);
      setSaveStatus((prev) => ({ ...prev, [userId]: "idle" }));
    } finally {
      setActionLoadingId(null);
    }
  };

  // Manual User Verification / Activation Action
  const handleActivateUser = async (targetUser: AdminUserRecord) => {
    setActionLoadingId(`activate-${targetUser.id}`);
    try {
      await activateAdminUser(targetUser.id, token || undefined, user?.id);
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, email_confirmed: true } : u))
      );
      if (targetUser.id === user?.id) {
        refreshProfile();
      }
    } catch (err) {
      console.error("Failed to activate user:", err);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleResetQuota = async (targetUser: AdminUserRecord) => {
    setActionLoadingId(`reset-${targetUser.id}`);
    try {
      await resetAdminUserQuota(targetUser.id, token || undefined, user?.id);
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, minutes_used_this_month: 0.0 } : u))
      );
      if (targetUser.id === user?.id) {
        refreshProfile();
      }
    } catch (err) {
      console.error("Failed to reset quota:", err);
    } finally {
      setActionLoadingId(null);
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
    const q = search.toLowerCase().trim();
    if (!q) return true;
    const name = (u.full_name || u.display_name || u.name || "").toLowerCase();
    const email = (u.email || "").toLowerCase();
    const role = (u.role || "").toLowerCase();
    const id = (u.id || "").toLowerCase();
    return name.includes(q) || email.includes(q) || role.includes(q) || id.includes(q);
  });

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent 
        showCloseButton={false}
        className="max-w-4xl w-[95vw] max-h-[90vh] flex flex-col rounded-2xl overflow-hidden bg-[#0f1013] border border-white/[0.08] text-[#f0f2f5] p-0 shadow-2xl backdrop-blur-xl"
      >
        {/* Header Bar */}
        <div className="px-4 py-3.5 sm:px-6 sm:py-4 border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3 shrink-0 bg-[#131519]/95">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/25 flex items-center justify-center text-[#ff5c47] shadow-inner shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <DialogTitle className="text-sm sm:text-base font-bold text-[#f0f2f5] font-heading tracking-tight">
                  Admin Management Console
                </DialogTitle>
                <Badge className="bg-[#ff5c47]/15 text-[#ff5c47] hover:bg-[#ff5c47]/20 border border-[#ff5c47]/30 text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded-full">
                  Full Access
                </Badge>
              </div>
              <DialogDescription className="text-xs text-[#8b909a] mt-0.5">
                Multi-tenant system controls, real-time usage quotas, and account verification
              </DialogDescription>
            </div>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <Button
              size="sm"
              variant="outline"
              onClick={loadData}
              disabled={loading}
              className="h-8 px-3 rounded-full border-white/10 bg-[#181a1f] text-[#8b909a] hover:text-[#f0f2f5] hover:border-white/20 text-xs gap-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-[#ff5c47]" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
            
            <Button
              size="icon"
              variant="ghost"
              onClick={onClose}
              className="w-8 h-8 rounded-full text-[#8b909a] hover:text-[#f0f2f5] hover:bg-white/10 transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Slim Responsive 4-Column Metric Stats Grid */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3.5 sm:p-4 bg-[#0b0c0e]/80 border-b border-white/[0.06] shrink-0 text-xs">
            <div className="p-2.5 sm:p-3 rounded-xl bg-[#14161b] border border-white/[0.06]">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Total Users</span>
                <Users className="w-3.5 h-3.5 text-[#8b909a]/70" />
              </div>
              <div className="text-base sm:text-lg font-bold text-[#f0f2f5] font-heading mt-1">
                {stats.total_users}
              </div>
            </div>

            <div className="p-2.5 sm:p-3 rounded-xl bg-[#14161b] border border-white/[0.06]">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Minutes Processed</span>
                <Activity className="w-3.5 h-3.5 text-[#ff5c47]/80" />
              </div>
              <div className="text-base sm:text-lg font-bold text-[#ff5c47] font-heading mt-1">
                {stats.total_minutes_processed.toFixed(1)}m
              </div>
            </div>

            <div className="p-2.5 sm:p-3 rounded-xl bg-[#14161b] border border-white/[0.06]">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Avg Usage</span>
                <BarChart3 className="w-3.5 h-3.5 text-[#3ec98a]/80" />
              </div>
              <div className="text-base sm:text-lg font-bold text-[#3ec98a] font-heading mt-1">
                {stats.average_usage_per_user.toFixed(1)}m
              </div>
            </div>

            <div className="p-2.5 sm:p-3 rounded-xl bg-[#14161b] border border-white/[0.06]">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Standard Limit</span>
                <Clock className="w-3.5 h-3.5 text-[#7cb0ff]/80" />
              </div>
              <div className="text-base sm:text-lg font-bold text-[#7cb0ff] font-heading mt-1">
                {stats.system_limit_per_user}m / mo
              </div>
            </div>
          </div>
        )}

        {/* Search & Directory Filter Bar */}
        <div className="px-4 py-3 sm:px-6 sm:py-3 border-b border-white/[0.06] bg-[#121418] shrink-0 flex flex-wrap items-center justify-between gap-3">
          <div className="relative flex-1 min-w-[220px] max-w-sm">
            <Search className="w-3.5 h-3.5 text-[#8b909a] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search users by name, email, ID, or role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-3 bg-[#181a1f] border border-white/10 rounded-xl text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors"
            />
          </div>
          <div className="text-xs text-[#8b909a] font-mono">
            {filteredUsers.length} user{filteredUsers.length === 1 ? "" : "s"} indexed
          </div>
        </div>

        {/* Scrollable User Directory Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {loading && users.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <Loader2 className="w-6 h-6 animate-spin text-[#ff5c47] mx-auto" />
              <p className="text-xs text-[#8b909a]">Loading user profiles and quotas...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="py-16 text-center space-y-2">
              <Users className="w-8 h-8 text-[#8b909a] mx-auto opacity-40" />
              <p className="text-sm font-medium text-[#f0f2f5]">No matching users found</p>
              <p className="text-xs text-[#8b909a]">Try adjusting your search query</p>
            </div>
          ) : (
            filteredUsers.map((u) => {
              const currentSlider = sliderValues[u.id] ?? u.monthly_minutes_limit ?? 300;
              const savedLimit = savedLimits[u.id] ?? u.monthly_minutes_limit ?? 300;
              const hasChanged = currentSlider !== savedLimit;
              const used = u.minutes_used_this_month ?? 0.0;
              const isConfirmed = Boolean(u.email_confirmed);
              const percent = Math.min(100, Math.round((used / Math.max(1, currentSlider)) * 100));
              const status = saveStatus[u.id] || "idle";

              // Identity Priority Display Calculation
              const rawName = (u.full_name || u.display_name || u.name || "").trim();
              const hasName = rawName.length > 0;
              const primaryIdentity = hasName ? rawName : (u.email || "Unnamed user");
              const secondaryIdentity = hasName && u.email ? u.email : null;
              const compactId = u.id && u.id.length > 12 
                ? `${u.id.slice(0, 8)}…${u.id.slice(-4)}` 
                : (u.id || "N/A");
              const avatarLetter = (hasName ? rawName[0] : (u.email ? u.email[0] : "U")).toUpperCase();

              return (
                <div
                  key={u.id}
                  className="p-4 sm:p-5 rounded-2xl bg-[#14161b] border border-white/[0.07] hover:border-white/[0.14] transition-all space-y-3.5 shadow-sm"
                >
                  {/* User Profile Row */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 min-w-0">
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      {/* Avatar */}
                      <div className="w-10 h-10 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center text-sm font-bold text-[#f0f2f5] shrink-0 uppercase font-heading mt-0.5">
                        {avatarLetter}
                      </div>
                      
                      {/* Identity Details Block */}
                      <div className="space-y-1 min-w-0 flex-1">
                        {/* Primary Line: Full Name or Email */}
                        <div className="flex items-center gap-2 flex-wrap min-w-0">
                          <span 
                            className="text-xs sm:text-sm font-semibold text-[#f0f2f5] break-all [overflow-wrap:anywhere]"
                            title={primaryIdentity}
                          >
                            {primaryIdentity}
                          </span>
                          
                          {u.role === "admin" ? (
                            <Badge className="bg-[#ff5c47]/15 text-[#ff5c47] border border-[#ff5c47]/30 text-[10px] px-1.5 py-0 h-4 font-mono shrink-0">
                              Admin
                            </Badge>
                          ) : (
                            <Badge className="bg-white/5 text-[#8b909a] border border-white/10 text-[10px] px-1.5 py-0 h-4 font-mono shrink-0">
                              User
                            </Badge>
                          )}

                          {isConfirmed ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#3ec98a]/10 border border-[#3ec98a]/20 text-[#3ec98a] text-[10px] font-medium shrink-0">
                              <CheckCircle2 className="w-3 h-3" />
                              Confirmed
                            </span>
                          ) : (
                            <Button
                              size="sm"
                              disabled={actionLoadingId === `activate-${u.id}`}
                              onClick={() => handleActivateUser(u)}
                              className="h-5 px-2 rounded-full bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30 text-[10px] font-medium gap-1 transition-all shrink-0"
                            >
                              {actionLoadingId === `activate-${u.id}` ? (
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              ) : (
                                <UserCheck className="w-2.5 h-2.5" />
                              )}
                              Verify Account
                            </Button>
                          )}
                        </div>

                        {/* Secondary Line: Email (when name exists as primary line) */}
                        {secondaryIdentity && (
                          <div 
                            className="text-xs text-[#b5b9c2] break-all [overflow-wrap:anywhere]"
                            title={secondaryIdentity}
                          >
                            {secondaryIdentity}
                          </div>
                        )}

                        {/* Compact User ID with Copy Button & Joined Date */}
                        <div className="text-[11px] text-[#8b909a] font-mono flex items-center gap-2 flex-wrap pt-0.5">
                          <div className="inline-flex items-center gap-1 bg-[#1c1e24] px-1.5 py-0.5 rounded border border-white/5 shrink-0">
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
                          <span className="shrink-0">Joined {new Date(u.created_at || Date.now()).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>

                    {/* Status & Quick Actions */}
                    <div className="flex items-center gap-2 shrink-0 self-start sm:self-center pt-1 sm:pt-0">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={actionLoadingId === `reset-${u.id}`}
                        onClick={() => handleResetQuota(u)}
                        className="h-7 sm:h-8 px-3 rounded-full border-white/10 bg-[#191b20] hover:bg-[#20232a] text-[#8b909a] hover:text-[#f0f2f5] text-xs font-medium gap-1.5 transition-all shrink-0 whitespace-nowrap"
                      >
                        {actionLoadingId === `reset-${u.id}` ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3.5 h-3.5" />
                        )}
                        Reset Usage
                      </Button>
                    </div>
                  </div>

                  {/* Quota Slider & Explicit Confirmation Controls */}
                  <div className="p-3 sm:p-3.5 rounded-xl bg-[#181a20] border border-white/[0.05] space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2 text-[#8b909a]">
                        <SlidersHorizontal className="w-3.5 h-3.5 text-[#ff5c47]" />
                        <span className="font-medium">Monthly Quota:</span>
                        <span className="text-[#f0f2f5] font-bold font-mono text-xs sm:text-sm">
                          {currentSlider} mins
                        </span>
                        
                        {hasChanged && (
                          <span className="text-[10px] text-[#ff5c47] font-semibold bg-[#ff5c47]/10 px-1.5 py-0.5 rounded border border-[#ff5c47]/20">
                            Unsaved
                          </span>
                        )}
                        {status === "saved" && (
                          <span className="text-[10px] text-[#3ec98a] font-medium">
                            ✓ Saved
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="font-mono text-[11px] text-[#8b909a]">
                          Used: <span className="text-[#f0f2f5] font-semibold">{used.toFixed(1)}m</span> ({percent}%)
                        </div>

                        {/* Explicit Quota Confirmation Button */}
                        {hasChanged && (
                          <Button
                            size="sm"
                            disabled={actionLoadingId === `save-${u.id}`}
                            onClick={() => handleSliderCommit(u.id)}
                            className="h-6 px-2.5 rounded-full bg-[#3ec98a] hover:bg-[#3ec98a]/90 text-black font-semibold text-[11px] gap-1 shadow-md transition-all animate-pulse"
                          >
                            {actionLoadingId === `save-${u.id}` ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            Confirm Quota
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Range Slider Container */}
                    <div className="flex items-center gap-2.5">
                      <span className="text-[10px] text-[#8b909a] font-mono w-7">0m</span>
                      <input
                        type="range"
                        min="0"
                        max="5000"
                        step="50"
                        value={currentSlider}
                        onChange={(e) => handleSliderChange(u.id, Number(e.target.value))}
                        className="flex-1 h-1.5 sm:h-2 bg-[#23262d] rounded-lg appearance-none cursor-pointer accent-[#ff5c47]"
                      />
                      <span className="text-[10px] text-[#8b909a] font-mono w-11 text-right">5000m</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-1 rounded-full bg-[#23262d] overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          percent >= 90 ? "bg-[#ff5c47]" : percent >= 60 ? "bg-[#e5a93c]" : "bg-[#3ec98a]"
                        }`}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
