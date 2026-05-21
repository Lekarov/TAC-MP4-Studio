"""Écran de chargement animé pendant l'export — TAC MP4 Studio.

Rendu : fond noir, texte bruité avec effet pixel/glitch,
lignes de scan, particules lumineuses, barre de progression.
Tout en numpy + cv2, aucun chargement fichier, < 2ms/frame.
"""
from __future__ import annotations

import math
import random

import cv2
import numpy as np

from app.logger import get_logger

_log = get_logger("loading")

# ── Constantes ────────────────────────────────────────────────────────────────
LINES = [
    "The Auralia Criya",
    "DoktorP3st",
    "TAC MP4 Studio",
    "2026",
]

# Palettes de couleurs pour les lignes
LINE_COLORS = [
    (180, 120, 255),   # violet — The Auralia Criya
    (100, 200, 255),   # cyan   — DoktorP3st
    (255, 255, 255),   # blanc  — TAC MP4 Studio
    (255, 180, 60),    # or     — 2026
]


def _draw_text_cv2(
    frame: np.ndarray,
    text: str,
    cx: int, cy: int,
    scale: float,
    color: tuple[int, int, int],
    thickness: int = 2,
    alpha: float = 1.0,
    jitter: int = 0,
) -> None:
    """Dessine du texte centré avec jitter optionnel."""
    font = cv2.FONT_HERSHEY_DUPLEX
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x = cx - tw // 2 + random.randint(-jitter, jitter)
    y = cy + th // 2 + random.randint(-jitter, jitter)
    c = tuple(int(v * alpha) for v in color)
    # Ombre
    shadow = tuple(int(v * alpha * 0.25) for v in color)
    cv2.putText(frame, text, (x + 3, y + 3), font, scale, shadow, thickness + 1, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), font, scale, c, thickness, cv2.LINE_AA)


