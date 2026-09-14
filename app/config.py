"""Configuration persistante — AppData/DoktorP3st/TAC_MP4."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.errors import ConfigError


APP_DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "DoktorP3st" / "TAC_MP4"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = APP_DATA_DIR / "config.json"
DEFAULT_CREATIONS_DIR = APP_DATA_DIR / "Creations"
DEFAULT_CREATIONS_DIR.mkdir(parents=True, exist_ok=True)

# Caractères interdits dans les noms de fichiers Windows
_INVALID_CHARS = set('<>:"/\\|?*')


def safe_name(name: str) -> str:
    """Nettoie un nom de projet pour qu'il soit valide comme nom de dossier Windows."""
    cleaned = "".join(c for c in name.strip() if c not in _INVALID_CHARS)
    cleaned = " ".join(cleaned.split())
    return cleaned or "Projet sans nom"


def default_config() -> dict:
    return {
        "project_root": str(DEFAULT_CREATIONS_DIR),
        "history": [],
        "turbo_v2_history": {},
        "turbo_v2_last_folder": "",
        "user_presets": {},
        "hidden_builtin_presets": [],
        "youtube_oauth_client_id": "",
        "youtube_oauth_client_secret": "",
        "youtube_profiles": {},
        "youtube_history": {},
        "youtube_last_scheduled_date": "",
        "youtube_channels": {},
        "youtube_active_channel": "",
        "youtube_title_prefixes": [],
        "youtube_active_title_prefix": "",
        "youtube_title_suffixes": [],
        "youtube_active_title_suffix": "",
        "settings": {
            "global_preset": "Dark Premium",
            "particle_preset": "Premium",
            "smoke_preset": "Cinématique",
            "smoke_color": "Blanc",
            "spectrum_style": "Cercle radial",
            "spectrum_size": 1.05,
            "spectrum_y": 0.90,
            "image_zoom": 1.00,
            "pulse_strength": 1.10,
            "export_mode": "COMPLET",
            "preview_start": "0",
            "window_geometry": "1220x780+80+40",
            "text_x": 0.50,
            "text_y": 0.70,
            "title_text": "",
        },
    }


def load_config() -> dict:
    """Charge la config depuis le disque, en fusionnant avec les valeurs par défaut."""
    cfg = default_config()
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                # Fusionne les clés top-level sauf settings (traité séparément)
                cfg.update({k: v for k, v in loaded.items() if k != "settings"})
                # Fusionne settings en préservant les nouvelles clés par défaut
                cfg["settings"].update(loaded.get("settings", {}))
        except (json.JSONDecodeError, OSError) as exc:
            raise ConfigError(
                "La configuration est corrompue et a été réinitialisée.",
                detail=str(exc),
            ) from exc

    Path(cfg.get("project_root", DEFAULT_CREATIONS_DIR)).mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(cfg: dict) -> None:
    """Sauvegarde la config sur le disque (écriture atomique via fichier temporaire)."""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_PATH)  # Remplacement atomique — évite les configs corrompues
    except OSError as exc:
        raise ConfigError(
            "Impossible de sauvegarder la configuration.",
            detail=str(exc),
        ) from exc
