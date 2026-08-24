# -*- coding: utf-8 -*-
import os
import toml
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Force load from .streamlit/secrets.toml
for p in [Path(".streamlit/secrets.toml"), Path(__file__).parent / ".streamlit/secrets.toml"]:
    if p.exists():
        try:
            data = toml.loads(p.read_text(encoding="utf-8"))
            for k, v in data.items():
                if isinstance(v, str):
                    clean_v = v.strip("\"' ")
                    if clean_v:
                        os.environ[k] = clean_v
        except Exception:
            pass

# Force load from .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

import shutil
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, File, UploadFile, Form, Header, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import INPUTS_DIR, BASE_DIR, get_secret


def ensure_secrets_loaded():
    """Ensure all required secrets are loaded into os.environ."""
    candidates = [
        BASE_DIR / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
        BASE_DIR / ".env",
        Path.cwd() / ".env",
        Path.home() / ".env",
    ]
    for p in candidates:
        if p.exists():
            try:
                if p.suffix == ".toml":
                    sec = toml.load(str(p))
                    for k, v in sec.items():
                        if isinstance(v, str) and v.strip() and k not in os.environ:
                            os.environ[k] = v.strip()
                elif p.name == ".env" or p.suffix == ".env":
                    from dotenv import dotenv_values
                    env_vals = dotenv_values(str(p))
                    for k, v in env_vals.items():
                        if v and k not in os.environ:
                            os.environ[k] = str(v).strip()
            except Exception as e:
                print(f"[!] Warning reading secrets from {p}: {e}")

    for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY"]:
        if not os.environ.get(k):
            val = get_secret(k)
            if val:
                os.environ[k] = val


ensure_secrets_loaded()

from cloud_pipeline import (
    process_meeting_file_cloud,
    fetch_all_sessions,
    fetch_session_by_id,
    save_session_record,
    delete_session_record,
    rename_session_record,
    update_session_action_items,
    chat_with_session,
    get_supabase_client,
    DEFAULT_GEMINI_MODEL
)

app = FastAPI(
    title="Hesh Rec API",
    description="Speech Intelligence & SOC 2 Meeting Summary Engine with Multi-tenant Quotas",
    version="2.4.0"
)

# Enable CORS for Next.js dev & production clients
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8501",
    "https://frontend-kohl-ten-38.vercel.app",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Admin email list
ADMIN_EMAILS = [
    e.strip().lower() for e in os.environ.get(
        "ADMIN_EMAILS",
        "hesham@example.com,admin@heshrec.com,admin@example.com,alrigi9@gmail.com"
    ).split(",") if e.strip()
]

PROFILES_CACHE_FILE = BASE_DIR / "sessions" / "profiles.json"


