"use client";

import React, { useState, useEffect, useTransition } from "react";
import { 
  ShieldCheck, 
  Users, 
  Clock, 
  Search, 
  RotateCcw, 
  Zap, 
  CheckCircle2, 
  AlertCircle, 
  Sliders, 
  Loader2, 
  RefreshCw,
  X,
  Mail,
  SlidersHorizontal,
  ChevronRight
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
  const [sliderValues, setSliderValues] = useState<Record<string, number>>({});
  const [saveStatus, setSaveStatus] = useState<Record<string, "saving" | "saved" | "idle">>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchAdminUsers(token || undefined, user?.id);
      setUsers(data.users || []);
      setStats(data.stats || null);
      // Initialize local slider values
      const initialLimits: Record<string, number> = {};
      (data.users || []).forEach((u) => {
        initialLimits[u.id] = u.monthly_minutes_limit ?? 300;
      });
      setSliderValues(initialLimits);
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

  const handleSliderCommit = async (userId: string, newLimit: number) => {
    setSaveStatus((prev) => ({ ...prev, [userId]: "saving" }));
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
      setSaveStatus((prev) => ({ ...prev, [userId]: "saved" }));
      setTimeout(() => {
        setSaveStatus((prev) => ({ ...prev, [userId]: "idle" }));
      }, 1500);
      if (userId === user?.id) {
        refreshProfile();
      }
    } catch (err) {
      console.error("Failed to update user limit:", err);
      setSaveStatus((prev) => ({ ...prev, [userId]: "idle" }));
    }
  };

  const handleActivateUser = async (targetUser: AdminUserRecord) => {
    setActionLoadingId(`activate-${targetUser.id}`);
    try {
      await activateAdminUser(targetUser.id, token || undefined, user?.id);
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, email_confirmed: true } : u))
      );
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

  const filteredUsers = users.filter((u) => {
    const q = search.toLowerCase();
    const email = (u.email || "").toLowerCase();
    const role = (u.role || "").toLowerCase();
    return email.includes(q) || role.includes(q);
  });

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl bg-[#111215] border border-[#232529] text-[#f0f2f5] p-0 overflow-hidden shadow-2xl rounded-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-[#232529] flex items-center justify-between shrink-0 bg-[#141517]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#ff5c47]/10 border border-[#ff5c47]/20 flex items-center justify-center text-[#ff5c47] shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-[#f0f2f5] font-heading flex items-center gap-2">
                Admin Management Console
                <Badge className="bg-[#ff5c47]/20 text-[#ff5c47] hover:bg-[#ff5c47]/20 border-0 text-[10px] uppercase tracking-wider font-mono">
                  Full Access
                </Badge>
              </DialogTitle>
              <DialogDescription className="text-xs text-[#8b909a] mt-0.5">
                Multi-tenant user directory, account activations, and dynamic quota sliders
              </DialogDescription>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={loadData}
              disabled={loading}
              className="h-8 px-3 rounded-full border-[#232529] bg-[#18191c] text-[#8b909a] hover:text-[#f0f2f5] text-xs gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={onClose}
              className="w-8 h-8 rounded-full text-[#8b909a] hover:text-[#f0f2f5] hover:bg-white/5"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Stats Metrics Bar */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-4 bg-[#0c0d0e]/60 border-b border-[#232529] shrink-0 text-xs">
            <div className="p-3 rounded-xl bg-[#141517] border border-[#232529]/60">
              <span className="text-[11px] text-[#8b909a]">Total Users</span>
              <div className="text-base font-bold text-[#f0f2f5] font-heading mt-0.5">
                {stats.total_users}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-[#141517] border border-[#232529]/60">
              <span className="text-[11px] text-[#8b909a]">Total Minutes Processed</span>
              <div className="text-base font-bold text-[#ff5c47] font-heading mt-0.5">
                {stats.total_minutes_processed.toFixed(1)}m
              </div>
            </div>
            <div className="p-3 rounded-xl bg-[#141517] border border-[#232529]/60">
              <span className="text-[11px] text-[#8b909a]">Average Usage</span>
              <div className="text-base font-bold text-[#3ec98a] font-heading mt-0.5">
                {stats.average_usage_per_user.toFixed(1)}m / user
              </div>
            </div>
            <div className="p-3 rounded-xl bg-[#141517] border border-[#232529]/60">
              <span className="text-[11px] text-[#8b909a]">Default Limit</span>
              <div className="text-base font-bold text-[#7cb0ff] font-heading mt-0.5">
                {stats.system_limit_per_user}m / mo
              </div>
            </div>
          </div>
        )}

        {/* Search Bar */}
        <div className="p-4 border-b border-[#232529] bg-[#141517] shrink-0 flex items-center justify-between gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-[#8b909a] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search users by email or role..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-9 pr-3 bg-[#18191c] border border-[#232529] rounded-xl text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors"
            />
          </div>
          <span className="text-xs text-[#8b909a] font-mono">
            {filteredUsers.length} user{filteredUsers.length === 1 ? "" : "s"}
          </span>
        </div>

        {/* Scrollable User Directory Table */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && users.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <Loader2 className="w-6 h-6 animate-spin text-[#ff5c47] mx-auto" />
              <p className="text-xs text-[#8b909a]">Loading user profiles and quotas...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="py-16 text-center space-y-2">
              <Users className="w-8 h-8 text-[#8b909a] mx-auto opacity-50" />
              <p className="text-xs text-[#8b909a]">No matching users found.</p>
            </div>
          ) : (
            filteredUsers.map((u) => {
              const currentSlider = sliderValues[u.id] ?? u.monthly_minutes_limit ?? 300;
              const used = u.minutes_used_this_month ?? 0.0;
              const isConfirmed = u.email_confirmed ?? true;
              const percent = Math.min(100, Math.round((used / Math.max(1, currentSlider)) * 100));
              const status = saveStatus[u.id] || "idle";

              return (
                <div
                  key={u.id}
                  className="p-4 rounded-2xl bg-[#141517] border border-[#232529] hover:border-[#2e3238] transition-all space-y-3"
                >
                  {/* User Top Row: Email, Role, Status Badges */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-xs font-semibold text-[#f0f2f5] shrink-0">
                        {u.email ? u.email[0].toUpperCase() : "U"}
                      </div>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-[#f0f2f5]">
                            {u.email || `User ${u.id.slice(0, 8)}`}
                          </span>
                          {u.role === "admin" && (
                            <Badge className="bg-[#ff5c47]/20 text-[#ff5c47] border-0 text-[10px] px-1.5 py-0 h-4">
                              Admin
                            </Badge>
                          )}
                        </div>
                        <div className="text-[11px] text-[#8b909a] font-mono">
                          ID: {u.id} • Joined {new Date(u.created_at || Date.now()).toLocaleDateString()}
                        </div>
                      </div>
                    </div>

                    {/* Status & Quick Action */}
                    <div className="flex items-center gap-2">
                      {isConfirmed ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#3ec98a]/10 border border-[#3ec98a]/20 text-[#3ec98a] text-[10px] font-medium">
                          <CheckCircle2 className="w-3 h-3" />
                          Confirmed
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          disabled={actionLoadingId === `activate-${u.id}`}
                          onClick={() => handleActivateUser(u)}
                          className="h-7 px-2.5 rounded-full bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30 text-[11px] font-medium gap-1"
                        >
                          {actionLoadingId === `activate-${u.id}` ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Zap className="w-3 h-3" />
                          )}
                          ⚡ Activate Account
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={actionLoadingId === `reset-${u.id}`}
                        onClick={() => handleResetQuota(u)}
                        className="h-7 px-2.5 rounded-full border-[#232529] bg-[#18191c] hover:bg-[#202227] text-[#8b909a] hover:text-[#f0f2f5] text-[11px] font-medium gap-1"
                      >
                        {actionLoadingId === `reset-${u.id}` ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3 h-3" />
                        )}
                        Reset Usage
                      </Button>
                    </div>
                  </div>

                  {/* Interactive Quota Slider Row */}
                  <div className="p-3 rounded-xl bg-[#18191c] border border-[#232529]/60 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5 text-[#8b909a]">
                        <SlidersHorizontal className="w-3.5 h-3.5 text-[#ff5c47]" />
                        <span>Monthly Quota Limit:</span>
                        <span className="text-[#f0f2f5] font-bold font-mono">
                          {currentSlider} mins
                        </span>
                        {status === "saving" && (
                          <span className="text-[10px] text-[#8b909a] animate-pulse">Saving...</span>
                        )}
                        {status === "saved" && (
                          <span className="text-[10px] text-[#3ec98a] font-medium">✓ Saved</span>
                        )}
                      </div>

                      <div className="font-mono text-[11px] text-[#8b909a]">
                        Used: <span className="text-[#f0f2f5] font-semibold">{used.toFixed(1)}m</span> ({percent}%)
                      </div>
                    </div>

                    {/* Range Slider */}
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="0"
                        max="5000"
                        step="50"
                        value={currentSlider}
                        onChange={(e) => handleSliderChange(u.id, Number(e.target.value))}
                        onMouseUp={() => handleSliderCommit(u.id, currentSlider)}
                        onTouchEnd={() => handleSliderCommit(u.id, currentSlider)}
                        className="flex-1 h-1.5 bg-[#232529] rounded-lg appearance-none cursor-pointer accent-[#ff5c47]"
                      />
                      <span className="text-[11px] text-[#8b909a] font-mono w-14 text-right">
                        {currentSlider}m
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-1.5 rounded-full bg-[#232529] overflow-hidden">
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
