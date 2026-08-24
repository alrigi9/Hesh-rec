# -*- coding: utf-8 -*-
import os
import toml
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

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]:
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
    description="Speech Intelligence & SOC 2 Meeting Summary Engine",
    version="2.4.0"
)

# Enable CORS for Next.js dev & production clients
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8501",
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


@app.get("/api/health")
async def health_check():
    """Simple status check for backend liveness."""
    return {
        "status": "ok",
        "service": "hesh-rec-api",
        "version": "2.4.0",
        "default_model": DEFAULT_GEMINI_MODEL
    }


@app.post("/api/process-audio")
async def process_audio(
    file: UploadFile = File(...),
    template_type: str = Form("executive"),
    custom_title: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """
    Accepts audio file upload, runs Whisper transcription + Gemini SOC 2 intelligence extraction,
    and returns the structured JSON report.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Validate file extension
    suffix = Path(file.filename).suffix.lower()
    allowed = [".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".flac"]
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Allowed: {', '.join(allowed)}"
        )

    # Save to local inputs dir with unique timestamped stream
    clean_fname = Path(file.filename).name.replace(" ", "_")
    timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = INPUTS_DIR / f"upload_{timestamp_prefix}_{clean_fname}"

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer, length=1024 * 1024)

        ensure_secrets_loaded()

        # 1. Direct environment variable lookup
        groq_key = (os.environ.get("GROQ_API_KEY") or "").strip().strip('"').strip("'")
        gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")

        # 2. Direct .streamlit/secrets.toml fallback
        for s_dir in [BASE_DIR, Path.cwd(), Path.home()]:
            secrets_file = s_dir / ".streamlit" / "secrets.toml"
            if secrets_file.exists():
                try:
                    sec = toml.load(str(secrets_file))
                    if not groq_key and "GROQ_API_KEY" in sec:
                        groq_key = str(sec["GROQ_API_KEY"]).strip().strip('"').strip("'")
                        if groq_key:
                            os.environ["GROQ_API_KEY"] = groq_key
                    if not gemini_key and ("GEMINI_API_KEY" in sec or "GOOGLE_API_KEY" in sec):
                        gemini_key = str(sec.get("GEMINI_API_KEY") or sec.get("GOOGLE_API_KEY")).strip().strip('"').strip("'")
                        if gemini_key:
                            os.environ["GEMINI_API_KEY"] = gemini_key
                except Exception as e:
                    print(f"[!] Warning loading secrets.toml: {e}", flush=True)

        # 3. Universal get_secret fallback
        if not groq_key:
            groq_key = get_secret("GROQ_API_KEY")
        if not gemini_key:
            gemini_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")

        if groq_key:
            print(f"[+] Loaded GROQ_API_KEY: {groq_key[:6]}... (length {len(groq_key)})", flush=True)
        else:
            print("[!] GROQ_API_KEY is not configured.", flush=True)

        result = process_meeting_file_cloud(
            audio_path=save_path,
            custom_title=custom_title,
            model_choice=DEFAULT_GEMINI_MODEL,
            user_id=user_id,
            template_type=template_type,
            groq_api_key=groq_key or None,
            gemini_api_key=gemini_key or None
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)}"
        )
    finally:
        file.file.close()


@app.get("/api/sessions")
async def list_sessions(user_id: Optional[str] = None):
    """Retrieves all sessions from local/cloud storage."""
    try:
        sessions = fetch_all_sessions(user_id=user_id)
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
        import uuid
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
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
