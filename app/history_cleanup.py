"""Nettoyage des exports déjà publiés sur YouTube.

Croise l'historique de génération (`history`) avec l'historique de
publication YouTube (`youtube_history`, clé "nomfichier|taille") : une
création dont le MP4 a été retrouvé côté YouTube est considérée comme
publiée. Sa vidéo et son audio source (copies propres au dossier du
projet) sont supprimés ; seule une trace texte + deux miniatures
compressées (vignette vidéo + pochette) sont conservées.
"""
from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)

THUMB_MAX_SIZE = (480, 270)
THUMB_QUALITY = 65


def _history_key(path: str) -> str:
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return f"{p.name}|{size}"


def _video_thumb_path(video_path: str) -> Path:
    return Path(str(video_path).replace(".mp4", "_thumb.jpg"))


def _path_shared(path: str, entry: dict, history: list[dict]) -> bool:
    """True si un autre historique non archivé pointe encore vers ce fichier
    (cas complet + short dérivés du même audio/pochette copiés une fois)."""
    for other in history:
        if other is entry or other.get("archived"):
            continue
        if other.get("audio") == path or other.get("image") == path:
            return True
    return False


def _is_candidate(entry: dict, youtube_history: dict) -> bool:
    if entry.get("archived"):
        return False
    video = entry.get("video")
    if not video or not Path(video).exists():
        return False
    return _history_key(video) in youtube_history


def find_cleanup_candidates(history: list[dict], youtube_history: dict) -> list[dict]:
    """Entrées déjà publiées sur YouTube et pas encore nettoyées."""
    return [h for h in history if _is_candidate(h, youtube_history)]


def _estimate_freed_bytes(entry: dict, history: list[dict]) -> int:
    total = 0
    video = entry.get("video")
    if video and Path(video).exists():
        total += Path(video).stat().st_size
    for field in ("audio", "image"):
        path = entry.get(field)
        if path and Path(path).exists() and not _path_shared(path, entry, history):
            total += Path(path).stat().st_size
    return total


def preview_cleanup(history: list[dict], youtube_history: dict) -> dict:
    """Aperçu sans rien modifier : nombre d'entrées concernées + espace estimé libéré."""
    candidates = find_cleanup_candidates(history, youtube_history)
    freed = sum(_estimate_freed_bytes(e, history) for e in candidates)
    return {"count": len(candidates), "freed_bytes": freed, "entries": candidates}


def _compress_image(src: Path, dest: Path) -> bool:
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        img.thumbnail(THUMB_MAX_SIZE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return True
    except Exception as exc:
        _log.debug("Compression miniature échouée pour %r: %s", src, exc)
        return False


def cleanup_published_exports(history: list[dict], youtube_history: dict) -> dict:
    """Nettoie en place les entrées de `history` déjà publiées sur YouTube.

    Pour chaque entrée concernée : supprime le MP4, supprime l'audio source
    sauf s'il est encore utilisé par une variante sœur (complet/short) non
    publiée, et conserve une vignette vidéo + une pochette compressées à la
    place. L'entrée reste dans l'historique avec `archived: True`.

    Retourne {"count": nb d'entrées nettoyées, "freed_bytes": espace libéré}.
    """
    candidates = find_cleanup_candidates(history, youtube_history)
    freed = 0
    cleaned = 0

    for entry in candidates:
        folder = Path(entry.get("folder") or Path(entry["video"]).parent)
        video_path = Path(entry["video"])
        thumb_src = _video_thumb_path(entry["video"])
        cover_src = Path(entry["image"]) if entry.get("image") else None
        audio_src = Path(entry["audio"]) if entry.get("audio") else None

        archive_thumb = folder / "_archive_thumb.jpg"
        archive_cover = folder / "_archive_cover.jpg"

        got_thumb = thumb_src.exists() and _compress_image(thumb_src, archive_thumb)
        got_cover = bool(cover_src) and cover_src.exists() and _compress_image(cover_src, archive_cover)

        if video_path.exists():
            freed += video_path.stat().st_size
            try:
                video_path.unlink()
            except OSError as exc:
                _log.debug("Suppression vidéo échouée pour %r: %s", video_path, exc)

        if thumb_src.exists():
            try:
                thumb_src.unlink()
            except OSError:
                pass

        audio_deleted = False
        if audio_src and audio_src.exists() and not _path_shared(str(audio_src), entry, history):
            freed += audio_src.stat().st_size
            try:
                audio_src.unlink()
                audio_deleted = True
            except OSError as exc:
                _log.debug("Suppression audio échouée pour %r: %s", audio_src, exc)

        cover_deleted = False
        if cover_src and cover_src.exists() and not _path_shared(str(cover_src), entry, history):
            freed += cover_src.stat().st_size
            try:
                cover_src.unlink()
                cover_deleted = True
            except OSError as exc:
                _log.debug("Suppression pochette échouée pour %r: %s", cover_src, exc)

        entry["archived"] = True
        entry["video"] = None
        if audio_deleted:
            entry["audio"] = None
        if cover_deleted:
            entry["image"] = None
        if got_thumb:
            entry["archive_thumb"] = str(archive_thumb)
        if got_cover:
            entry["archive_cover"] = str(archive_cover)

        cleaned += 1

    return {"count": cleaned, "freed_bytes": freed}
