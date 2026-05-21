"""Constantes visuelles, presets et palettes couleurs — Update 5."""
from __future__ import annotations

# ── Dimensions ────────────────────────────────────────────────────────────────
WIDTH = 1920
HEIGHT = 1080
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
PREVIEW_W = 960
PREVIEW_H = 540
FPS = 30
PREVIEW_SECONDS = 22

# ── Palettes ──────────────────────────────────────────────────────────────────
SMOKE_COLORS: dict[str, tuple[int, int, int]] = {
    "Blanc":     (235, 235, 235),
    "Or chaud":  (214, 172, 86),
    "Rouge":     (255, 45,  35),
    "Bleu néon": (75,  145, 255),
    "Violet":    (168, 95,  255),
    "Vert":      (35,  255, 80),
    "Reggae":    (255, 220, 20),
}

REGGAE_PALETTE: list[tuple[int, int, int]] = [
    (255, 35, 25),
    (255, 225, 20),
    (25, 255, 70),
]

# ── Presets globaux — Update 5 : tous les champs supportés ───────────────────
# Clés optionnelles : vinyl_mode, vinyl_black, spectrum_color,
#                     floating_bg, bg_mode, gradient_top, gradient_bottom
GLOBAL_PRESETS: dict[str, dict] = {

    # ── Presets classiques (mis à jour) ───────────────────────────────────────
    "Clean White": {
        "particle_preset": "Épuré",
        "smoke_preset":    "Légère",
        "smoke_color":     "Blanc",
        "spectrum_style":  "Barres premium",
        "spectrum_size":   0.95,
        "spectrum_y":      0.90,
        "image_zoom":      1.00,
        "pulse_strength":  0.85,
        "vinyl_mode":      False,
        "spectrum_color":  "#ffffff",
        "floating_bg":     False,
        "bg_mode":         "photo",
    },
    "Dark Premium": {
        "particle_preset": "Premium",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Blanc",
        "spectrum_style":  "Cercle radial",
        "spectrum_size":   1.05,
        "spectrum_y":      0.90,
        "image_zoom":      1.00,
        "pulse_strength":  1.10,
        "vinyl_mode":      False,
        "spectrum_color":  "#ffffff",
        "floating_bg":     False,
        "bg_mode":         "photo",
    },
    "Neon Club": {
        "particle_preset": "Énergie",
        "smoke_preset":    "Dense",
        "smoke_color":     "Bleu néon",
        "spectrum_style":  "Barres néon",
        "spectrum_size":   1.20,
        "spectrum_y":      0.88,
        "image_zoom":      0.96,
        "pulse_strength":  1.45,
        "vinyl_mode":      False,
        "spectrum_color":  "#ffffff",
        "floating_bg":     False,
        "bg_mode":         "photo",
    },
    "Reggae Smoke": {
        "particle_preset":   "Énergie",
        "smoke_preset":      "Dense",
        "smoke_color":       "Reggae",
        "spectrum_style":    "Arc plasma",
        "spectrum_size":     1.20,
        "spectrum_y":        0.88,
        "image_zoom":        1.00,
        "pulse_strength":    1.45,
        "vinyl_mode":        False,
        "spectrum_color":    "#ff2020",   # bass = rouge
        "spectrum_color_mid": "#ffdd00",  # mid  = jaune
        "spectrum_color_high": "#20ff50", # high = vert
        "spectrum_tricolor": True,
        "spectrum_reactive": True,
        "floating_bg":       False,
        "bg_mode":           "photo",
    },
    "Chill Lo-Fi": {
        "particle_preset": "Pluie lumineuse",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Violet",
        "spectrum_style":  "Onde plasma",
        "spectrum_size":   0.85,
        "spectrum_y":      0.91,
        "image_zoom":      1.05,
        "pulse_strength":  0.75,
        "vinyl_mode":      False,
        "spectrum_color":  "#ffffff",
        "floating_bg":     True,
        "bg_mode":         "photo",
    },
    "Short Vertical": {
        "particle_preset": "Premium",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Blanc",
        "spectrum_style":  "Symétrie miroir",
        "spectrum_size":   1.10,
        "spectrum_y":      0.82,
        "image_zoom":      1.05,
        "pulse_strength":  1.20,
        "vinyl_mode":      False,
        "spectrum_color":  "#ffffff",
        "floating_bg":     False,
        "bg_mode":         "photo",
    },

    # ── Nouveaux presets (Update 4 + 5) ───────────────────────────────────────
    "Vinyl Classic": {
        "particle_preset": "Épuré",
        "smoke_preset":    "Légère",
        "smoke_color":     "Blanc",
        "spectrum_style":  "Barres premium",
        "spectrum_size":   1.00,
        "spectrum_y":      0.90,
        "image_zoom":      1.00,
        "pulse_strength":  1.00,
        "vinyl_mode":      True,
        "vinyl_black":     True,     # vinyle noir classique
        "spectrum_color":  "#e8c97a",  # or chaud
        "floating_bg":     False,
        "bg_mode":         "gradient",
        "gradient_top":    "#1a0e04",
        "gradient_bottom": "#0d0808",
    },
    "Vinyl Gold": {
        "particle_preset": "Premium",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Or chaud",
        "spectrum_style":  "Cercle + barres",
        "spectrum_size":   1.10,
        "spectrum_y":      0.89,
        "image_zoom":      1.05,
        "pulse_strength":  1.20,
        "vinyl_mode":      True,
        "vinyl_black":     False,    # image visible sur le vinyle
        "spectrum_color":  "#d4a840",
        "floating_bg":     True,
        "bg_mode":         "photo",
    },
    "Acid Wave": {
        "particle_preset": "Énergie",
        "smoke_preset":    "Dense",
        "smoke_color":     "Vert",
        "spectrum_style":  "Oscilloscope",
        "spectrum_size":   1.15,
        "spectrum_y":      0.88,
        "image_zoom":      1.00,
        "pulse_strength":  1.35,
        "vinyl_mode":      False,
        "spectrum_color":  "#00ff88",
        "floating_bg":     True,
        "bg_mode":         "gradient",
        "gradient_top":    "#001a0a",
        "gradient_bottom": "#000d05",
    },
    "Purple Dream": {
        "particle_preset": "Pluie lumineuse",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Violet",
        "spectrum_style":  "Cercle radial",
        "spectrum_size":   1.05,
        "spectrum_y":      0.90,
        "image_zoom":      1.05,
        "pulse_strength":  0.90,
        "vinyl_mode":      True,
        "vinyl_black":     False,
        "spectrum_color":  "#b06aff",
        "floating_bg":     True,
        "bg_mode":         "gradient",
        "gradient_top":    "#120a1e",
        "gradient_bottom": "#0a0512",
    },
    "Neon Tricolor": {
        "particle_preset":    "Énergie",
        "smoke_preset":       "Cinématique",
        "smoke_color":        "Bleu néon",
        "spectrum_style":     "Barres néon",
        "spectrum_size":      1.15,
        "spectrum_y":         0.88,
        "image_zoom":         0.98,
        "pulse_strength":     1.40,
        "vinyl_mode":         False,
        "spectrum_color":     "#ff0080",   # bass = rose
        "spectrum_color_mid": "#8000ff",   # mid  = violet
        "spectrum_color_high": "#00e5ff",  # high = cyan
        "spectrum_tricolor":  True,
        "spectrum_reactive":  True,
        "floating_bg":        False,
        "bg_mode":            "photo",
    },
    "Sunrise": {
        "particle_preset":    "Pluie lumineuse",
        "smoke_preset":       "Légère",
        "smoke_color":        "Or chaud",
        "spectrum_style":     "Symétrie miroir",
        "spectrum_size":      1.00,
        "spectrum_y":         0.89,
        "image_zoom":         1.00,
        "pulse_strength":     1.00,
        "vinyl_mode":         False,
        "spectrum_color":     "#ff4400",   # bass = orange rouge
        "spectrum_color_mid": "#ffaa00",   # mid  = or
        "spectrum_color_high": "#ffee88",  # high = jaune doux
        "spectrum_tricolor":  True,
        "spectrum_reactive":  False,
        "floating_bg":        False,
        "bg_mode":            "gradient",
        "gradient_top":       "#1a0800",
        "gradient_bottom":    "#0d0400",
    },
    "Midnight Vinyl": {
        "particle_preset": "Premium",
        "smoke_preset":    "Cinématique",
        "smoke_color":     "Bleu néon",
        "spectrum_style":  "Symétrie miroir",
        "spectrum_size":   1.10,
        "spectrum_y":      0.88,
        "image_zoom":      1.00,
        "pulse_strength":  1.15,
        "vinyl_mode":      True,
        "vinyl_black":     True,
        "spectrum_color":  "#4da8ff",
        "floating_bg":     False,
        "bg_mode":         "gradient",
        "gradient_top":    "#040810",
        "gradient_bottom": "#020509",
    },
}

