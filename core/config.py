import os
import mimetypes
from pathlib import Path
from dotenv import load_dotenv

# Base Project Root
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env", override=True)

# Directory configurations
INPUTS_DIR = Path(os.getenv("INPUTS_DIR", str(BASE_DIR / "inputs"))).resolve()
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(BASE_DIR / "outputs"))).resolve()

# Ensure inputs and outputs directories exist
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Default Gemini model
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

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
    """Retrieve Gemini API key from environment."""
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

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
