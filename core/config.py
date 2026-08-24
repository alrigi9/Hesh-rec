import os
import mimetypes
from pathlib import Path
import toml
from dotenv import load_dotenv

# Base Project Root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env", override=True)


def _clean_key(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s


def get_secret(key_name: str, default: str = "") -> str:
    """Universal fallback secret resolver across os.environ, st.secrets, .streamlit/secrets.toml, and .env."""
    # 1. Check os.environ
    val = _clean_key(os.environ.get(key_name))
    if val:
        return val

    # 2. Check streamlit secrets if available
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key_name in st.secrets:
            s_val = _clean_key(st.secrets[key_name])
            if s_val:
                os.environ[key_name] = s_val
                return s_val
    except Exception:
        pass

    # 3. Check .streamlit/secrets.toml directly
    try:
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
                if p.suffix == ".toml":
                    sec = toml.load(str(p))
                    if key_name in sec:
                        res = _clean_key(sec[key_name])
                        if res:
                            os.environ[key_name] = res
                            return res
                elif p.name == ".env" or p.suffix == ".env":
                    from dotenv import dotenv_values
                    env_vals = dotenv_values(str(p))
                    if key_name in env_vals:
                        res = _clean_key(env_vals[key_name])
                        if res:
                            os.environ[key_name] = res
                            return res
    except Exception:
        pass

    return default


# Directory configurations
INPUTS_DIR = Path(os.getenv("INPUTS_DIR", str(BASE_DIR / "inputs"))).resolve()
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(BASE_DIR / "outputs"))).resolve()

# Ensure inputs and outputs directories exist
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Default Gemini model
DEFAULT_MODEL = get_secret("GEMINI_MODEL", "gemini-2.5-flash")

# Supported media extensions
SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".mp4", ".aac", 
    ".flac", ".ogg", ".mov", ".mkv", ".webm", ".wma"
}

# Custom MIME type fallbacks for media
MIME_MAP = {
    ".mp3": "audio/mp3",
    ".wav": "audio/wav",
    ".m4a": "audio/m4a",
    ".mp4": "video/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".wma": "audio/x-ms-wma",
}

def get_api_key() -> str | None:
    """Retrieve Gemini API key from environment or secrets."""
    key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
    return key if key else None

def get_mime_type(file_path: Path | str) -> str:
    """Return appropriate MIME type for audio/video file."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext in MIME_MAP:
        return MIME_MAP[ext]
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"

def is_supported_media(file_path: Path | str) -> bool:
    """Check if file extension is among supported media formats."""
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS
