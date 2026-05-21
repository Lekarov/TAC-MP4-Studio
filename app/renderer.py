"""Rendu frame par frame — OpenCV + PIL.

Update 4 : disque vinyle rotatif réactif aux beats.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.logger import get_logger
from app.models import RenderSettings
from app.particles import (FloatingParticle, SmokeBlob, VeilBlob,
                           PlasmaTrail, draw_ambient_glow)
from app.presets import (
    WIDTH, HEIGHT,
    PARTICLE_PRESETS, SMOKE_PRESETS, SMOKE_COLORS, REGGAE_PALETTE,
)
from app.spectrum import draw_spectrum, draw_audio_orb, spectrum_bands
from app.vinyl import draw_vinyl_disk, _make_sleeve, _composite_image

_log = get_logger("renderer")

# ── Caches ────────────────────────────────────────────────────────────────────
_vignette_cache: dict[tuple[int, int], np.ndarray] = {}
_font_cache: dict[tuple[int, bool, str], Any] = {}
_font_registry: dict[str, str | None] = {}
_font_registry_built: bool = False
_color_cache: dict[str, tuple[int, int, int]] = {}   # hex → (r,g,b)
_MAX_COLOR_CACHE = 64    # taille max du cache couleur — évite la croissance indéfinie
_MAX_FONT_CACHE  = 64    # ~32 tailles × 2 bold états


def _parse_hex(hex_color: str) -> tuple[int, int, int]:
    """Parse un hex color (#rrggbb) en tuple RGB, avec cache borné."""
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
    """Teinte une couleur BGR par (r,g,b) avec la luminosité donnée."""
    s = brightness / 255.0
    return (int(b * s), int(g * s), int(r * s))


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
    """Interpolation linéaire entre deux couleurs RGB."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _tricolor_for_bar(i: int, n: int, brightness: int,
                      c_bass: tuple, c_mid: tuple, c_high: tuple,
                      kick: float = 0.0, reactive: bool = False) -> tuple[int, int, int]:
    """Retourne la couleur BGR d'une barre selon sa position (bass→mid→high).

    Update 7 :
    - Dégradé 3 couleurs sur la largeur du spectre
    - Mode réactif : flash blanc/brillant sur les kicks
    """
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


def extract_dominant_color(cover_bgr: np.ndarray) -> str:
    """Extrait la couleur dominante d'une pochette (BGR numpy).

    Retourne un hex string (#rrggbb). Utilisé pour spectrum_color_auto.
    """
    small = cv2.resize(cover_bgr, (32, 32))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].flatten()
    mask = sat > 60
    if mask.sum() < 8:
        return "#ffffff"
    pixels = small.reshape(-1, 3)[mask]
    mean_bgr = pixels.mean(axis=0).astype(int)
    b, g, r = int(mean_bgr[0]), int(mean_bgr[1]), int(mean_bgr[2])
    # Booster la saturation : amplifier l'écart par rapport au gris
    gray = (r + g + b) // 3
    boost = 1.6
    r = min(255, max(0, int(gray + (r - gray) * boost)))
    g = min(255, max(0, int(gray + (g - gray) * boost)))
    b_out = min(255, max(0, int(gray + (b - gray) * boost)))
    return f"#{r:02x}{g:02x}{b_out:02x}"


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _build_font_registry() -> None:
    """Construit le registre des polices (dossier fonts/ + système Windows)."""
    global _font_registry, _font_registry_built
    if _font_registry_built:
        return
    import os as _os2, platform

    fonts_dir = _os2.path.join(_os2.path.dirname(_os2.path.dirname(__file__)), "fonts")
    # Noms affichés → fichier sans extension
    bundled = {
        "Liberation Sans":   "LiberationSans-Bold",
        "Liberation Serif":  "LiberationSerif-Bold",
        "Liberation Mono":   "LiberationMono-Bold",
        "Carlito":           "Carlito-Bold",
        "Caladea":           "Caladea-Bold",
        "Montserrat":        "Montserrat-Bold",
        "Oswald":            "Oswald-Bold",
        "Bebas Neue":        "BebasNeue-Regular",
        "Russo One":         "RussoOne-Regular",
        "Pacifico":          "Pacifico-Regular",
        "Raleway":           "Raleway-Bold",
        "Playfair Display":  "PlayfairDisplay-Bold",
    }
    registry: dict[str, str | None] = {"Défaut": None}
    if _os2.path.isdir(fonts_dir):
        for label, stem in bundled.items():
            for ext in (".ttf", ".otf"):
                path = _os2.path.join(fonts_dir, stem + ext)
                if _os2.path.isfile(path):
                    registry[label] = path
                    break

    # Polices Windows sympas
    if platform.system() == "Windows":
        wf = _os2.path.join(_os2.environ.get("WINDIR", "C:/Windows"), "Fonts")
        win = {
            "Impact":      "impact.ttf",
            "Georgia":     "georgiabd.ttf",
            "Trebuchet":   "trebucbd.ttf",
            "Arial Black": "ariblk.ttf",
        }
        for label, fname in win.items():
            p = _os2.path.join(wf, fname)
            if _os2.path.isfile(p):
                registry[label] = p
        # Segoe UI toujours dispo sur Windows
        seg = _os2.path.join(wf, "segoeuib.ttf")
        if _os2.path.isfile(seg):
            registry["Segoe UI"] = seg

    _font_registry = registry
    _font_registry_built = True


def get_font_names() -> list[str]:
    _build_font_registry()
    return list(_font_registry.keys())


def safe_font(size: int, bold: bool = False, font_name: str = "Défaut") -> Any:
    """Charge une police PIL depuis le registre. Résultat mis en cache par (size, bold, font_name)."""
    _build_font_registry()
    size = max(12, (size // 2) * 2)
    key = (size, bold, font_name)
    if key not in _font_cache:
        if len(_font_cache) >= _MAX_FONT_CACHE:
            _font_cache.pop(next(iter(_font_cache)))
        path = _font_registry.get(font_name)
        try:
            if path:
                _font_cache[key] = ImageFont.truetype(path, size=size)
            else:
                # Défaut : Segoe UI si dispo
                candidates = [
                    "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
                    "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
                ]
                for p in candidates:
                    if Path(p).exists():
                        _font_cache[key] = ImageFont.truetype(p, size=size)
                        break
                else:
                    _font_cache[key] = ImageFont.load_default()
        except Exception as exc:
            _log.warning("Font not found, using default fallback. font_name=%r path=%r error=%s",
                         font_name, path, exc)
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _get_vignette(width: int, height: int) -> np.ndarray:
    key = (width, height)
    if key not in _vignette_cache:
        y_idx, x_idx = np.ogrid[:height, :width]
        dist = np.sqrt((x_idx - width / 2.0) ** 2 + (y_idx - height / 2.0) ** 2)
        mask = np.clip(1.0 - dist / (min(width, height) * 0.92), 0.16, 1.0)
        _vignette_cache[key] = mask[..., np.newaxis].astype(np.float32)
    return _vignette_cache[key]


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


# ── Chargement image ──────────────────────────────────────────────────────────

def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def generate_gradient_bg(color_top: str, color_bottom: str,
                          width: int, height: int) -> np.ndarray:
    """Génère un fond dégradé vertical BGR (numpy vectorisé)."""
    top = np.array(_hex_to_bgr(color_top),    dtype=np.float32)
    bot = np.array(_hex_to_bgr(color_bottom), dtype=np.float32)
    t = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, np.newaxis, np.newaxis]
    gradient = (top[np.newaxis] * (1.0 - t) + bot[np.newaxis] * t).astype(np.uint8)
    return np.repeat(gradient, width, axis=1)


def load_cover_image(path, blur_radius, zoom, width=WIDTH, height=HEIGHT,
                     bg_mode="photo", gradient_top="#1a1a2e", gradient_bottom="#0f3460",
                     background_brightness: float = 0.85, bg_image_path: str = ""):
    """Charge la pochette et génère le background (photo floutée, dégradé ou image perso).

    bg_mode "photo" | "gradient" | "custom"
    """
    img = Image.open(path).convert("RGB")

    def _crop_to_ratio(src: Image.Image) -> Image.Image:
        src_w, src_h = src.size
        target_ratio = width / height
        src_ratio = src_w / src_h
        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            src = src.crop((left, 0, left + new_w, src_h))
        else:
            new_h = int(src_w / target_ratio)
            top_px = (src_h - new_h) // 2
            src = src.crop((0, top_px, src_w, top_px + new_h))
        return src

    if bg_mode == "gradient":
        bg_arr = generate_gradient_bg(gradient_top, gradient_bottom, width, height)
    elif bg_mode == "custom" and bg_image_path and Path(bg_image_path).is_file():
        bg_src = Image.open(bg_image_path).convert("RGB")
        bg = _crop_to_ratio(bg_src).resize((width, height), Image.LANCZOS)
        if blur_radius > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(float(blur_radius)))
        bg = ImageEnhance.Brightness(bg).enhance(float(background_brightness))
        bg_arr = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)
    else:
        bg = _crop_to_ratio(img.copy()).resize((width, height), Image.LANCZOS)
        if blur_radius > 0:
            bg = bg.filter(ImageFilter.GaussianBlur(float(blur_radius)))
        bg = ImageEnhance.Brightness(bg).enhance(float(background_brightness))
        bg_arr = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)

    # Pochette
    is_vertical = height > width
    zoom_factor = 0.60 if is_vertical else 0.53
    max_side = int(min(width, height) * zoom_factor * zoom)
    cover = img.copy()
    cover.thumbnail((max_side, max_side), Image.LANCZOS)
    cover_arr = cv2.cvtColor(np.array(cover), cv2.COLOR_RGB2BGR)

    return bg_arr, cover_arr


# ── Dessin éléments ───────────────────────────────────────────────────────────

def draw_vignette(frame):
    h, w = frame.shape[:2]
    frame[:] = (frame.astype(np.float32) * _get_vignette(w, h)).astype(np.uint8)


def overlay_center(base, overlay, bass, kick, pulse_strength, is_vertical=False):
    height, width = base.shape[:2]
    h, w = overlay.shape[:2]
    x = (width - w) // 2
    pulse = int((8 + bass * 20 * pulse_strength + kick * 35 * pulse_strength) * (width / WIDTH))

    if is_vertical:
        y = int(height * 0.12)
    else:
        y = (height - h) // 2 - int(height * 0.09)

    # Glow two-pass : halo serré + halo diffus, intensité réactive au kick
    glow_intensity = 0.30 + bass * 0.10 + kick * 0.20
    glow = np.zeros_like(base)
    rounded_rectangle(glow, (x - pulse, y - pulse),
                      (x + w + pulse, y + h + pulse), 24, (155, 155, 155), -1)
    blur_tight = cv2.GaussianBlur(glow, (55, 55), 0)
    blur_wide  = cv2.GaussianBlur(glow, (91, 91), 0)
    glow_combined = cv2.addWeighted(blur_tight, 0.65, blur_wide, 0.40, 0)
    cv2.addWeighted(glow_combined, glow_intensity, base, 1.0, 0, base)

    base[y:y + h, x:x + w] = overlay


def _draw_text_line(draw, text, font, x_center, y, alpha,
                    shadow_intensity=0.5, shadow_color_rgb=(0, 0, 0),
                    shadow_offset_x=4.0, shadow_offset_y=4.0):
    """Dessine une ligne de texte centrée avec ombre paramétrable."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = int(x_center - tw / 2)
    shadow_a = int(shadow_intensity * 120)
    if shadow_a > 0:
        ox, oy = int(shadow_offset_x), int(shadow_offset_y)
        sr, sg, sb = shadow_color_rgb
        for dx, dy in [(-ox, -oy), (ox, -oy), (-ox, oy), (ox, oy)]:
            draw.text((x + dx, y + dy), text, font=font, fill=(sr, sg, sb, shadow_a))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))


def draw_reactive_text(frame, title, rms, kick, text_x=0.50, text_y=0.70,
                       artist="", font_name="Défaut",
                       font_size_scale=1.0, subtitle_text="",
                       shadow_intensity=0.5, shadow_color="#000000",
                       shadow_offset_x=4.0, shadow_offset_y=4.0):
    """Rend le texte artiste + titre + sous-titre sur la frame.

    v1.8 : taille de police paramétrable, 3e ligne sous-titre, ombre configurable.
    """
    has_artist = bool(artist.strip())
    has_title  = bool(title.strip())
    has_sub    = bool(subtitle_text.strip())

    if not has_artist and not has_title and not has_sub:
        return

    height, width = frame.shape[:2]
    scale = width / WIDTH
    kick_boost = 1.0 + kick * 0.10 + rms * 0.025
    fss = max(0.3, float(font_size_scale))

    artist_size = max(16, int(62 * scale * kick_boost * fss))
    title_size  = max(14, int(44 * scale * kick_boost * fss))
    sub_size    = max(12, int(34 * scale * kick_boost * fss))

    font_artist   = safe_font(artist_size, bold=True,  font_name=font_name)
    font_title    = safe_font(title_size,  bold=False, font_name=font_name)
    font_subtitle = safe_font(sub_size,    bold=False, font_name=font_name) if has_sub else None

    # Convertir en RGBA directement pour éviter double convert("RGBA") plus bas
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    cx = width * text_x
    base_y = int(height * text_y)
    text_alpha  = int(min(255, 210 + kick * 45))
    title_alpha = int(text_alpha * 0.82)
    sub_alpha   = int(title_alpha * 0.75)
    spacing_at  = int(artist_size * 1.25)   # artiste top → titre top
    spacing_ts  = int(title_size  * 1.20)   # titre top → sous-titre top

    shadow_rgb = _parse_hex(shadow_color)
    shadow_kw = dict(
        shadow_intensity=shadow_intensity,
        shadow_color_rgb=shadow_rgb,
        shadow_offset_x=shadow_offset_x,
        shadow_offset_y=shadow_offset_y,
    )

    if has_artist and has_title:
        sub_extra = (spacing_ts + sub_size) if has_sub else title_size
        total_h   = spacing_at + sub_extra
        y_artist  = base_y - total_h // 2
        y_title   = y_artist + spacing_at
        _draw_text_line(draw, artist.strip(), font_artist, cx, y_artist, text_alpha,  **shadow_kw)
        _draw_text_line(draw, title.strip(),  font_title,  cx, y_title,  title_alpha, **shadow_kw)
        if has_sub:
            _draw_text_line(draw, subtitle_text.strip(), font_subtitle, cx, y_title + spacing_ts, sub_alpha, **shadow_kw)

    elif has_artist:
        y = base_y - artist_size // 2
        _draw_text_line(draw, artist.strip(), font_artist, cx, y, text_alpha, **shadow_kw)
        if has_sub:
            _draw_text_line(draw, subtitle_text.strip(), font_subtitle, cx, y + spacing_at, sub_alpha, **shadow_kw)

    else:
        # Titre seul — avec wrapping
        max_width = int(width * 0.78)
        words = title.strip().split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font_title)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        lines = lines[:2]
        lh = int(title_size * 1.16)
        y = base_y - len(lines) * lh // 2
        for i, line in enumerate(lines):
            _draw_text_line(draw, line, font_title, cx, y + i * lh, title_alpha, **shadow_kw)
        if has_sub:
            y_sub = y + len(lines) * lh + int(title_size * 0.25)
            _draw_text_line(draw, subtitle_text.strip(), font_subtitle, cx, y_sub, sub_alpha, **shadow_kw)

    img = Image.alpha_composite(img, layer)
    frame[:] = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def draw_music_linked_particles(frame, particles, high, kick, settings: RenderSettings):
    preset = PARTICLE_PRESETS[settings.particle_preset]
    if preset["count"] <= 0:
        particles.clear()
        return particles

    height, width = frame.shape[:2]
    target_count = int(preset["count"] * (width / WIDTH) ** 0.5)

    while len(particles) < target_count:
        particles.append(FloatingParticle(width, height, settings.particle_preset))
    if len(particles) > target_count:
        del particles[target_count:]

    layer = np.zeros_like(frame)
    for p in particles:
        p.update(high, kick, preset)
        p.draw(layer, high, kick, preset, width / WIDTH)

    # Two-pass bloom : halo serré + halo diffus
    blur_tight = cv2.GaussianBlur(layer, (5,  5), 0)
    blur_halo  = cv2.GaussianBlur(layer, (21, 21), 0)
    bloom = cv2.addWeighted(blur_tight, 0.85, blur_halo, 0.45, 0)
    cv2.addWeighted(bloom, 0.78, frame, 1.0, 0, frame)
    return particles


