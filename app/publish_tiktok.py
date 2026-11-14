"""Publication sur TikTok avec l'API officielle « Content Posting API » (connexion OAuth)."""
import hashlib
import json
import math
import secrets
import time
import urllib.parse
from pathlib import Path

import requests

from . import config

TOKEN_FILE = config.TOKENS_DIR / "tiktok.json"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.publish"

_pending: dict[str, str] = {}  # state -> code_verifier


def is_configured() -> bool:
    return bool(config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET)


def is_connected() -> bool:
    return TOKEN_FILE.exists()


def auth_url() -> str:
    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(48)[:64]
    _pending[state] = verifier
    challenge = hashlib.sha256(verifier.encode()).hexdigest()  # TikTok demande l'encodage hexadécimal
    params = {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)


def _save(tok: dict) -> None:
    tok["obtained_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(tok), encoding="utf-8")


def handle_callback(code: str, state: str) -> None:
    verifier = _pending.pop(state, None)
    if verifier is None:
        raise RuntimeError("Connexion TikTok expirée, recommence depuis l'application.")
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": config.TIKTOK_CLIENT_KEY,
        "client_secret": config.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
        "code_verifier": verifier,
    }, timeout=30)
    tok = r.json()
    if "access_token" not in tok:
        raise RuntimeError(f"TikTok a refusé la connexion : {tok}")
    _save(tok)


def _access_token() -> str:
    if not TOKEN_FILE.exists():
        raise RuntimeError("TikTok n'est pas connecté.")
    tok = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    if time.time() > tok["obtained_at"] + tok.get("expires_in", 0) - 300:
        r = requests.post(f"{API}/oauth/token/", data={
            "client_key": config.TIKTOK_CLIENT_KEY,
            "client_secret": config.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
        }, timeout=30)
        new = r.json()
        if "access_token" not in new:
            TOKEN_FILE.unlink(missing_ok=True)
            raise RuntimeError("La connexion TikTok a expiré, reconnecte ton compte.")
        _save(new)
        tok = new
    return tok["access_token"]


def _post(path: str, body: dict) -> dict:
    r = requests.post(f"{API}{path}", json=body, timeout=60, headers={
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json; charset=UTF-8",
    })
    data = r.json()
    err = data.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok : {err.get('code')} – {err.get('message')}")
    return data.get("data", {})


def creator_info() -> dict:
    return _post("/post/publish/creator_info/query/", {})


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


def upload(video: Path, caption: str, privacy_level: str) -> dict:
    size = video.stat().st_size
    if size <= 64 * 1024 * 1024:
        chunk_size, count = size, 1
    else:
        chunk_size = 10 * 1024 * 1024
        count = size // chunk_size  # le dernier morceau contient le reste
    init = _post("/post/publish/video/init/", {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": count,
        },
    })
    upload_url, publish_id = init["upload_url"], init["publish_id"]
    with open(video, "rb") as f:
        for i in range(count):
            first = i * chunk_size
            last = size - 1 if i == count - 1 else first + chunk_size - 1
            f.seek(first)
            chunk = f.read(last - first + 1)
            r = requests.put(upload_url, data=chunk, timeout=300, headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {first}-{last}/{size}",
            })
            if r.status_code not in (200, 201, 206):
                raise RuntimeError(f"Envoi vers TikTok échoué (code {r.status_code}).")

    status = "PROCESSING_UPLOAD"
    for _ in range(40):
        time.sleep(3)
        st = _post("/post/publish/status/fetch/", {"publish_id": publish_id})
        status = st.get("status", status)
        if status == "PUBLISH_COMPLETE":
            break
        if status == "FAILED":
            raise RuntimeError(f"TikTok a refusé la vidéo : {st.get('fail_reason')}")
    return {"publish_id": publish_id, "tiktok_status": status}
