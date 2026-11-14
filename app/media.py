"""Téléchargement de la vidéo (yt-dlp) et transcription (Whisper)."""
import json
import subprocess
from pathlib import Path

from . import config

_whisper_model = None


def download(url: str, job_dir: Path, on_progress=None) -> dict:
    """Télécharge la vidéo en MP4 (1080p max). Retourne {path, title}."""
    import yt_dlp

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                on_progress(d.get("downloaded_bytes", 0) / total)

    opts = {
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(job_dir / "source.%(ext)s"),
        "ffmpeg_location": config.ffmpeg_path(),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    path = job_dir / "source.mp4"
    if not path.exists():
        # au cas où l'extension finale n'est pas .mp4
        candidates = sorted(job_dir.glob("source.*"))
        if not candidates:
            raise RuntimeError("Le téléchargement n'a produit aucun fichier.")
        path = candidates[0]
    return {"path": str(path), "title": info.get("title") or "Vidéo"}


def extract_audio(video: Path, out_wav: Path) -> None:
    cmd = [config.ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(video),
           "-vn", "-ac", "1", "-ar", "16000", str(out_wav)]
    subprocess.run(cmd, check=True)


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        # int8 = rapide sur un ordinateur sans carte graphique
        _whisper_model = WhisperModel(config.WHISPER_MODEL, device="auto", compute_type="int8")
    return _whisper_model


def transcribe(video: Path, job_dir: Path, language: str | None = None, on_progress=None) -> dict:
    """Transcrit avec horodatage mot par mot. Résultat sauvegardé dans transcript.json."""
    cache = job_dir / "transcript.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))

    wav = job_dir / "audio.wav"
    extract_audio(video, wav)
    model = _get_whisper()
    segments_iter, info = model.transcribe(
        str(wav),
        language=language or None,
        word_timestamps=True,
        vad_filter=True,
    )
    segments = []
    for seg in segments_iter:
        words = [
            {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
            for w in (seg.words or [])
            if w.word.strip()
        ]
        segments.append({"start": round(seg.start, 2), "end": round(seg.end, 2),
                         "text": seg.text.strip(), "words": words})
        if on_progress and info.duration:
            on_progress(min(seg.end / info.duration, 1.0))
    result = {"language": info.language, "duration": info.duration, "segments": segments}
    cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    wav.unlink(missing_ok=True)
    return result
