"""Publication sur YouTube Shorts avec l'API officielle YouTube Data v3 (connexion OAuth Google)."""
import os
from pathlib import Path

from . import config

# Autorise la connexion Google sur http://localhost (pas besoin de https en local)
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

TOKEN_FILE = config.TOKENS_DIR / "youtube.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

_pending = {}  # state -> Flow


def is_configured() -> bool:
    return config.YOUTUBE_CLIENT_SECRET_FILE.exists()


def is_connected() -> bool:
    return TOKEN_FILE.exists()


def auth_url() -> str:
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(str(config.YOUTUBE_CLIENT_SECRET_FILE), scopes=SCOPES,
                                         redirect_uri=config.YOUTUBE_REDIRECT_URI)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    _pending[state] = flow
    return url


def handle_callback(full_url: str, state: str) -> None:
    flow = _pending.pop(state, None)
    if flow is None:
        raise RuntimeError("Connexion YouTube expirée, recommence depuis l'application.")
    flow.fetch_token(authorization_response=full_url)
    TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        raise RuntimeError("YouTube n'est pas connecté.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception:
            TOKEN_FILE.unlink(missing_ok=True)
            raise RuntimeError("La connexion YouTube a expiré, reconnecte ton compte.")
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_name() -> str:
    res = _service().channels().list(part="snippet", mine=True).execute()
    items = res.get("items", [])
    return items[0]["snippet"]["title"] if items else "(chaîne inconnue)"


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


def upload(video: Path, title: str, description: str, tags: list[str], privacy: str) -> dict:
    from googleapiclient.http import MediaFileUpload

    if "#shorts" not in (title + description).lower():
        description = (description + "\n\n#Shorts").strip()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = _service().videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = req.next_chunk()
    vid = response["id"]
    return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}
