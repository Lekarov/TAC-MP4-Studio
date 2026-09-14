"""Authentification YouTube — OAuth2 Google via Device Authorization Grant.

Même principe que le bot Discord (utils/youtube_oauth.py) : pas de serveur web
local requis, un code à valider sur google.com/device. Le refresh_token obtenu
ne périme jamais.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import requests

from app.config import APP_DATA_DIR
from app.errors import YoutubeError

DEVICE_CODE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT        = "https://oauth2.googleapis.com/token"
SCOPE                 = "https://www.googleapis.com/auth/youtube"

LEGACY_TOKEN_PATH = APP_DATA_DIR / "youtube_token.json"


def token_path(channel_id: str) -> Path:
    return APP_DATA_DIR / f"youtube_token_{channel_id or 'default'}.json"


def _load_token(channel_id: str) -> dict:
    import json
    path = token_path(channel_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_token(channel_id: str, data: dict) -> None:
    import json
    path = token_path(channel_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def has_refresh_token(channel_id: str) -> bool:
    return bool(_load_token(channel_id).get("refresh_token"))


def forget_token(channel_id: str) -> None:
    try:
        token_path(channel_id).unlink(missing_ok=True)
    except Exception:
        pass


def start_device_flow(client_id: str) -> dict:
    """Retourne {device_code, user_code, verification_url, interval, expires_in}."""
    if not client_id:
        raise YoutubeError("Identifiants OAuth Google manquants (client_id).")
    try:
        resp = requests.post(DEVICE_CODE_ENDPOINT, data={
            "client_id": client_id,
            "scope": SCOPE,
        }, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise YoutubeError("Impossible de démarrer l'autorisation Google.", detail=str(exc)) from exc


def poll_for_token(client_id: str, client_secret: str, device_code: str,
                    interval: int, expires_in: int, channel_id: str) -> tuple[bool, str]:
    """Poll bloquant — à appeler depuis un thread. Retourne (ok, message)."""
    deadline = time.time() + expires_in
    token = _load_token(channel_id)

    while time.time() < deadline:
        time.sleep(max(5, interval))
        try:
            resp = requests.post(TOKEN_ENDPOINT, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }, timeout=15)
        except requests.RequestException:
            continue

        if resp.status_code == 200:
            data = resp.json()
            if "refresh_token" in data:
                token["refresh_token"] = data["refresh_token"]
            token["access_token"] = data.get("access_token")
            token["expires_at"] = time.time() + data.get("expires_in", 3600)
            _save_token(channel_id, token)
            if not token.get("refresh_token"):
                return False, (
                    "Token reçu sans refresh_token (déjà autorisé précédemment). "
                    "Va sur myaccount.google.com/permissions, révoque l'accès à cette "
                    "application, puis relance l'autorisation."
                )
            return True, "Autorisation YouTube réussie."

        body = {}
        try:
            body = resp.json()
        except Exception:
            pass
        error = body.get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error in ("access_denied", "expired_token"):
            return False, f"Autorisation refusée ou expirée ({error})."
        return False, f"Erreur inattendue : {body or resp.text}"

    return False, "Délai dépassé — relance l'autorisation."


def get_access_token(client_id: str, client_secret: str, channel_id: str) -> Optional[str]:
    token = _load_token(channel_id)
    if not token.get("refresh_token"):
        return None
    if token.get("access_token") and token.get("expires_at", 0) - time.time() > 120:
        return token["access_token"]
    try:
        resp = requests.post(TOKEN_ENDPOINT, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        token["access_token"] = data["access_token"]
        token["expires_at"] = time.time() + data.get("expires_in", 3600)
        _save_token(channel_id, token)
        return token["access_token"]
    except requests.RequestException:
        return None
