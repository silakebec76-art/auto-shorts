"""Découpe, recadrage vertical 9:16 qui suit la personne qui parle, et sous-titres animés."""
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import config

OUT_W, OUT_H = 1080, 1920


# ---------------------------------------------------------------- sous-titres

def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(word: str) -> str:
    return word.replace("\\", "").replace("{", "").replace("}", "").upper()


def _chunk_words(words: list[dict]) -> list[list[dict]]:
    """Regroupe les mots par petits blocs de 1 à 3 mots (style TikTok)."""
    chunks, cur = [], []
    for w in words:
        if cur:
            gap = w["start"] - cur[-1]["end"]
            length = sum(len(x["word"]) + 1 for x in cur) + len(w["word"])
            if len(cur) >= 3 or length > 18 or gap > 0.6 or cur[-1]["word"][-1:] in ".!?,;:":
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def build_ass(words: list[dict], clip_start: float, clip_end: float, out_path: Path) -> None:
    """Crée un fichier .ass : chaque mot s'allume en jaune quand il est prononcé."""
    font = config.SUBTITLE_FONT
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dur = clip_end - clip_start
    local = []
    for w in words:
        s, e = w["start"] - clip_start, w["end"] - clip_start
        if e <= 0 or s >= dur:
            continue
        local.append({"start": max(0.0, s), "end": min(dur, e), "word": w["word"]})

    lines = []
    chunks = _chunk_words(local)
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else dur
        chunk_end = min(next_start, chunk[-1]["end"] + 0.4)
        for wi, w in enumerate(chunk):
            ev_start = w["start"]
            ev_end = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
            if ev_end <= ev_start:
                continue
            parts = []
            for k, other in enumerate(chunk):
                txt = _clean(other["word"])
                if k == wi:
                    # mot actif : jaune, avec un petit effet de « pop »
                    parts.append(r"{\c&H0000E5FF&\fscx108\fscy108\t(0,90,\fscx118\fscy118)}" + txt + r"{\r}")
                else:
                    parts.append(txt)
            pop = r"{\fad(60,0)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ass_time(ev_start)},{_ass_time(ev_end)},Main,,0,0,0,,{pop}{' '.join(parts)}")
    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- recadrage

def _detect_faces_track(path: Path, crop_w: int, on_progress=None) -> tuple[np.ndarray, float, int, int]:
    """Analyse la vidéo et retourne, pour chaque image, le centre horizontal à suivre."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    step = max(1, round(fps / 6))  # ~6 analyses par seconde
    scale = 640.0 / max(w, 1) if w > 640 else 1.0

    samples, idx, last_x = {}, 0, None
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                small = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1.0 else frame
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                min_size = (max(20, int(small.shape[0] * 0.05)),) * 2
                faces = list(frontal.detectMultiScale(gray, 1.1, 5, minSize=min_size))
                if not faces:
                    faces = list(profile.detectMultiScale(gray, 1.15, 5, minSize=min_size))
                if faces:
                    def score(f):
                        fx, fy, fw, fh = f
                        cx = (fx + fw / 2) / scale
                        dist = abs(cx - last_x) / w if last_x is not None else 0
                        return fw * fh * (1.0 - 0.6 * dist)
                    fx, fy, fw, fh = max(faces, key=score)
                    last_x = (fx + fw / 2) / scale
                    samples[idx] = last_x
        idx += 1
        if on_progress and idx % 30 == 0:
            on_progress(0.5 * idx / total)
    cap.release()
    n = max(idx, 1)

    if not samples:
        return np.full(n, w / 2.0), fps, w, h

    keys = sorted(samples)
    xs = np.interp(np.arange(n), keys, [samples[k] for k in keys])

    # découpe en « plans » quand le visage suivi saute (changement de caméra)
    cuts = [0]
    for a, b in zip(keys, keys[1:]):
        if abs(samples[b] - samples[a]) > crop_w * 0.6:
            cuts.append(b)
    cuts.append(n)
    smooth = np.empty(n)
    win = max(1, int(fps * 0.8))
    for a, b in zip(cuts, cuts[1:]):
        seg = xs[a:b].copy()
        if len(seg) > win:
            kernel = np.ones(win) / win
            padded = np.pad(seg, (win // 2, win - 1 - win // 2), mode="edge")
            seg = np.convolve(padded, kernel, mode="valid")
        smooth[a:b] = seg
    # caméra calme : on ne bouge que si la cible s'éloigne vraiment
    out = np.empty(n)
    cut_set = set(cuts)
    cam = smooth[0]
    dead = crop_w * 0.08
    for i in range(n):
        if i in cut_set:
            cam = smooth[i]
        diff = smooth[i] - cam
        if abs(diff) > dead:
            cam += (diff - np.sign(diff) * dead) * 0.25
        out[i] = cam
    return out, fps, w, h


def render_clip(source: Path, job_dir: Path, index: int, start: float, end: float,
                words: list[dict], on_progress=None) -> Path:
    """Fabrique le short final clip_<index>.mp4 (1080x1920, sous-titres incrustés)."""
    ff = config.ffmpeg_path()
    raw = job_dir / f"raw_{index}.mp4"
    ass = job_dir / f"subs_{index}.ass"
    out = job_dir / f"clip_{index}.mp4"
    dur = end - start

    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(source),
                    "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                    "-c:a", "aac", "-b:a", "192k", str(raw)], check=True)
    build_ass(words, start, end, ass)

    cap = cv2.VideoCapture(str(raw))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    crop_w = int(h * 9 / 16) // 2 * 2

    # le filtre « ass » est lancé depuis le dossier du projet avec un nom relatif
    # (évite les soucis de chemins Windows du type C:\...)
    if crop_w >= w:
        # vidéo déjà verticale : on l'adapte simplement au format 1080x1920
        vf = (f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,"
              f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,ass={ass.name}")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", raw.name, "-vf", vf,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out.name],
                       check=True, cwd=job_dir)
    else:
        track, fps, w, h = _detect_faces_track(raw, crop_w, on_progress)
        cmd = [ff, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{crop_w}x{h}", "-r", f"{fps:.5f}", "-i", "-",
               "-i", raw.name, "-map", "0:v", "-map", "1:a?",
               "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1,ass={ass.name}",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out.name]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, cwd=job_dir)
        cap = cv2.VideoCapture(str(raw))
        i = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                cx = track[min(i, len(track) - 1)]
                x0 = int(round(cx - crop_w / 2))
                x0 = max(0, min(w - crop_w, x0))
                proc.stdin.write(np.ascontiguousarray(frame[:, x0:x0 + crop_w]).tobytes())
                i += 1
                if on_progress and i % 30 == 0:
                    on_progress(0.5 + 0.5 * i / len(track))
        finally:
            cap.release()
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="ignore")
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg a échoué : {err[-500:]}")
    raw.unlink(missing_ok=True)
    return out
