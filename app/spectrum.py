"""Spectre audio — fonctions de rendu du spectre et de l'orbe audio.

Extrait de app/renderer.py pour séparation des responsabilités.

Optimisations perf :
- Cache des indices de bandes géométriques dans spectrum_bands (évite np.geomspace à chaque frame).
- Cache des positions angulaires/coordonnées de l'orbe audio (evite math.cos/sin en boucle).
- Vectorisation du tracé de l'oscilloscope (suppression de boucle Python 256 iter).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from app.models import RenderSettings


# ── Cache des indices de bandes spectrales ────────────────────────────────────
# Clé : (bins, bar_count) → (starts, ends)
_bands_idx_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
_MAX_BANDS_CACHE = 16

# ── Cache des positions angulaires de l'orbe ─────────────────────────────────
# Clé : (n, radius) → (cos_a, sin_a) tableaux float32
_orb_angle_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
_MAX_ORB_CACHE = 16


# ── Helpers couleur (dupliqués ici pour éviter l'import circulaire) ───────────

_color_cache: dict[str, tuple[int, int, int]] = {}
_MAX_COLOR_CACHE = 64   # ~64 couleurs hex différentes max


def _parse_hex(hex_color: str) -> tuple[int, int, int]:
    if hex_color not in _color_cache:
        if len(_color_cache) >= _MAX_COLOR_CACHE:
            _color_cache.pop(next(iter(_color_cache)))
        h = hex_color.lstrip("#")
        try:
            _color_cache[hex_color] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except (ValueError, IndexError):
            _color_cache[hex_color] = (255, 255, 255)
    return _color_cache[hex_color]


def _tint_bgr(brightness: int, r: int, g: int, b: int) -> tuple[int, int, int]:
    s = brightness / 255.0
    return (int(b * s), int(g * s), int(r * s))


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _tricolor_for_bar(i: int, n: int, brightness: int,
                      c_bass: tuple, c_mid: tuple, c_high: tuple,
                      kick: float = 0.0, reactive: bool = False) -> tuple[int, int, int]:
    t = i / max(1, n - 1)
    if t < 0.5:
        rgb = _lerp_color(c_bass, c_mid, t * 2.0)
    else:
        rgb = _lerp_color(c_mid, c_high, (t - 0.5) * 2.0)

    if reactive and kick > 0.3:
        flash = min(1.0, (kick - 0.3) / 0.7)
        white = (255, 255, 255)
        rgb = _lerp_color(rgb, white, flash * 0.65)

    s = brightness / 255.0
    return (int(rgb[2] * s), int(rgb[1] * s), int(rgb[0] * s))


def rounded_rectangle(img, pt1, pt2, radius, color, thickness=-1):
    x1, y1 = pt1
    x2, y2 = pt2
    radius = max(1, min(radius, abs(x2 - x1) // 2, abs(y2 - y1) // 2))
    if thickness == -1:
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for cx, cy in [(x1+radius, y1+radius), (x2-radius, y1+radius),
                       (x1+radius, y2-radius), (x2-radius, y2-radius)]:
            cv2.circle(img, (cx, cy), radius, color, -1)
    else:
        cv2.rectangle(img, pt1, pt2, color, thickness, lineType=cv2.LINE_AA)


# ── Spectre ───────────────────────────────────────────────────────────────────

def spectrum_bands(spec_frame, bar_count=84):
    """Calcule les valeurs de bandes spectrales.

    Les indices de découpe (géométriques) sont mis en cache par (bins, bar_count)
    pour éviter de recalculer np.geomspace à chaque frame (~84 appels/seconde).
    """
    bins = len(spec_frame)
    cache_key = (bins, bar_count)
    if cache_key not in _bands_idx_cache:
        if len(_bands_idx_cache) >= _MAX_BANDS_CACHE:
            _bands_idx_cache.pop(next(iter(_bands_idx_cache)))
        idx = np.geomspace(1, bins, bar_count + 1).astype(int) - 1
        idx = np.clip(idx, 0, bins - 1)
        starts = idx[:-1]
        ends = np.maximum(idx[1:], idx[:-1] + 1)
        _bands_idx_cache[cache_key] = (starts, ends)

    starts, ends = _bands_idx_cache[cache_key]
    cumsum = np.empty(len(spec_frame) + 1, dtype=np.float32)
    cumsum[0] = 0.0
    np.cumsum(spec_frame, out=cumsum[1:])
    sums = cumsum[ends] - cumsum[starts]
    vals = (sums / np.maximum(ends - starts, 1).astype(np.float32))
    return np.clip(np.power(vals, 1.55), 0.0, 1.0)


def draw_spectrum(frame, bands, rms, bass, mid, high, settings: RenderSettings,
                  raw_frame=None, kick: float = 0.0):
    """Rendu du spectre. Supporte la couleur personnalisée + 3 couleurs (Update 7)."""
    height, width = frame.shape[:2]
    is_v = settings.is_vertical

    eff_y = max(settings.spectrum_y, 0.72) if is_v else settings.spectrum_y
    base_y = int(height * eff_y)
    max_w = int(width * (0.86 if is_v else 0.74))
    gap = max(2, int(7 * width / 1920))
    bar_count = len(bands)
    bar_w = max(2, int((max_w - gap * (bar_count - 1)) / bar_count))
    total_w = bar_count * bar_w + (bar_count - 1) * gap
    start_x = width // 2 - total_w // 2
    size = settings.spectrum_size
    style = settings.spectrum_style

    sr, sg, sb = _parse_hex(settings.spectrum_color)
    use_custom = (sr, sg, sb) != (255, 255, 255)

    if settings.spectrum_tricolor:
        c_bass = _parse_hex(settings.spectrum_color)
        c_mid  = _parse_hex(settings.spectrum_color_mid)
        c_high = _parse_hex(settings.spectrum_color_high)

        def tint(brightness: int, bar_idx: int = 0) -> tuple:
            return _tricolor_for_bar(bar_idx, bar_count, brightness,
                                     c_bass, c_mid, c_high,
                                     kick, settings.spectrum_reactive)
    else:
        def tint(brightness: int, bar_idx: int = 0) -> tuple:
            if settings.spectrum_reactive and kick > 0.3:
                flash = min(1.0, (kick - 0.3) / 0.7)
                sr2 = int(sr + (255 - sr) * flash * 0.6)
                sg2 = int(sg + (255 - sg) * flash * 0.6)
                sb2 = int(sb + (255 - sb) * flash * 0.6)
                return _tint_bgr(brightness, sr2, sg2, sb2)
            return _tint_bgr(brightness, sr, sg, sb) if use_custom else (brightness, brightness, brightness)

    # ── Barres premium ────────────────────────────────────────────────────────
    if style == "Barres premium":
        glow_layer = np.zeros_like(frame)
        for i, value in enumerate(bands):
            x1 = start_x + i * (bar_w + gap)
            x2 = x1 + bar_w
            h = int((height * 0.025 + value * height * 0.21 * size) * (0.82 + bass * 0.45 + rms * 0.2))
            bright = int(np.clip(175 + value * 80 + high * 20, 175, 255))
            rounded_rectangle(frame, (x1, base_y - h), (x2, base_y), max(1, bar_w // 2), tint(bright, i), -1)
            # Tip glow : halo sur la pointe de chaque barre
            if h > 4:
                tip_h = min(h, max(4, int(h * 0.30 + 6)))
                rounded_rectangle(glow_layer, (x1 - 1, base_y - h),
                                  (x2 + 1, base_y - h + tip_h),
                                  max(1, bar_w // 2 + 1), tint(bright, i), -1)
        blur_k = max(5, (bar_w * 2 + 1) | 1)
        glow_layer = cv2.GaussianBlur(glow_layer, (blur_k, blur_k), 0)
        cv2.addWeighted(glow_layer, 0.50, frame, 1.0, 0, frame)
        cv2.line(frame, (start_x, base_y + int(height * 0.022)),
                 (start_x + total_w, base_y + int(height * 0.022)),
                 tint(245, bar_count // 2), max(1, int(1 + bass * 5)), lineType=cv2.LINE_AA)

    # ── Barres néon ───────────────────────────────────────────────────────────
    elif style == "Barres néon":
        glow_layer = np.zeros_like(frame)
        for i, value in enumerate(bands):
            x1 = start_x + i * (bar_w + gap)
            x2 = x1 + bar_w
            h = int((height * 0.025 + value * height * 0.21 * size) * (0.82 + bass * 0.45 + rms * 0.2))
            if h <= 0:
                continue
            bright = int(np.clip(0.6 + value * 0.4, 0, 1) * 255)
            if settings.spectrum_tricolor:
                color      = tint(bright, i)
                glow_color = tint(255,    i)
            else:
                t_v = min(1.0, float(i) / bar_count)
                r_v = int(255 * (1.0 - t_v * 0.6))
                g_v = int(80 + 120 * t_v)
                b_v = int(60 + 195 * t_v)
                if settings.spectrum_reactive and kick > 0.3:
                    flash = min(1.0, (kick - 0.3) / 0.7)
                    r_v = min(255, r_v + int((255 - r_v) * flash * 0.6))
                    g_v = min(255, g_v + int((255 - g_v) * flash * 0.6))
                    b_v = min(255, b_v + int((255 - b_v) * flash * 0.6))
                color      = (int(b_v * bright / 255), int(g_v * bright / 255), int(r_v * bright / 255))
                glow_color = (min(255, b_v), min(255, g_v), min(255, r_v))
            rounded_rectangle(frame, (x1, base_y - h), (x2, base_y), max(1, bar_w // 2), color, -1)
            rounded_rectangle(glow_layer, (x1 - 2, base_y - h - 4), (x2 + 2, base_y), max(1, bar_w // 2 + 2), glow_color, -1)
        blur_k = 15 | 1
        glow_layer = cv2.GaussianBlur(glow_layer, (blur_k, blur_k), 0)
        cv2.addWeighted(glow_layer, 0.55, frame, 1.0, 0, frame)

    # ── Symétrie miroir ───────────────────────────────────────────────────────
    elif style == "Symétrie miroir":
        center_y = base_y - int(height * 0.04)
        for i, value in enumerate(bands):
            x1 = start_x + i * (bar_w + gap)
            x2 = x1 + bar_w
            h_half = int((height * 0.015 + value * height * 0.13 * size) * (0.85 + bass * 0.55))
            bright = int(np.clip(175 + value * 80 + high * 20, 175, 255))
            rounded_rectangle(frame, (x1, center_y - h_half), (x2, center_y), max(1, bar_w // 2), tint(bright, i), -1)
            faded = int(bright * 0.72)
            rounded_rectangle(frame, (x1, center_y), (x2, center_y + h_half), max(1, bar_w // 2), tint(faded, i), -1)
        cv2.line(frame, (start_x, center_y), (start_x + total_w, center_y),
                 tint(255, bar_count // 2), max(1, int(1.5 + bass * 4)), lineType=cv2.LINE_AA)

    # ── Arc plasma ────────────────────────────────────────────────────────────
    elif style == "Arc plasma":
        _draw_arc_plasma(frame, bands, bass, kick=kick, settings=settings,
                         base_y=base_y, width=width, height=height, size=size)

    elif style == "Onde plasma":
        _draw_onde_plasma(frame, bands, rms, bass, mid, high,
                          base_y, start_x, total_w, bar_w, gap, height, width, size)

    # ── Waveform miroir ───────────────────────────────────────────────────────
    elif style == "Waveform miroir":
        center_y = base_y - int(height * 0.08)
        for i, value in enumerate(bands):
            x1 = start_x + i * (bar_w + gap)
            x2 = x1 + bar_w
            h = int((height * 0.012 + value * height * 0.12 * size) * (0.85 + bass * 0.55))
            bright = int(np.clip(175 + value * 80 + high * 20, 175, 255))
            rounded_rectangle(frame, (x1, center_y - h), (x2, center_y + h), max(1, bar_w // 2), tint(bright, i), -1)

    # ── Oscilloscope ──────────────────────────────────────────────────────────
    elif style == "Oscilloscope":
        _draw_oscilloscope(frame, raw_frame, rms, bass, high, base_y,
                           start_x, total_w, height, width, size, tint)

    # ── Ligne fine ────────────────────────────────────────────────────────────
    elif style == "Ligne fine":
        pts = []
        for i, value in enumerate(bands):
            x = start_x + i * (bar_w + gap)
            y = base_y - int(value * height * 0.18 * size * (0.8 + mid * 0.4))
            pts.append((x, y))
        for i in range(len(pts) - 1):
            cv2.line(frame, pts[i], pts[i + 1], tint(235, i),
                     max(1, int(2 * width / 1920)), lineType=cv2.LINE_AA)


def _draw_oscilloscope(frame, raw_frame, rms, bass, high, base_y,
                        start_x, total_w, height, width, size, tint_fn):
    """Oscilloscope : forme d'onde brute temps réel (Update 5).

    Optimisation : calcul vectorisé numpy des coordonnées (évite boucle Python 256 iter).
    """
    if raw_frame is None or len(raw_frame) == 0:
        return

    n_pts = 256
    samples = np.interp(
        np.linspace(0, len(raw_frame) - 1, n_pts),
        np.arange(len(raw_frame)),
        raw_frame,
    )

    amp_scale = height * 0.18 * size * (0.7 + bass * 0.8 + rms * 0.4)
    center_y  = base_y - int(height * 0.04)
    step      = total_w / max(1, n_pts - 1)
    lw        = max(1, int((1.5 + rms * 2.5) * width / 1920))

    # Vectorisation : calcul des coordonnées sans boucle Python
    i_arr = np.arange(n_pts, dtype=np.float32)
    x_arr = (start_x + i_arr * step).astype(np.int32)
    amps  = np.clip(samples * amp_scale,
                    -height * 0.25, height * 0.25).astype(np.int32)
    y_up   = (center_y - amps).astype(np.int32)
    y_down = (center_y + amps).astype(np.int32)

    bright = int(np.clip(190 + rms * 65 + high * 20, 190, 255))
    color  = tint_fn(bright)
    glow = np.zeros_like(frame)

    # Dessiner les segments avec polylines OpenCV
    pts_up_cv   = np.stack([x_arr, y_up],   axis=1).reshape(-1, 1, 2)
    pts_down_cv = np.stack([x_arr, y_down], axis=1).reshape(-1, 1, 2)
    cv2.polylines(frame, [pts_up_cv],   False, color, lw,     cv2.LINE_AA)
    cv2.polylines(frame, [pts_down_cv], False, color, lw,     cv2.LINE_AA)
    cv2.polylines(glow,  [pts_up_cv],   False, color, lw + 6, cv2.LINE_AA)
    cv2.polylines(glow,  [pts_down_cv], False, color, lw + 6, cv2.LINE_AA)

    cv2.line(frame, (start_x, center_y), (start_x + total_w, center_y),
             tint_fn(60), 1, cv2.LINE_AA)

    glow = cv2.GaussianBlur(glow, (19, 19), 0)
    cv2.addWeighted(glow, 0.45, frame, 1.0, 0, frame)


# Cache des angles de l'arc plasma par (n,) → (cos_a, sin_a)
_arc_angle_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
_MAX_ARC_CACHE = 8


def _draw_arc_plasma(frame, bands, bass, kick, settings, base_y, width, height, size):
    """Demi-cercle plasma au bas du cadre.

    Optimisation : les tableaux cos/sin sont pré-calculés et mis en cache par n.
    """
    n = min(len(bands), 96)
    sample = np.interp(np.linspace(0, len(bands) - 1, n), np.arange(len(bands)), bands)

    cx = width // 2
    cy = base_y + int(height * 0.05)
    radius = int(width * 0.32 * size + kick * 8)

    glow_layer = np.zeros_like(frame)

    # Cache des angles (ne dépend que de n)
    if n not in _arc_angle_cache:
        if len(_arc_angle_cache) >= _MAX_ARC_CACHE:
            _arc_angle_cache.pop(next(iter(_arc_angle_cache)))
        angles = np.array([math.pi + (i / (n - 1)) * math.pi for i in range(n)],
                          dtype=np.float32)
        _arc_angle_cache[n] = (np.cos(angles), np.sin(angles))

    cos_a, sin_a = _arc_angle_cache[n]

    for i, value in enumerate(sample):
        bar_len = int(8 + value * height * 0.09 * size + bass * 18)

        x1 = int(cx + cos_a[i] * radius)
        y1 = int(cy + sin_a[i] * radius)
        x2 = int(cx + cos_a[i] * (radius + bar_len))
        y2 = int(cy + sin_a[i] * (radius + bar_len))

        t = float(i) / n
        r = int(255 * (1.0 - t * 0.5))
        g = int(60 + 140 * t)
        b = int(80 + 175 * t)
        bright_f = 0.65 + float(value) * 0.35
        color      = (int(b * bright_f), int(g * bright_f), int(r * bright_f))
        glow_color = (min(255, b), min(255, g), min(255, r))

        lw = max(1, int(3 * width / 1920))
        cv2.line(frame, (x1, y1), (x2, y2), color, lw, lineType=cv2.LINE_AA)
        cv2.line(glow_layer, (x1, y1), (x2, y2), glow_color, lw + 4, lineType=cv2.LINE_AA)

    bright_ring = int(np.clip(60 + bass * 80, 60, 140))
    cv2.circle(frame, (cx, cy), radius, (bright_ring, bright_ring, bright_ring),
               max(1, int(1.5 * width / 1920)), lineType=cv2.LINE_AA)

    blur_k = (31 | 1)
    glow_layer = cv2.GaussianBlur(glow_layer, (blur_k, blur_k), 0)
    cv2.addWeighted(glow_layer, 0.6, frame, 1.0, 0, frame)


def _draw_onde_plasma(frame, bands, rms, bass, mid, high, base_y, start_x, total_w, bar_w, gap, height, width, size):
    """Waveform épaisse avec halo lumineux coloré."""
    n = len(bands)
    glow_layer = np.zeros_like(frame)

    pts_main = []
    pts_mirror = []

    for i, value in enumerate(bands):
        x = start_x + i * (bar_w + gap)
        amplitude = int(value * height * 0.16 * size * (0.85 + bass * 0.5))
        pts_main.append((x, base_y - amplitude))
        pts_mirror.append((x, base_y + int(amplitude * 0.4)))

    for i in range(len(pts_main) - 1):
        val = float(bands[i])
        t = float(i) / n
        r = int(200 + 55 * (1.0 - t))
        g = int(100 + 100 * t)
        b = int(50 + 200 * t)
        lw_main = max(2, int((2 + val * 5) * width / 1920))
        lw_glow = lw_main + 8
        cv2.line(frame, pts_main[i], pts_main[i + 1], (b // 2, g // 2, r // 2), lw_main, lineType=cv2.LINE_AA)
        cv2.line(glow_layer, pts_main[i], pts_main[i + 1], (b, g, r), lw_glow, lineType=cv2.LINE_AA)

    for i in range(len(pts_mirror) - 1):
        bright = int(np.clip(80 + bands[i] * 80, 60, 160))
        cv2.line(frame, pts_mirror[i], pts_mirror[i + 1], (bright // 2, bright // 2, bright // 2),
                 max(1, int(1.5 * width / 1920)), lineType=cv2.LINE_AA)

    blur_k = (25 | 1)
    glow_layer = cv2.GaussianBlur(glow_layer, (blur_k, blur_k), 0)
    cv2.addWeighted(glow_layer, 0.65, frame, 1.0, 0, frame)


def draw_audio_orb(frame, bands, bass, kick, settings: RenderSettings):
    """Rendu de l'orbe audio circulaire.

    Optimisation : les tableaux cos/sin des angles sont mis en cache par (n, radius)
    pour éviter math.cos/sin en boucle Python (~112 appels/frame).
    """
    if settings.spectrum_style not in ("Cercle radial", "Cercle + barres"):
        return

    height, width = frame.shape[:2]
    is_v = settings.is_vertical

    if is_v:
        center = (width // 2, int(height * 0.58))
    else:
        center = (width // 2, height // 2 - int(height * 0.09))

    radius = int(min(width, height) * 0.36 + kick * 12)
    n = min(len(bands), 112)
    sample = np.interp(np.linspace(0, len(bands) - 1, n), np.arange(len(bands)), bands)

    sr, sg, sb = _parse_hex(settings.spectrum_color)
    use_c = (sr, sg, sb) != (255, 255, 255)
    tri = settings.spectrum_tricolor
    if tri:
        c_bass = _parse_hex(settings.spectrum_color)
        c_mid  = _parse_hex(settings.spectrum_color_mid)
        c_high = _parse_hex(settings.spectrum_color_high)

    glow_layer = np.zeros_like(frame)
    lw = max(1, int(2 * width / 1920))

    # Cache des cos/sin pour éviter les calculs trigonométriques en boucle
    angle_key = (n, radius)
    if angle_key not in _orb_angle_cache:
        if len(_orb_angle_cache) >= _MAX_ORB_CACHE:
            _orb_angle_cache.pop(next(iter(_orb_angle_cache)))
        angles = np.array([(i / n) * math.tau - math.pi / 2 for i in range(n)],
                          dtype=np.float32)
        _orb_angle_cache[angle_key] = (np.cos(angles), np.sin(angles))

    cos_a, sin_a = _orb_angle_cache[angle_key]

    for i, value in enumerate(sample):
        length = int(6 + value * height * 0.082 * settings.spectrum_size + bass * 12 + kick * 16)
        x1 = int(center[0] + cos_a[i] * radius)
        y1 = int(center[1] + sin_a[i] * radius)
        x2 = int(center[0] + cos_a[i] * (radius + length))
        y2 = int(center[1] + sin_a[i] * (radius + length))
        bright = int(np.clip(170 + value * 85 + bass * 20 + kick * 20, 170, 255))
        if tri:
            color = _tricolor_for_bar(i, n, bright, c_bass, c_mid, c_high,
                                      kick, settings.spectrum_reactive)
        elif use_c:
            color = _tint_bgr(bright, sr, sg, sb)
        else:
            color = (bright, bright, bright)
        cv2.line(frame,      (x1, y1), (x2, y2), color, lw,     lineType=cv2.LINE_AA)
        cv2.line(glow_layer, (x1, y1), (x2, y2), color, lw + 4, lineType=cv2.LINE_AA)

    blur_k = 15 | 1
    glow_layer = cv2.GaussianBlur(glow_layer, (blur_k, blur_k), 0)
    cv2.addWeighted(glow_layer, 0.55, frame, 1.0, 0, frame)