def draw_smoke(frame, smoke_blobs, bass, kick, settings: RenderSettings):
    preset = SMOKE_PRESETS[settings.smoke_preset]
    if preset["density"] <= 0:
        smoke_blobs.clear()
        return smoke_blobs

    smoke_type = preset.get("type", "blob")

    # Lueur ambiante — pas de particules, pur numpy
    if smoke_type == "glow":
        smoke_blobs.clear()
        rgb = SMOKE_COLORS.get(settings.smoke_color, SMOKE_COLORS["Blanc"])
        draw_ambient_glow(frame, bass, kick, preset, (rgb[2], rgb[1], rgb[0]))
        return smoke_blobs

    height, width = frame.shape[:2]
    _BLOB_CLS = {"blob": SmokeBlob, "voiles": VeilBlob, "plasma": PlasmaTrail}
    blob_cls = _BLOB_CLS.get(smoke_type, SmokeBlob)

    if smoke_type == "voiles":
        target = max(2, int(4 * preset["density"]))
    elif smoke_type == "plasma":
        target = max(4, int(14 * preset["density"] * (width / WIDTH) ** 0.5))
    else:
        target = int(18 * preset["density"] * (width / WIDTH) ** 0.5)

    # Remplace les blobs du mauvais type (changement de preset en cours de route)
    smoke_blobs[:] = [b if isinstance(b, blob_cls) else blob_cls(width, height)
                      for b in smoke_blobs[:target]]
    while len(smoke_blobs) < target:
        smoke_blobs.append(blob_cls(width, height))

    layer = np.zeros_like(frame)
    for blob in smoke_blobs:
        blob.update(bass, kick, preset)
        if settings.smoke_color == "Reggae":
            rgb = REGGAE_PALETTE[blob.color_index % len(REGGAE_PALETTE)]
        else:
            rgb = SMOKE_COLORS.get(settings.smoke_color, SMOKE_COLORS["Blanc"])
        blob.draw(layer, (rgb[2], rgb[1], rgb[0]), bass, kick, preset)

    blur = (preset["blur"] | 1) if preset.get("blur", 0) > 0 else 0
    if blur > 1:
        layer = cv2.GaussianBlur(layer, (blur, blur), 0)

    alpha = 0.82 if smoke_type == "voiles" else 0.76
    cv2.addWeighted(layer, alpha, frame, 1.0, 0, frame)
    return smoke_blobs



