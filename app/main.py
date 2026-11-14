"""Serveur web local : http://localhost:8000"""
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, publish_tiktok, publish_youtube

app = FastAPI(title="Auto Shorts")
STATIC = config.ROOT / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def _startup():
    jobs.start_worker()


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC / "index.html")


# ------------------------------------------------------------------ état

@app.get("/api/status")
def status():
    return {
        "ai": bool(config.ANTHROPIC_API_KEY),
        "whisper_model": config.WHISPER_MODEL,
        "youtube": {"configured": publish_youtube.is_configured(), "connected": publish_youtube.is_connected()},
        "tiktok": {"configured": publish_tiktok.is_configured(), "connected": publish_tiktok.is_connected()},
    }


# ------------------------------------------------------------------ projets

class NewJob(BaseModel):
    url: str
    count: int = 8
    language: str | None = None


@app.post("/api/jobs")
def new_job(body: NewJob):
    url = body.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "Colle un lien qui commence par http")
    return jobs.create(url, body.count, body.language or None)


@app.post("/api/jobs/upload")
async def new_job_upload(file: UploadFile = File(...), count: int = Form(8), language: str = Form("")):
    tmp = Path(tempfile.mkdtemp()) / (Path(file.filename or "video.mp4").name)
    with open(tmp, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return jobs.create(None, count, language or None, local_file=tmp)


@app.get("/api/jobs")
def list_jobs():
    return jobs.list_jobs()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Projet introuvable")
    return job


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    jobs.delete(job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    if not jobs.get(job_id):
        raise HTTPException(404, "Projet introuvable")
    jobs.retry(job_id)
    return {"ok": True}


class ClipEdit(BaseModel):
    title: str
    description: str
    hashtags: list[str]


def _clip(job_id: str, index: int) -> tuple[dict, dict]:
    job = jobs.get(job_id)
    if not job or index >= len(job["clips"]):
        raise HTTPException(404, "Short introuvable")
    return job, job["clips"][index]


@app.put("/api/jobs/{job_id}/clips/{index}")
def edit_clip(job_id: str, index: int, body: ClipEdit):
    _clip(job_id, index)
    tags = [t.strip().lstrip("#").replace(" ", "") for t in body.hashtags if t.strip()]
    return jobs.update_clip(job_id, index, title=body.title.strip(), description=body.description.strip(),
                            hashtags=tags)


@app.get("/media/{job_id}/{name}")
def media(job_id: str, name: str):
    path = (config.JOBS_DIR / job_id / name).resolve()
    if config.JOBS_DIR.resolve() not in path.parents or not path.exists() or path.suffix != ".mp4":
        raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4")


# ------------------------------------------------------------------ publication

def _in_background(job_id: str, index: int, platform: str, fn):
    jobs.update_clip(job_id, index, **{platform: {"status": "uploading"}})

    def run():
        try:
            result = fn()
            jobs.update_clip(job_id, index, **{platform: {**result, "status": "done"}})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            jobs.update_clip(job_id, index, **{platform: {"status": "error", "error": str(e)}})

    threading.Thread(target=run, daemon=True).start()


class YoutubePost(BaseModel):
    privacy: str = "public"  # public | unlisted | private


@app.post("/api/jobs/{job_id}/clips/{index}/youtube")
def post_youtube(job_id: str, index: int, body: YoutubePost):
    job, clip = _clip(job_id, index)
    if not clip.get("file"):
        raise HTTPException(400, "Ce short n'est pas encore prêt")
    if not publish_youtube.is_connected():
        raise HTTPException(400, "Connecte d'abord ton compte YouTube")
    path = config.JOBS_DIR / job_id / clip["file"]
    tags_line = " ".join("#" + h for h in clip["hashtags"])
    desc = f"{clip['description']}\n\n{tags_line}".strip()
    _in_background(job_id, index, "youtube",
                   lambda: publish_youtube.upload(path, clip["title"], desc, clip["hashtags"], body.privacy))
    return {"ok": True}


class TiktokPost(BaseModel):
    privacy_level: str = "SELF_ONLY"


@app.post("/api/jobs/{job_id}/clips/{index}/tiktok")
def post_tiktok(job_id: str, index: int, body: TiktokPost):
    job, clip = _clip(job_id, index)
    if not clip.get("file"):
        raise HTTPException(400, "Ce short n'est pas encore prêt")
    if not publish_tiktok.is_connected():
        raise HTTPException(400, "Connecte d'abord ton compte TikTok")
    path = config.JOBS_DIR / job_id / clip["file"]
    caption = f"{clip['title']} {' '.join('#' + h for h in clip['hashtags'])}".strip()
    _in_background(job_id, index, "tiktok", lambda: publish_tiktok.upload(path, caption, body.privacy_level))
    return {"ok": True}


@app.get("/api/tiktok/creator")
def tiktok_creator():
    try:
        return publish_tiktok.creator_info()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))


@app.get("/api/youtube/channel")
def youtube_channel():
    try:
        return {"name": publish_youtube.channel_name()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ connexions OAuth

def _message_page(title: str, text: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>{title}</title>
<body style="font-family:system-ui;background:#0f0f14;color:#eee;display:grid;place-items:center;height:100vh">
<div style="text-align:center"><h2>{title}</h2><p>{text}</p><p><a style="color:#ff4d6d" href="/">Retour à l'application</a></p></div>""")


@app.get("/auth/youtube/start")
def youtube_start():
    if not publish_youtube.is_configured():
        return _message_page("YouTube pas encore configuré",
                             "Ajoute le fichier client_secret.json dans le dossier de l'application (voir le guide).")
    return RedirectResponse(publish_youtube.auth_url())


@app.get("/auth/youtube/callback")
def youtube_callback(request: Request, state: str = "", error: str = ""):
    if error:
        return _message_page("Connexion annulée", error)
    try:
        publish_youtube.handle_callback(str(request.url), state)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return _message_page("Erreur de connexion YouTube", str(e))
    return RedirectResponse("/?connected=youtube")


@app.get("/auth/tiktok/start")
def tiktok_start():
    if not publish_tiktok.is_configured():
        return _message_page("TikTok pas encore configuré",
                             "Ajoute TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET dans le fichier .env (voir le guide).")
    return RedirectResponse(publish_tiktok.auth_url())


@app.get("/auth/tiktok/callback/")
def tiktok_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error or not code:
        return _message_page("Connexion annulée", error_description or error or "Pas de code reçu")
    try:
        publish_tiktok.handle_callback(code, state)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        return _message_page("Erreur de connexion TikTok", str(e))
    return RedirectResponse("/?connected=tiktok")


@app.post("/auth/{platform}/disconnect")
def disconnect(platform: str):
    {"youtube": publish_youtube, "tiktok": publish_tiktok}[platform].disconnect()
    return {"ok": True}


def run():
    import uvicorn

    print("\n  Auto Shorts démarre… Ouvre http://localhost:%d dans ton navigateur.\n"
          "  (Pour arrêter : ferme cette fenêtre ou appuie sur Ctrl+C)\n" % config.PORT)
    threading.Timer(2.0, lambda: webbrowser.open(config.BASE_URL)).start()
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="warning")


if __name__ == "__main__":
    run()