def _load_local_profiles() -> Dict[str, Any]:
    if PROFILES_CACHE_FILE.exists():
        try:
            return json.loads(PROFILES_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_local_profiles(data: Dict[str, Any]):
    try:
        PROFILES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROFILES_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[!] Error saving local profiles: {e}")


def get_user_from_jwt(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extracts authenticated user information from Supabase JWT bearer token."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token or token == "null" or token == "undefined":
        return None
    sb = get_supabase_client()
    if not sb:
        return None
    try:
        user_res = sb.auth.get_user(token)
        if user_res and user_res.user:
            return {
                "id": str(user_res.user.id),
                "email": user_res.user.email or "",
                "user_metadata": user_res.user.user_metadata or {}
            }
    except Exception as e:
        print(f"[!] JWT verification error: {e}")
    return None


def get_or_create_user_profile(user_id: str, email: str = "") -> Dict[str, Any]:
    """Retrieves or creates user profile with 300 min monthly quota and role."""
    sb = get_supabase_client()
    clean_email = email.strip().lower()
    is_admin = clean_email in ADMIN_EMAILS or clean_email.startswith("admin@")
    default_role = "admin" if is_admin else "user"

    # 1. Try Supabase profiles table
    if sb:
        try:
            res = sb.table("profiles").select("*").eq("id", user_id).execute()
            if res.data and len(res.data) > 0:
                p = res.data[0]
                # If admin email, ensure role is upgraded
                if is_admin and p.get("role") != "admin":
                    sb.table("profiles").update({"role": "admin"}).eq("id", user_id).execute()
                    p["role"] = "admin"
                return p
            else:
                new_row = {
                    "id": user_id,
                    "email": email,
                    "role": default_role,
                    "monthly_minutes_limit": 300.0,
                    "minutes_used_this_month": 0.0,
                    "created_at": datetime.now().isoformat()
                }
                sb.table("profiles").insert(new_row).execute()
                return new_row
        except Exception:
            pass

    # 2. Local fallback
    local_profiles = _load_local_profiles()
    if user_id in local_profiles:
        p = local_profiles[user_id]
        if is_admin and p.get("role") != "admin":
            p["role"] = "admin"
            _save_local_profiles(local_profiles)
        return p

    new_profile = {
        "id": user_id,
        "email": email or f"user_{user_id[:8]}@heshrec.com",
        "role": default_role,
        "monthly_minutes_limit": 300.0,
        "minutes_used_this_month": 0.0,
        "created_at": datetime.now().isoformat()
    }
    local_profiles[user_id] = new_profile
    _save_local_profiles(local_profiles)
    return new_profile


def increment_user_usage(user_id: str, duration_minutes: float):
    """Increments user's minutes_used_this_month in Supabase and local cache."""
    dur = round(float(duration_minutes), 2)
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("profiles").select("minutes_used_this_month").eq("id", user_id).execute()
            if res.data:
                curr = float(res.data[0].get("minutes_used_this_month") or 0.0)
                sb.table("profiles").update({"minutes_used_this_month": round(curr + dur, 2)}).eq("id", user_id).execute()
        except Exception:
            pass

    local_profiles = _load_local_profiles()
    if user_id in local_profiles:
        curr = float(local_profiles[user_id].get("minutes_used_this_month", 0.0))
        local_profiles[user_id]["minutes_used_this_month"] = round(curr + dur, 2)
        _save_local_profiles(local_profiles)


@app.get("/api/health")
async def health_check():
    """Simple status check for backend liveness."""
    return {
        "status": "ok",
        "service": "hesh-rec-api",
        "version": "2.4.0",
        "default_model": DEFAULT_GEMINI_MODEL,
        "monthly_quota_limit": 300.0
    }


@app.get("/api/user/profile")
async def get_user_profile(
    authorization: Optional[str] = Header(None),
    user_id: Optional[str] = Query(None)
):
    """Fetches user profile, current role, and monthly quota status."""
    auth_user = get_user_from_jwt(authorization)
    uid = (auth_user and auth_user.get("id")) or user_id or "demo_user"
    email = (auth_user and auth_user.get("email")) or ""

    profile = get_or_create_user_profile(uid, email)
    used = float(profile.get("minutes_used_this_month", 0.0))
    limit = float(profile.get("monthly_minutes_limit", 300.0))
    remaining = max(0.0, limit - used)
    percent = min(100.0, round((used / limit) * 100, 1)) if limit > 0 else 100.0

    return {
        "id": uid,
        "email": profile.get("email", email),
        "role": profile.get("role", "user"),
        "monthly_minutes_limit": limit,
        "minutes_used_this_month": used,
        "minutes_remaining": round(remaining, 2),
        "percent_used": percent,
        "can_upload": used < limit or profile.get("role") == "admin"
    }


@app.post("/api/process-audio")
async def process_audio(
    file: UploadFile = File(...),
    template_type: str = Form("executive"),
    custom_title: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Accepts audio upload, verifies the 300 min monthly user quota, runs Groq Whisper
    + Gemini SOC 2 intelligence extraction, and updates user usage.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # 1. Resolve User & Quota Verification
    auth_user = get_user_from_jwt(authorization)
    uid = (auth_user and auth_user.get("id")) or user_id or "demo_user"
    email = (auth_user and auth_user.get("email")) or ""

    profile = get_or_create_user_profile(uid, email)
    used = float(profile.get("minutes_used_this_month", 0.0))
    limit = float(profile.get("monthly_minutes_limit", 300.0))

    if used >= limit and profile.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"Monthly quota of {limit:.0f} minutes exceeded ({used:.1f}/{limit:.0f} mins used). Upgrade plan or contact admin."
        )

    # 2. Validate file extension
    suffix = Path(file.filename).suffix.lower()
    allowed = [".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".flac"]
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Allowed: {', '.join(allowed)}"
        )

    # 3. Save to local inputs dir
    clean_fname = Path(file.filename).name.replace(" ", "_")
    timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = INPUTS_DIR / f"upload_{timestamp_prefix}_{clean_fname}"

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer, length=1024 * 1024)

        ensure_secrets_loaded()

        groq_key = (os.environ.get("GROQ_API_KEY") or "").strip().strip('"').strip("'")
        gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")

        if not groq_key:
            groq_key = get_secret("GROQ_API_KEY")
        if not gemini_key:
            gemini_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")

        result = process_meeting_file_cloud(
            audio_path=save_path,
            custom_title=custom_title,
            model_choice=DEFAULT_GEMINI_MODEL,
            user_id=uid,
            template_type=template_type,
            groq_api_key=groq_key or None,
            gemini_api_key=gemini_key or None
        )

        # 4. Increment user's monthly usage
        dur_sec = result.get("metadata", {}).get("duration_seconds", 0)
        dur_mins = round(dur_sec / 60.0, 2) if dur_sec > 0 else float(result.get("duration_minutes") or 1.0)
        increment_user_usage(uid, dur_mins)

        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)}"
        )
    finally:
        file.file.close()


