# -*- coding: utf-8 -*-
"""
FastAPI Backend for Hesh Rec
High-performance REST API supporting Next.js frontend with full Groq Whisper + Gemini cloud pipelines.
"""

import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import toml
from dotenv import load_dotenv

load_dotenv()

# Fallback: Load from .streamlit/secrets.toml if env vars are missing
secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
if os.path.exists(secrets_path):
    try:
        secrets = toml.load(secrets_path)
        for k, v in secrets.items():
            if isinstance(v, str) and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        print(f"Warning loading secrets.toml: {e}")

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
    save_session_record,
    delete_session_record,
    rename_session_record,
    update_session_action_items,
    chat_with_session,
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
        groq_k = get_secret("GROQ_API_KEY")
        if groq_k:
            os.environ["GROQ_API_KEY"] = groq_k
        gemini_k = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
        if gemini_k:
            os.environ["GEMINI_API_KEY"] = gemini_k

        result = process_meeting_file_cloud(
            audio_path=save_path,
            custom_title=custom_title,
            model_choice=DEFAULT_GEMINI_MODEL,
            user_id=user_id,
            template_type=template_type
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
