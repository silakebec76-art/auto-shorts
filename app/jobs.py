"""File d'attente des traitements : chaque lien YouTube devient un « projet » avec ses shorts."""
import json
import queue
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import ai, config, media, video

_lock = threading.RLock()
_jobs: dict[str, dict] = {}
_queue: "queue.Queue[str]" = queue.Queue()


def _job_dir(job_id: str) -> Path:
    return config.JOBS_DIR / job_id


def _save(job: dict) -> None:
    with _lock:
        d = _job_dir(job["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(d / "job.json")


def load_all() -> None:
    for f in config.JOBS_DIR.glob("*/job.json"):
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if job["status"] not in ("done", "error"):
            job["status"], job["message"] = "error", "Interrompu (l'application a été fermée). Relance-le."
        for c in job.get("clips", []):
            for p in ("youtube", "tiktok"):
                if c.get(p, {}).get("status") == "uploading":
                    c[p] = {"status": "error", "error": "Interrompu"}
        _jobs[job["id"]] = job


def list_jobs() -> list[dict]:
    with _lock:
        return sorted((dict(j) for j in _jobs.values()), key=lambda j: -j["created_at"])


def get(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        return json.loads(json.dumps(j)) if j else None


def update(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs[job_id]
        job.update(fields)
        _save(job)


def update_clip(job_id: str, index: int, **fields) -> dict:
    with _lock:
        clip = _jobs[job_id]["clips"][index]
        clip.update(fields)
        _save(_jobs[job_id])
        return dict(clip)


def create(url: str | None, count: int, language: str | None, local_file: Path | None = None) -> dict:
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    job = {
        "id": job_id, "url": url, "title": local_file.name if local_file else url,
        "count": max(1, min(15, count)), "language": language or None,
        "status": "queued", "progress": 0.0, "message": "En attente…",
        "clips": [], "created_at": time.time(), "local": bool(local_file),
    }
    d = _job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    if local_file:
        shutil.move(str(local_file), d / "source.mp4")
    with _lock:
        _jobs[job_id] = job
        _save(job)
    _queue.put(job_id)
    return job


def retry(job_id: str) -> None:
    update(job_id, status="queued", message="En attente…", progress=0.0, clips=[])
    _queue.put(job_id)


def delete(job_id: str) -> None:
    with _lock:
        _jobs.pop(job_id, None)
    shutil.rmtree(_job_dir(job_id), ignore_errors=True)


def _run(job_id: str) -> None:
    job = get(job_id)
    if not job:
        return
    d = _job_dir(job_id)

    def step(status, message, base, span):
        def cb(p):
            update(job_id, status=status, message=message, progress=round(base + span * p, 3))
        cb(0)
        return cb

    # 1. téléchargement
    source = d / "source.mp4"
    if not source.exists():
        cb = step("downloading", "Téléchargement de la vidéo…", 0.0, 0.15)
        info = media.download(job["url"], d, cb)
        source = Path(info["path"])
        update(job_id, title=info["title"])

    # 2. transcription
    cb = step("transcribing", "Transcription de la voix (Whisper)… ça peut prendre quelques minutes", 0.15, 0.30)
    transcript = media.transcribe(source, d, job["language"], cb)
    if not any(s["words"] for s in transcript["segments"]):
        raise RuntimeError("Aucune parole détectée dans la vidéo.")

    # 3. choix des moments
    msg = "L'IA cherche les meilleurs moments…" if config.ANTHROPIC_API_KEY else \
        "Recherche des moments (mode simple, sans clé IA)…"
    step("analyzing", msg, 0.45, 0.05)
    moments = ai.pick_moments(transcript, get(job_id)["title"], job["count"])
    if not moments:
        raise RuntimeError("Aucun moment de 15 à 60 secondes n'a été trouvé.")
    clips = []
    for i, m in enumerate(moments):
        clips.append({**m, "index": i, "file": None, "youtube": {}, "tiktok": {}})
    update(job_id, clips=clips)

    # 4. fabrication des shorts
    words = [w for s in transcript["segments"] for w in s["words"]]
    n = len(clips)
    for i, c in enumerate(clips):
        cb = step("rendering", f"Montage du short {i + 1} sur {n} (recadrage + sous-titres)…",
                  0.5 + 0.5 * i / n, 0.5 / n)
        out = video.render_clip(source, d, i, c["start"], c["end"], words, cb)
        update_clip(job_id, i, file=out.name)

    update(job_id, status="done", progress=1.0, message=f"{n} shorts prêts !")


def _worker() -> None:
    while True:
        job_id = _queue.get()
        try:
            _run(job_id)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            update(job_id, status="error", message=f"Erreur : {e}")


def start_worker() -> None:
    load_all()
    threading.Thread(target=_worker, daemon=True).start()
