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
  Calendar,
  Layers,
  Sparkles
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
    const id = (u.id || "").toLowerCase();
    return email.includes(q) || role.includes(q) || id.includes(q);
  });

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent 
        showCloseButton={false}
        className="w-[92vw] max-w-5xl md:max-w-6xl bg-[#0f1013] border border-white/[0.08] text-[#f0f2f5] p-0 overflow-hidden shadow-2xl rounded-2xl md:rounded-3xl max-h-[90vh] sm:max-h-[92vh] flex flex-col backdrop-blur-xl"
      >
        {/* Header Bar */}
        <div className="px-5 py-4 sm:px-8 sm:py-5 border-b border-white/[0.07] flex flex-wrap items-center justify-between gap-3 shrink-0 bg-[#131519]/90">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl sm:rounded-2xl bg-[#ff5c47]/10 border border-[#ff5c47]/25 flex items-center justify-center text-[#ff5c47] shadow-inner shrink-0">
              <ShieldCheck className="w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <DialogTitle className="text-base sm:text-lg font-bold text-[#f0f2f5] font-heading tracking-tight">
                  Admin Management Console
                </DialogTitle>
                <Badge className="bg-[#ff5c47]/15 text-[#ff5c47] hover:bg-[#ff5c47]/20 border border-[#ff5c47]/30 text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded-full">
                  Full Access
                </Badge>
              </div>
              <DialogDescription className="text-xs text-[#8b909a] mt-0.5">
                Multi-tenant system controls, real-time usage quotas, and account management
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

        {/* Top Analytics / Stats Metric Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-4 p-4 sm:px-8 sm:py-5 bg-[#0b0c0e]/80 border-b border-white/[0.06] shrink-0 text-xs">
            <div className="p-3.5 sm:p-4 rounded-xl sm:rounded-2xl bg-[#14161b] border border-white/[0.06] hover:border-white/10 transition-all flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Total Registered Users</span>
                <Users className="w-4 h-4 text-[#8b909a]/70" />
              </div>
              <div className="text-lg sm:text-2xl font-bold text-[#f0f2f5] font-heading mt-2 tracking-tight">
                {stats.total_users}
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl sm:rounded-2xl bg-[#14161b] border border-white/[0.06] hover:border-white/10 transition-all flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Minutes Ingested</span>
                <Activity className="w-4 h-4 text-[#ff5c47]/80" />
              </div>
              <div className="text-lg sm:text-2xl font-bold text-[#ff5c47] font-heading mt-2 tracking-tight">
                {stats.total_minutes_processed.toFixed(1)}m
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl sm:rounded-2xl bg-[#14161b] border border-white/[0.06] hover:border-white/10 transition-all flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Avg Usage / User</span>
                <BarChart3 className="w-4 h-4 text-[#3ec98a]/80" />
              </div>
              <div className="text-lg sm:text-2xl font-bold text-[#3ec98a] font-heading mt-2 tracking-tight">
                {stats.average_usage_per_user.toFixed(1)}m
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl sm:rounded-2xl bg-[#14161b] border border-white/[0.06] hover:border-white/10 transition-all flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8b909a]">
                <span className="text-[11px] font-medium">Monthly Standard Cap</span>
                <Clock className="w-4 h-4 text-[#7cb0ff]/80" />
              </div>
              <div className="text-lg sm:text-2xl font-bold text-[#7cb0ff] font-heading mt-2 tracking-tight">
                {stats.system_limit_per_user}m / mo
              </div>
            </div>
          </div>
        )}

        {/* Search & Directory Controls Filter Bar */}
        <div className="px-4 py-3 sm:px-8 sm:py-4 border-b border-white/[0.06] bg-[#121418] shrink-0 flex flex-wrap items-center justify-between gap-3">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <Search className="w-4 h-4 text-[#8b909a] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by email, role, or user ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-9 pr-4 bg-[#181a1f] border border-white/10 rounded-xl text-xs text-[#f0f2f5] placeholder-[#8b909a] focus:outline-none focus:border-[#ff5c47]/60 transition-colors"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-[#8b909a] font-mono">
            <span className="inline-block w-2 h-2 rounded-full bg-[#3ec98a] animate-pulse" />
            <span>
              {filteredUsers.length} user{filteredUsers.length === 1 ? "" : "s"} indexed
            </span>
          </div>
        </div>

        {/* Scrollable User Directory List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-8 space-y-3.5">
          {loading && users.length === 0 ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="w-7 h-7 animate-spin text-[#ff5c47] mx-auto" />
              <p className="text-xs text-[#8b909a]">Loading active directories and quota usage...</p>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="py-20 text-center space-y-2">
              <Users className="w-10 h-10 text-[#8b909a] mx-auto opacity-40" />
              <p className="text-sm font-medium text-[#f0f2f5]">No matching users found</p>
              <p className="text-xs text-[#8b909a]">Try adjusting your search query</p>
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
                  className="p-4 sm:p-5 rounded-2xl bg-[#14161b] border border-white/[0.07] hover:border-white/[0.14] transition-all space-y-4 shadow-sm"
                >
                  {/* User Profile Info Row */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center text-sm font-bold text-[#f0f2f5] shrink-0 uppercase font-heading shadow-inner">
                        {u.email ? u.email[0] : "U"}
                      </div>
                      
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs sm:text-sm font-semibold text-[#f0f2f5] truncate max-w-[200px] sm:max-w-xs md:max-w-md">
                            {u.email || `User ${u.id.slice(0, 8)}`}
                          </span>
                          
                          {u.role === "admin" ? (
                            <Badge className="bg-[#ff5c47]/15 text-[#ff5c47] border border-[#ff5c47]/30 text-[10px] px-2 py-0 h-4 font-mono">
                              Admin
                            </Badge>
                          ) : (
                            <Badge className="bg-white/5 text-[#8b909a] border border-white/10 text-[10px] px-2 py-0 h-4 font-mono">
                              User
                            </Badge>
                          )}
                        </div>

                        <div className="text-[11px] text-[#8b909a] font-mono flex items-center gap-2 flex-wrap">
                          <span className="truncate max-w-[180px] sm:max-w-xs">ID: {u.id}</span>
                          <span>•</span>
                          <span>Joined {new Date(u.created_at || Date.now()).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>

                    {/* Status Badges & Quick Action Controls */}
                    <div className="flex items-center gap-2 shrink-0 flex-wrap sm:flex-nowrap">
                      {isConfirmed ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#3ec98a]/10 border border-[#3ec98a]/20 text-[#3ec98a] text-[11px] font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Confirmed
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          disabled={actionLoadingId === `activate-${u.id}`}
                          onClick={() => handleActivateUser(u)}
                          className="h-8 px-3 rounded-full bg-[#ff5c47]/15 hover:bg-[#ff5c47]/25 text-[#ff5c47] border border-[#ff5c47]/30 text-xs font-medium gap-1.5 transition-all"
                        >
                          {actionLoadingId === `activate-${u.id}` ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Zap className="w-3.5 h-3.5" />
                          )}
                          ⚡ Activate Account
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={actionLoadingId === `reset-${u.id}`}
                        onClick={() => handleResetQuota(u)}
                        className="h-8 px-3 rounded-full border-white/10 bg-[#191b20] hover:bg-[#20232a] text-[#8b909a] hover:text-[#f0f2f5] text-xs font-medium gap-1.5 transition-all"
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

                  {/* Interactive Quota Slider & Meter Controls */}
                  <div className="p-3.5 sm:p-4 rounded-xl bg-[#181a20] border border-white/[0.05] space-y-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2 text-[#8b909a]">
                        <SlidersHorizontal className="w-3.5 h-3.5 text-[#ff5c47]" />
                        <span className="font-medium">Monthly Quota Cap:</span>
                        <span className="text-[#f0f2f5] font-bold font-mono text-xs sm:text-sm">
                          {currentSlider} mins
                        </span>
                        
                        {status === "saving" && (
                          <span className="text-[10px] text-[#ff5c47] font-medium animate-pulse ml-1">
                            Saving...
                          </span>
                        )}
                        {status === "saved" && (
                          <span className="text-[10px] text-[#3ec98a] font-medium ml-1">
                            ✓ Saved
                          </span>
                        )}
                      </div>

                      <div className="font-mono text-[11px] text-[#8b909a]">
                        Used: <span className="text-[#f0f2f5] font-semibold">{used.toFixed(1)}m</span> ({percent}%)
                      </div>
                    </div>

                    {/* Range Slider Container with Min/Max markers */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] text-[#8b909a] font-mono w-8">0m</span>
                        <input
                          type="range"
                          min="0"
                          max="5000"
                          step="50"
                          value={currentSlider}
                          onChange={(e) => handleSliderChange(u.id, Number(e.target.value))}
                          onMouseUp={() => handleSliderCommit(u.id, currentSlider)}
                          onTouchEnd={() => handleSliderCommit(u.id, currentSlider)}
                          className="flex-1 h-2 bg-[#23262d] rounded-lg appearance-none cursor-pointer accent-[#ff5c47]"
                        />
                        <span className="text-[10px] text-[#8b909a] font-mono w-12 text-right">5000m</span>
                      </div>
                    </div>

                    {/* Visual Progress Bar */}
                    <div className="w-full h-1.5 rounded-full bg-[#23262d] overflow-hidden">
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
