"""Réglages de l'application, lus depuis le fichier .env."""
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
TOKENS_DIR = DATA_DIR / "tokens"
for d in (DATA_DIR, JOBS_DIR, TOKENS_DIR):
    d.mkdir(parents=True, exist_ok=True)

PORT = int(os.getenv("PORT", "8000"))
BASE_URL = f"http://localhost:{PORT}"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5").strip()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small").strip()

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
TIKTOK_REDIRECT_URI = f"{BASE_URL}/auth/tiktok/callback/"

YOUTUBE_CLIENT_SECRET_FILE = ROOT / "client_secret.json"
YOUTUBE_REDIRECT_URI = f"{BASE_URL}/auth/youtube/callback"

SUBTITLE_FONT = os.getenv("SUBTITLE_FONT", "Arial").strip()


def ffmpeg_path() -> str:
    """ffmpeg installé sur l'ordinateur, sinon celui fourni par le paquet imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
