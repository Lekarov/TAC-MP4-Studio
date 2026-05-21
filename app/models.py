"""Modèles — Update 7 : spectre 3 couleurs + réactivité beats."""
from __future__ import annotations
from dataclasses import dataclass
from app.presets import WIDTH, HEIGHT


@dataclass
class RenderSettings:
    audio_path: str
    image_path: str
    output_path: str
    title_text: str
    artist_text: str
    duration_limit: float | None
    start_offset: float

    particle_preset: str
    smoke_preset: str
    smoke_color: str
    spectrum_style: str
    spectrum_size: float
    spectrum_y: float
    image_zoom: float
    pulse_strength: float

    text_x: float = 0.50
    text_y: float = 0.70
    background_blur: float = 8.0
    output_width: int = WIDTH
    output_height: int = HEIGHT

    bg_mode: str = "photo"
    bg_image_path: str = ""
    gradient_top: str = "#1a1a2e"
    gradient_bottom: str = "#0f3460"
    vinyl_mode: bool = False
    vinyl_black: bool = False

    # Update 5
    spectrum_color: str = "#ffffff"
    spectrum_color_auto: bool = False
    floating_bg: bool = False
    bg_oscillate: bool = False
    background_brightness: float = 0.85

    # Update 7 — spectre 3 couleurs + réactivité
    spectrum_color_mid: str = "#ffffff"   # couleur médiums
    spectrum_color_high: str = "#ffffff"  # couleur aigus
    spectrum_tricolor: bool = False       # activer le dégradé 3 bandes
    spectrum_reactive: bool = False       # flash couleur sur les kicks

    # Texte — police
    font_name: str = "Défaut"             # nom affiché (clé dans FONT_REGISTRY)

    # v1.8 — Texte amélioré
    show_text: bool = True
    font_size_scale: float = 1.0
    subtitle_text: str = ""
    shadow_intensity: float = 0.5
    shadow_color: str = "#000000"
    shadow_offset_x: float = 4.0
    shadow_offset_y: float = 4.0

    @property
    def is_vertical(self) -> bool:
        return self.output_height > self.output_width
