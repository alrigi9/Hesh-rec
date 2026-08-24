-- Supabase Schema Migration: Multi-tenant Profiles, 300 Min Quota, and Admin Role
-- Execute this script in your Supabase SQL Editor (https://supabase.com/dashboard/project/bdgjsmwtxfacgqqhwtzw/sql)

-- 1. Create profiles table
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user')),
  monthly_minutes_limit DOUBLE PRECISION DEFAULT 300.0,
  minutes_used_this_month DOUBLE PRECISION DEFAULT 0.0,
  last_reset_date TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Enable Row Level Security (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 3. RLS Policies for profiles
DROP POLICY IF EXISTS "Users can view their own profile" ON public.profiles;
CREATE POLICY "Users can view their own profile"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "Users can update their own profile" ON public.profiles;
CREATE POLICY "Users can update their own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id);

DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
CREATE POLICY "Admins can view all profiles"
  ON public.profiles FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = auth.uid() AND role = 'admin'
    )
  );

DROP POLICY IF EXISTS "Admins can update all profiles" ON public.profiles;
CREATE POLICY "Admins can update all profiles"
  ON public.profiles FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = auth.uid() AND role = 'admin'
    )
  );

DROP POLICY IF EXISTS "Service role has full access to profiles" ON public.profiles;
CREATE POLICY "Service role has full access to profiles"
  ON public.profiles FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- 4. Create trigger to automatically insert new profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role, monthly_minutes_limit, minutes_used_this_month, created_at)
  VALUES (
    NEW.id,
    NEW.email,
    'user',
    300.0,
    0.0,
    NOW()
  )
  ON CONFLICT (id) DO UPDATE
  SET email = EXCLUDED.email;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 5. Update sessions / recordings table with user_id and duration_minutes
CREATE TABLE IF NOT EXISTS public.sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  title TEXT NOT NULL DEFAULT 'Untitled Meeting',
  duration TEXT,
  duration_minutes DOUBLE PRECISION DEFAULT 0.0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  summary TEXT,
  executive_summary TEXT,
  discussion_pillars JSONB DEFAULT '[]'::jsonb,
  action_items JSONB DEFAULT '[]'::jsonb,
  strategic_insights JSONB DEFAULT '{}'::jsonb,
  mindmap_markdown TEXT,
  transcript TEXT,
  transcript_segments JSONB DEFAULT '[]'::jsonb,
  is_public BOOLEAN DEFAULT TRUE
);

DO $$ 
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sessions' AND column_name = 'user_id') THEN
    ALTER TABLE public.sessions ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sessions' AND column_name = 'duration_minutes') THEN
    ALTER TABLE public.sessions ADD COLUMN duration_minutes DOUBLE PRECISION DEFAULT 0.0;
  END IF;
END $$;

-- 6. RLS Policies on sessions
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read their own or public sessions" ON public.sessions;
CREATE POLICY "Users can read their own or public sessions"
  ON public.sessions FOR SELECT
  USING (
    is_public = true 
    OR auth.uid() = user_id 
    OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
  );

DROP POLICY IF EXISTS "Users can insert their own sessions" ON public.sessions;
CREATE POLICY "Users can insert their own sessions"
  ON public.sessions FOR INSERT
  WITH CHECK (auth.uid() = user_id OR auth.uid() IS NULL);

DROP POLICY IF EXISTS "Users can update their own sessions" ON public.sessions;
CREATE POLICY "Users can update their own sessions"
  ON public.sessions FOR UPDATE
  USING (auth.uid() = user_id OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));

DROP POLICY IF EXISTS "Users can delete their own sessions" ON public.sessions;
CREATE POLICY "Users can delete their own sessions"
  ON public.sessions FOR DELETE
  USING (auth.uid() = user_id OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));

DROP POLICY IF EXISTS "Service role has full access to sessions" ON public.sessions;
CREATE POLICY "Service role has full access to sessions"
  ON public.sessions FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
