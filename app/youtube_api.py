"""Lecture/édition de la bibliothèque YouTube (chaîne, playlists, vidéos)
via l'API Data v3 en HTTP brut — même esprit que youtube_upload.py.
"""
from __future__ import annotations

from typing import Optional

import requests

from app.errors import YoutubeAuthError, YoutubeError

API_BASE = "https://www.googleapis.com/youtube/v3"


def _get(access_token: str, path: str, params: dict) -> dict:
    try:
        resp = requests.get(
            f"{API_BASE}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        status = exc.response.status_code if exc.response is not None else 0
        if status in (401, 403):
            raise YoutubeAuthError(
                "Autorisation YouTube insuffisante ou expirée.", detail=detail) from exc
        raise YoutubeError(f"Erreur API YouTube ({path}).", detail=detail) from exc
    except requests.RequestException as exc:
        raise YoutubeError(f"Erreur réseau ({path}).", detail=str(exc)) from exc


def get_uploads_playlist_id(access_token: str) -> str:
    data = _get(access_token, "channels", {
        "part": "contentDetails",
        "mine": "true",
    })
    items = data.get("items", [])
    if not items:
        raise YoutubeError("Aucune chaîne trouvée pour ce compte.")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_playlists(access_token: str) -> list[dict]:
    """Retourne [{id, title, item_count}, ...]."""
    playlists = []
    page_token: Optional[str] = None
    while True:
        params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get(access_token, "playlists", params)
        for item in data.get("items", []):
            playlists.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "item_count": item.get("contentDetails", {}).get("itemCount", 0),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return playlists


def list_playlist_video_ids(access_token: str, playlist_id: str) -> list[str]:
    ids = []
    page_token: Optional[str] = None
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        data = _get(access_token, "playlistItems", params)
        for item in data.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return ids


def get_videos_details(access_token: str, video_ids: list[str]) -> list[dict]:
    """Retourne les métadonnées complètes (snippet+status) par lots de 50 IDs."""
    results = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = _get(access_token, "videos", {
            "part": "snippet,status",
            "id": ",".join(batch),
        })
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            status = item.get("status", {})
            thumbs = snippet.get("thumbnails", {})
            thumb_url = (thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            results.append({
                "id": item["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", "22"),
                "thumbnail_url": thumb_url,
                "privacy_status": status.get("privacyStatus", "private"),
                "publish_at": status.get("publishAt", ""),
            })
    return results


def update_video(
    access_token: str,
    video_id: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    privacy_status: str,
    publish_at_iso: Optional[str] = None,
) -> None:
    status: dict = {"privacyStatus": privacy_status}
    if privacy_status == "private" and publish_at_iso:
        status["publishAt"] = publish_at_iso

    body = {
        "id": video_id,
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": category_id,
        },
        "status": status,
    }
    try:
        resp = requests.put(
            f"{API_BASE}/videos",
            params={"part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=body,
            timeout=20,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        status = exc.response.status_code if exc.response is not None else 0
        if status in (401, 403):
            raise YoutubeAuthError(
                "Autorisation YouTube insuffisante ou expirée.", detail=detail) from exc
        raise YoutubeError("Impossible de mettre à jour la vidéo.", detail=detail) from exc
    except requests.RequestException as exc:
        raise YoutubeError("Erreur réseau pendant la mise à jour.", detail=str(exc)) from exc