def render_loading_frame(
    width: int,
    height: int,
    t: float,
    progress: float = 0.0,
    export_label: str = "Export en cours...",
) -> np.ndarray:  # type: ignore[return]
    """Génère un frame d'écran de chargement.

    Args:
        width, height : dimensions de sortie
        t             : temps en secondes (float croissant)
        progress      : 0.0 → 1.0 (avancement de l'export)
        export_label  : texte de statut affiché en bas
    """
    try:
        if width <= 0 or height <= 0:
            _log.warning("render_loading_frame called with invalid dimensions %dx%d", width, height)
            return np.zeros((max(1, height), max(1, width), 3), dtype=np.uint8)
    except Exception:
        return np.zeros((480, 640, 3), dtype=np.uint8)

    rng = random.Random(int(t * 30))   # seed par frame pour cohérence

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cx, cy = width // 2, height // 2
    scale = width / 1920.0

    # ── Fond : vignette sombre ────────────────────────────────────────────────
    y_idx, x_idx = np.ogrid[:height, :width]
    dist = np.sqrt(((x_idx - cx) / width) ** 2 + ((y_idx - cy) / height) ** 2)
    vignette = np.clip(1.0 - dist * 1.8, 0.0, 1.0)

    # Légère teinte violette au centre
    vig_r = (vignette * 12).astype(np.uint8)
    vig_b = (vignette * 22).astype(np.uint8)
    frame[:, :, 0] = vig_b
    frame[:, :, 2] = vig_r

    # ── Lignes de scan horizontales ───────────────────────────────────────────
    scan_speed = t * 180 * scale
    for i in range(8):
        sy = int((scan_speed + i * height / 8) % height)
        alpha_scan = 0.04 + 0.03 * math.sin(t * 2.5 + i)
        frame[sy:sy + 1, :] = np.clip(
            frame[sy:sy + 1, :].astype(np.float32) + alpha_scan * 60, 0, 255
        ).astype(np.uint8)

    # ── Particules flottantes ─────────────────────────────────────────────────
    n_particles = int(60 * scale)
    rng2 = random.Random(42)   # seed fixe pour positions de base
    for _ in range(n_particles):
        bx = rng2.uniform(0, width)
        by = rng2.uniform(0, height)
        spd = rng2.uniform(0.3, 1.2)
        phase = rng2.uniform(0, math.tau)
        # Dérive lente
        px = int((bx + math.sin(t * spd + phase) * 30) % width)
        py = int((by - t * spd * 15) % height)
        br = int(rng2.uniform(60, 160))
        r_col = int(br * 0.7)
        b_col = int(br * 1.2)
        cv2.circle(frame, (px, py), max(1, int(scale * 1.5)),
                   (min(255, b_col), 0, min(255, r_col)), -1, cv2.LINE_AA)

    # ── Grille pixel légère ───────────────────────────────────────────────────
    grid_size = int(max(20, 40 * scale))
    for gx in range(0, width, grid_size):
        frame[:, gx] = np.clip(frame[:, gx].astype(np.int16) + 8, 0, 255).astype(np.uint8)
    for gy in range(0, height, grid_size):
        frame[gy, :] = np.clip(frame[gy, :].astype(np.int16) + 8, 0, 255).astype(np.uint8)

    # ── Textes principaux ─────────────────────────────────────────────────────
    n_lines = len(LINES)
    line_h = int(height * 0.11)
    total_h = line_h * n_lines
    start_y = cy - total_h // 2

    for idx, (text, color) in enumerate(zip(LINES, LINE_COLORS)):
        # Phase d'entrée : chaque ligne arrive avec un délai
        entry_t = max(0.0, t - idx * 0.25)
        if entry_t <= 0:
            continue
        entry_alpha = min(1.0, entry_t * 2.5)

        # Pulsation douce
        pulse = 0.92 + 0.08 * math.sin(t * 1.8 + idx * 1.1)

        # Taille de police selon le rang
        if idx == 0:   fs = 1.6 * scale
        elif idx == 1: fs = 1.2 * scale
        elif idx == 2: fs = 0.8 * scale
        else:          fs = 1.0 * scale

        fs *= pulse

        # Glitch : jitter aléatoire déclenché ponctuellement
        glitch = 0
        if rng.random() < 0.06:
            glitch = rng.randint(1, 5)

        line_cy = start_y + idx * line_h + line_h // 2

        # Lueur derrière le texte
        glow_layer = np.zeros_like(frame)
        _draw_text_cv2(glow_layer, text, cx, line_cy,
                       fs * 1.05, color, thickness=8, alpha=entry_alpha * 0.3)
        glow_layer = cv2.GaussianBlur(glow_layer, (31, 31), 0)
        cv2.addWeighted(glow_layer, 1.0, frame, 1.0, 0, frame)

        # Texte principal
        _draw_text_cv2(frame, text, cx, line_cy,
                       fs, color, thickness=max(1, int(2 * scale)),
                       alpha=entry_alpha, jitter=glitch)

        # Ligne décorative sous The Auralia Criya
        if idx == 0 and entry_alpha > 0.5:
            lw = int(200 * scale * entry_alpha)
            ly = line_cy + int(line_h * 0.38)
            lthick = max(1, int(scale))
            cv2.line(frame, (cx - lw, ly), (cx + lw, ly),
                     tuple(int(v * 0.45 * entry_alpha) for v in color),
                     lthick, cv2.LINE_AA)

    # ── Barre de progression ──────────────────────────────────────────────────
    bar_y = int(height * 0.86)
    bar_w = int(width * 0.55)
    bar_h = max(3, int(8 * scale))
    bx1 = cx - bar_w // 2
    bx2 = cx + bar_w // 2
    br_corner = bar_h // 2

    # Track
    cv2.rectangle(frame, (bx1, bar_y), (bx2, bar_y + bar_h), (40, 40, 40), -1)

    # Fill
    fill_w = int(bar_w * min(1.0, progress))
    if fill_w > 0:
        # Dégradé violet→cyan sur le fill
        fill_frame = np.zeros_like(frame)
        cv2.rectangle(fill_frame, (bx1, bar_y), (bx1 + fill_w, bar_y + bar_h),
                      (200, 80, 180), -1)
        cv2.addWeighted(fill_frame, 1.0, frame, 1.0, 0, frame)
        # Lueur sur le bord droit du fill
        glow_x = bx1 + fill_w
        glow_bar = np.zeros_like(frame)
        cv2.circle(glow_bar, (glow_x, bar_y + bar_h // 2), int(18 * scale),
                   (255, 120, 255), -1)
        glow_bar = cv2.GaussianBlur(glow_bar, (25, 25), 0)
        cv2.addWeighted(glow_bar, 0.7, frame, 1.0, 0, frame)

    # Bord de la barre
    cv2.rectangle(frame, (bx1, bar_y), (bx2, bar_y + bar_h), (80, 80, 80), 1)

    # % texte
    pct_text = f"{int(progress * 100)}%"
    (pw, ph), _ = cv2.getTextSize(pct_text, cv2.FONT_HERSHEY_DUPLEX, 0.55 * scale, 1)
    cv2.putText(frame, pct_text,
                (cx - pw // 2, bar_y - int(12 * scale) + ph // 2),
                cv2.FONT_HERSHEY_DUPLEX, 0.55 * scale, (200, 200, 200), 1, cv2.LINE_AA)

    # ── Texte statut export en bas ─────────────────────────────────────────────
    (sw, sh), _ = cv2.getTextSize(export_label, cv2.FONT_HERSHEY_PLAIN,
                                   1.0 * scale, 1)
    cv2.putText(frame, export_label,
                (cx - sw // 2, int(height * 0.93)),
                cv2.FONT_HERSHEY_PLAIN, 1.0 * scale, (120, 120, 120), 1, cv2.LINE_AA)

    return frame
