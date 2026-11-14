"""Choix des meilleurs moments + titres/descriptions/hashtags avec Claude."""
import json

from . import config

MIN_LEN, MAX_LEN = 15.0, 60.0

CLIP_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "début en secondes"},
                    "end": {"type": "number", "description": "fin en secondes"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string", "description": "pourquoi ce moment est fort"},
                    "score": {"type": "integer", "description": "potentiel viral de 1 à 100"},
                },
                "required": ["start", "end", "title", "description", "hashtags", "reason", "score"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

SYSTEM = """Tu es un monteur expert en vidéos courtes virales (TikTok, YouTube Shorts, Reels).
On te donne la transcription horodatée d'une longue vidéo. Ta mission : repérer les meilleurs
moments à transformer en shorts verticaux.

Un bon moment :
- dure entre 15 et 60 secondes (idéalement 25 à 45 s) ;
- commence par une accroche forte dès la première phrase (question, affirmation surprenante,
  émotion, conflit, chiffre choc) ;
- se comprend tout seul, sans avoir vu le reste de la vidéo ;
- se termine sur une phrase complète, idéalement une conclusion ou une chute ;
- ne chevauche pas les autres moments choisis.

Utilise exactement les horodatages de la transcription : commence au début d'une phrase et
termine à la fin d'une phrase.

Pour chaque moment, écris dans la langue de la vidéo :
- un titre accrocheur (moins de 70 caractères, sans hashtag) ;
- une courte description (1 à 3 phrases) qui donne envie de regarder ;
- 3 à 6 hashtags pertinents (sans le #, sans espace), dont au moins un populaire.
Classe les moments du plus fort au moins fort."""


def _format_transcript(transcript: dict) -> str:
    lines = []
    for seg in transcript["segments"]:
        lines.append(f"[{seg['start']:.1f} - {seg['end']:.1f}] {seg['text']}")
    return "\n".join(lines)


def _snap_to_words(clip: dict, transcript: dict) -> dict | None:
    """Recale début/fin sur des mots réels et force une durée entre 15 et 60 s."""
    words = [w for s in transcript["segments"] for w in s["words"]]
    if not words:
        return None
    duration = transcript.get("duration") or words[-1]["end"]
    start = max(0.0, float(clip["start"]))
    end = min(float(clip["end"]), duration)
    # premier mot qui commence après (ou presque) le début demandé
    starts = [w for w in words if w["start"] >= start - 0.3]
    if not starts:
        return None
    start = starts[0]["start"]
    if end - start > MAX_LEN:
        end = start + MAX_LEN
    if end - start < MIN_LEN:
        end = min(start + MIN_LEN, duration)
    # dernier mot qui finit avant la fin
    ends = [w for w in words if w["end"] <= end + 0.3 and w["end"] > start]
    if ends:
        end = ends[-1]["end"]
    if end - start < MIN_LEN - 1:
        return None
    clip = dict(clip)
    clip["start"] = round(max(0.0, start - 0.15), 2)
    clip["end"] = round(min(duration, end + 0.35), 2)
    clip["hashtags"] = [h.strip().lstrip("#").replace(" ", "") for h in clip.get("hashtags", []) if h.strip()]
    return clip


def _remove_overlaps(clips: list[dict]) -> list[dict]:
    kept = []
    for c in clips:
        if all(c["end"] <= k["start"] or c["start"] >= k["end"] for k in kept):
            kept.append(c)
    return kept


def pick_moments(transcript: dict, video_title: str, count: int) -> list[dict]:
    if not config.ANTHROPIC_API_KEY:
        return fallback_moments(transcript, video_title, count)

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    user = (
        f"Titre de la vidéo : {video_title}\n"
        f"Durée : {transcript.get('duration', 0):.0f} secondes\n"
        f"Nombre de moments souhaités : {count} (moins si la vidéo est trop courte "
        f"ou n'a pas assez de bons moments)\n\n"
        f"Transcription :\n{_format_transcript(transcript)}"
    )
    with client.beta.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=32000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": CLIP_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RuntimeError("L'IA a refusé d'analyser cette vidéo.")
    text = "".join(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    clips = [c for c in (_snap_to_words(c, transcript) for c in data["clips"]) if c]
    clips.sort(key=lambda c: -c.get("score", 0))
    return _remove_overlaps(clips)[:count]


def fallback_moments(transcript: dict, video_title: str, count: int) -> list[dict]:
    """Sans clé IA : découpe simple sur les passages où l'on parle le plus."""
    segs = transcript["segments"]
    candidates = []
    for i, s in enumerate(segs):
        start, j, n_words = s["start"], i, 0
        while j < len(segs) and segs[j]["end"] - start <= 45:
            n_words += len(segs[j]["words"])
            j += 1
        if j - 1 >= i and segs[j - 1]["end"] - start >= MIN_LEN:
            end = segs[j - 1]["end"]
            candidates.append({"start": start, "end": end, "density": n_words / (end - start),
                               "text": " ".join(x["text"] for x in segs[i:j])})
    candidates.sort(key=lambda c: -c["density"])
    clips = []
    for c in candidates:
        first = c["text"].split(".")[0][:70].strip()
        clip = {"start": c["start"], "end": c["end"], "title": first or video_title[:70],
                "description": c["text"][:200], "hashtags": ["shorts", "viral"],
                "reason": "Passage dense en paroles (mode sans IA)", "score": int(c["density"] * 20)}
        clip = _snap_to_words(clip, transcript)
        if clip:
            clips.append(clip)
    return _remove_overlaps(clips)[:count]
