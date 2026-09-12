"""Upload résumable de vidéos vers YouTube (API Data v3), sans dépendance
google-api-python-client — juste des requêtes HTTP brutes via `requests`,
dans le même esprit que app/youtube_auth.py.
"""
from __future__ import annotations

import json
import os
from typing import Callable, Optional

import requests

from app.errors import YoutubeError

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 Mo


def upload_video(
    access_token: str,
    file_path: str,
    title: str,
    description: str,
    tags: list[str],
    publish_at_iso: Optional[str],
    category_id: str = "10",  # Musique
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """Upload une vidéo en résumable. Retourne l'ID de la vidéo YouTube créée."""
    status = {"privacyStatus": "private" if publish_at_iso else "public"}
    if publish_at_iso:
        status["publishAt"] = publish_at_iso

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": category_id,
        },
        "status": status,
    }

    file_size = os.path.getsize(file_path)

    try:
        init_resp = requests.post(
            UPLOAD_ENDPOINT,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(file_size),
            },
            data=json.dumps(metadata),
            timeout=30,
        )
        init_resp.raise_for_status()
    except requests.RequestException as exc:
        raise YoutubeError("Impossible de démarrer l'upload YouTube.", detail=str(exc)) from exc

    upload_url = init_resp.headers.get("Location")
    if not upload_url:
        raise YoutubeError("YouTube n'a pas renvoyé d'URL d'upload.", detail=init_resp.text)

    sent = 0
    with open(file_path, "rb") as f:
        while sent < file_size:
            chunk = f.read(CHUNK_SIZE)
            chunk_len = len(chunk)
            end = sent + chunk_len - 1
            try:
                resp = requests.put(
                    upload_url,
                    headers={
                        "Content-Length": str(chunk_len),
                        "Content-Range": f"bytes {sent}-{end}/{file_size}",
                    },
                    data=chunk,
                    timeout=120,
                )
            except requests.RequestException as exc:
                raise YoutubeError("Upload interrompu (réseau).", detail=str(exc)) from exc

            if resp.status_code in (200, 201):
                sent += chunk_len
                if progress_callback:
                    progress_callback(1.0)
                data = resp.json()
                video_id = data.get("id")
                if not video_id:
                    raise YoutubeError("Réponse YouTube invalide.", detail=resp.text)
                return video_id
            elif resp.status_code == 308:
                sent += chunk_len
                if progress_callback:
                    progress_callback(min(1.0, sent / file_size))
                continue
            else:
                raise YoutubeError(
                    f"Erreur YouTube ({resp.status_code}) pendant l'upload.",
                    detail=resp.text,
                )

    raise YoutubeError("Upload terminé sans confirmation de YouTube.")