PARTICLE_PRESETS: dict[str, dict] = {
    "Aucune":          {"count": 0,   "speed": 0.00, "size": 0.00, "alpha": 0.00},
    "Épuré":           {"count": 120, "speed": 0.65, "size": 1.00, "alpha": 0.65},
    "Premium":         {"count": 260, "speed": 1.00, "size": 1.15, "alpha": 0.85},
    "Énergie":         {"count": 440, "speed": 1.55, "size": 1.25, "alpha": 1.00},
    "Pluie lumineuse": {"count": 360, "speed": 1.20, "size": 0.90, "alpha": 0.75},
}

SMOKE_PRESETS: dict[str, dict] = {
    # ── Fumée classique ───────────────────────────────────────────────────────
    "Aucune":         {"density": 0.00, "speed": 0.00, "blur": 0,   "type": "blob"},
    "Légère":         {"density": 0.35, "speed": 0.55, "blur": 31,  "type": "blob"},
    "Cinématique":    {"density": 0.78, "speed": 0.85, "blur": 45,  "type": "blob"},
    "Dense":          {"density": 1.18, "speed": 1.15, "blur": 59,  "type": "blob"},
    # ── Nouveaux effets ───────────────────────────────────────────────────────
    "Voiles":         {"density": 1.00, "speed": 0.35, "blur": 111, "type": "voiles"},
    "Lueur ambiante": {"density": 1.00, "speed": 1.00, "blur": 0,   "type": "glow"},
    "Traces plasma":  {"density": 1.20, "speed": 1.20, "blur": 13,  "type": "plasma"},
}

SPECTRUM_STYLES: list[str] = [
    "Barres premium",
    "Barres néon",
    "Cercle radial",
    "Cercle + barres",
    "Symétrie miroir",
    "Arc plasma",
    "Onde plasma",
    "Waveform miroir",
    "Oscilloscope",
    "Ligne fine",
]
