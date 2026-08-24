export interface UserProfile {
  id: string;
  email: string;
  role: "admin" | "user" | string;
  monthly_minutes_limit: number;
  minutes_used_this_month: number;
  minutes_remaining: number;
  percent_used: number;
  can_upload: boolean;
}

export interface AdminUserRecord {
  id: string;
  email: string;
  role: "admin" | "user" | string;
  monthly_minutes_limit: number;
  minutes_used_this_month: number;
  created_at: string;
}

export interface AdminDashboardStats {
  total_users: number;
  total_minutes_processed: number;
  average_usage_per_user: number;
  system_limit_per_user: number;
}