# ── Rendu complet d'une frame ─────────────────────────────────────────────────

def render_frame(bg, cover, particles, smoke_blobs, spec_frame, metrics,
                 smoothed_bands, settings: RenderSettings, vinyl_angle: float = 0.0,
                 frame_idx: int = 0, raw_frame=None):
    # Fond flottant (Update 5) — dérive sinusoïdale réactive aux basses
    # Utilise pad(edge) + crop pour éviter la ligne de bordure du np.roll
    if settings.floating_bg:
        phase = frame_idx * (2.0 * math.pi / (30 * 8))  # cycle 8s
        bass_val = float(metrics.get("bass", 0))
        dx = int(math.sin(phase) * 22 * (1.0 + bass_val * 1.8))
        dy = int(math.cos(phase * 0.65) * 12 * (1.0 + bass_val * 1.2))
        pad = 32
        padded = np.pad(bg, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        py = max(0, min(pad + dy, padded.shape[0] - bg.shape[0]))
        px = max(0, min(pad + dx, padded.shape[1] - bg.shape[1]))
        frame = padded[py:py + bg.shape[0], px:px + bg.shape[1]].copy()
    elif getattr(settings, "bg_oscillate", False):
        phase = frame_idx * (2.0 * math.pi / (30 * 14))  # cycle 14s lent
        rms_val  = float(metrics.get("rms",  0))
        bass_val = float(metrics.get("bass", 0))
        dx = int(math.sin(phase)        * 3 * (1.0 + rms_val  * 0.6))  # max ~5 px
        dy = int(math.cos(phase * 0.7)  * 2 * (1.0 + bass_val * 0.4))  # max ~3 px
        pad = 8
        padded = np.pad(bg, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        py = max(0, min(pad + dy, padded.shape[0] - bg.shape[0]))
        px = max(0, min(pad + dx, padded.shape[1] - bg.shape[1]))
        frame = padded[py:py + bg.shape[0], px:px + bg.shape[1]].copy()
    else:
        frame = bg.copy()

    is_v = settings.is_vertical

    rms  = metrics["rms"]
    bass = metrics["bass"]
    mid  = metrics["mid"]
    high = metrics["high"]
    kick = metrics["kick"]

    particles   = draw_music_linked_particles(frame, particles, high, kick, settings)
    smoke_blobs = draw_smoke(frame, smoke_blobs, bass, kick, settings)

    # Vignette appliquée ICI : assombrit fond + particules + fumée uniquement.
    # Spectre, texte et pochette sont dessinés après, à leur luminosité réelle.
    draw_vignette(frame)

    bands = spectrum_bands(spec_frame, 84)
    # Smoothing adaptatif : montée rapide sur les beats, descente lente après
    alpha = np.where(bands > smoothed_bands, 0.38, 0.14).astype(np.float32)
    smoothed_bands[:] = smoothed_bands * (1.0 - alpha) + bands * alpha

    draw_audio_orb(frame, smoothed_bands, bass, kick, settings)

    # Pochette / Vinyle — selon le mode
    if settings.vinyl_mode:
        new_vinyl_angle = vinyl_angle + 1.8
        draw_vinyl_disk(frame, cover, vinyl_angle, bass, kick, settings)
    else:
        new_vinyl_angle = vinyl_angle
        overlay_center(frame, cover, bass, kick, settings.pulse_strength, is_vertical=is_v)

    # Texte
    eff_text_y = settings.text_y
    if is_v:
        eff_text_y = 0.62

    if getattr(settings, "show_text", True):
        draw_reactive_text(frame, settings.title_text, rms, kick,
                           settings.text_x, eff_text_y,
                           artist=settings.artist_text,
                           font_name=getattr(settings, "font_name", "Défaut"),
                           font_size_scale=getattr(settings, "font_size_scale", 1.0),
                           subtitle_text=getattr(settings, "subtitle_text", ""),
                           shadow_intensity=getattr(settings, "shadow_intensity", 0.5),
                           shadow_color=getattr(settings, "shadow_color", "#000000"),
                           shadow_offset_x=getattr(settings, "shadow_offset_x", 4.0),
                           shadow_offset_y=getattr(settings, "shadow_offset_y", 4.0))

    if settings.spectrum_style != "Cercle radial":
        draw_spectrum(frame, smoothed_bands, rms, bass, mid, high, settings, raw_frame=raw_frame, kick=kick)

    return frame, particles, smoke_blobs, smoothed_bands, new_vinyl_angle