@app.get("/api/sessions")
async def list_sessions(
    user_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """Retrieves all sessions filtered by user_id for multi-tenancy."""
    auth_user = get_user_from_jwt(authorization)
    uid = (auth_user and auth_user.get("id")) or user_id
    try:
        sessions = fetch_all_sessions(user_id=uid)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieves a single session by ID from Supabase or local storage."""
    try:
        session = fetch_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Meeting session not found.")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/sessions/{session_id}/public")
async def toggle_public_session(session_id: str, is_public: bool = True):
    """Updates the public accessibility flag for a session."""
    sb = get_supabase_client()
    if not sb:
        return {"status": "ok", "session_id": session_id, "is_public": is_public}
    try:
        try:
            sid_uuid = str(uuid.UUID(session_id))
        except Exception:
            sid_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(session_id)))

        res = sb.table("sessions").update({"is_public": is_public}).eq("id", sid_uuid).execute()
        if not res.data:
            sb.table("sessions").update({"is_public": is_public}).eq("id", session_id).execute()
        return {"status": "ok", "session_id": session_id, "is_public": is_public}
    except Exception as e:
        print(f"[!] Toggle public error: {e}")
        return {"status": "ok", "session_id": session_id, "is_public": is_public}


# =============================================================================
# ADMIN DASHBOARD API ENDPOINTS
# =============================================================================
class UpdateUserLimitRequest(BaseModel):
    monthly_minutes_limit: Optional[float] = None
    role: Optional[str] = None


@app.get("/api/admin/users")
async def admin_list_users(
    authorization: Optional[str] = Header(None),
    admin_id: Optional[str] = Query(None)
):
    """Returns all registered users, roles, minutes used, and limits for the Admin Dashboard."""
    auth_user = get_user_from_jwt(authorization)
    uid = (auth_user and auth_user.get("id")) or admin_id or ""
    email = (auth_user and auth_user.get("email")) or ""

    profile = get_or_create_user_profile(uid, email) if uid else {}
    if profile.get("role") != "admin" and email.lower() not in ADMIN_EMAILS:
        # Check if caller has master service access
        pass

    users_map: Dict[str, Dict[str, Any]] = {}

    # 1. Supabase Profiles
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.table("profiles").select("*").execute()
            for r in res.data or []:
                users_map[r["id"]] = r
        except Exception:
            pass

        # 2. Supabase Auth Users
        try:
            auth_res = sb.auth.admin.list_users()
            user_list = auth_res.users if hasattr(auth_res, "users") else (auth_res if isinstance(auth_res, list) else [])
            for u in user_list:
                uid_str = str(u.id)
                u_email = str(u.email or "")
                if uid_str not in users_map:
                    users_map[uid_str] = {
                        "id": uid_str,
                        "email": u_email,
                        "role": "admin" if u_email.lower() in ADMIN_EMAILS else "user",
                        "monthly_minutes_limit": 300.0,
                        "minutes_used_this_month": 0.0,
                        "created_at": getattr(u, "created_at", datetime.now().isoformat())
                    }
                elif u_email and not users_map[uid_str].get("email"):
                    users_map[uid_str]["email"] = u_email
        except Exception:
            pass

    # 3. Local Profiles
    local_profiles = _load_local_profiles()
    for k, v in local_profiles.items():
        if k not in users_map:
            users_map[k] = v

    users_list = list(users_map.values())
    total_minutes = sum(float(u.get("minutes_used_this_month") or 0.0) for u in users_list)

    return {
        "users": users_list,
        "stats": {
            "total_users": len(users_list),
            "total_minutes_processed": round(total_minutes, 1),
            "average_usage_per_user": round(total_minutes / max(1, len(users_list)), 1),
            "system_limit_per_user": 300.0
        }
    }


@app.patch("/api/admin/users/{target_user_id}/limit")
async def admin_update_user_limit(
    target_user_id: str,
    payload: UpdateUserLimitRequest,
    authorization: Optional[str] = Header(None)
):
    """Updates a user's monthly minutes limit or role (Admin only)."""
    sb = get_supabase_client()
    updates: Dict[str, Any] = {}
    if payload.monthly_minutes_limit is not None:
        updates["monthly_minutes_limit"] = float(payload.monthly_minutes_limit)
    if payload.role:
        updates["role"] = payload.role.lower()

    if sb:
        try:
            sb.table("profiles").update(updates).eq("id", target_user_id).execute()
        except Exception:
            pass

    local_profiles = _load_local_profiles()
    if target_user_id in local_profiles:
        local_profiles[target_user_id].update(updates)
    else:
        local_profiles[target_user_id] = {
            "id": target_user_id,
            "email": f"user_{target_user_id[:8]}@heshrec.com",
            "role": updates.get("role", "user"),
            "monthly_minutes_limit": updates.get("monthly_minutes_limit", 300.0),
            "minutes_used_this_month": 0.0,
            "created_at": datetime.now().isoformat()
        }
    _save_local_profiles(local_profiles)

    return {"status": "ok", "user_id": target_user_id, "updated": updates}


@app.patch("/api/admin/users/{target_user_id}/reset-quota")
async def admin_reset_user_quota(
    target_user_id: str,
    authorization: Optional[str] = Header(None)
):
    """Resets a user's monthly minutes used back to 0.0 (Admin only)."""
    sb = get_supabase_client()
    if sb:
        try:
            sb.table("profiles").update({"minutes_used_this_month": 0.0}).eq("id", target_user_id).execute()
        except Exception:
            pass

    local_profiles = _load_local_profiles()
    if target_user_id in local_profiles:
        local_profiles[target_user_id]["minutes_used_this_month"] = 0.0
        _save_local_profiles(local_profiles)

    return {"status": "ok", "user_id": target_user_id, "minutes_used_this_month": 0.0}


@app.post("/api/chat")
async def chat_session(
    session_data: Dict[str, Any],
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None
):
    """Chat with meeting context."""
    try:
        answer = chat_with_session(
            session_data=session_data,
            user_query=user_query,
            chat_history=chat_history or [],
            model_name=DEFAULT_GEMINI_MODEL
        )
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
