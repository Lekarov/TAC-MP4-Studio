"""TAC MP4 Studio — Update 3

Nouveautés :
  1. Fond dégradé configurable avec color pickers (alternative à la photo floutée)
  2. Miniatures dans l'historique (screenshot auto après chaque export)
  3. Mode plein écran preview (bouton ⛶ ou double-clic sur la preview)
"""
from __future__ import annotations

import os
import re
import shutil
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

from app.config import load_config, save_config, DEFAULT_CREATIONS_DIR
from app.errors import AudioImportError, ConfigError, ImageImportError
from app.logger import get_logger, log_exception
# NB: RenderSettings et les constantes presets ci-dessous ne sont pas toutes
# utilisées directement dans ce fichier — turbo.py, export_ui.py et preview.py
# les importent à l'exécution via `from app.ui.app import ...` (mêmes conventions
# que pour les couleurs/fonts). Ne pas les retirer sans vérifier ces mixins.
from app.models import RenderSettings
from app.presets import (
    GLOBAL_PRESETS, PARTICLE_PRESETS, SMOKE_COLORS, SMOKE_PRESETS, SPECTRUM_STYLES,
    PREVIEW_SECONDS, PREVIEW_W, PREVIEW_H, SHORT_WIDTH, SHORT_HEIGHT, FPS,
)
from app.renderer import load_cover_image, render_frame, get_font_names
from app.ui.preview import PreviewMixin
from app.ui.editor import EditorMixin
from app.ui.pages import PagesMixin
from app.ui.turbo import TurboMixin
from app.ui.turbo_v2 import TurboV2Mixin
from app.ui.export_ui import ExportMixin
from app.ui.youtube_ui import YoutubeMixin

_log = get_logger("ui")

PREVIEW_W_V = 304
PREVIEW_H_V = 540
WAVEFORM_H  = 56

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Version ───────────────────────────────────────────────────────────────────
VERSION = "1.12.0"  # v1.12.0 — Synchro YouTube, historique de publication, gestion des données

BG      = "#0a0a0a"
SURF    = "#111111"
SURF2   = "#191919"
SURF3   = "#212121"
BORDER  = "#2a2a2a"
ACCENT  = "#7c3aed"
ACCHOV  = "#6d28d9"
ACCLT   = "#a78bfa"
TEXT    = "#f4f4f5"
MUTED   = "#71717a"
SUCCESS = "#22c55e"
WARN    = "#f59e0b"
DANGER  = "#ef4444"

FONT_H1 = FONT_H2 = FONT_SEC = FONT_SM = FONT_MU = None
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def _init_fonts():
    global FONT_H1, FONT_H2, FONT_SEC, FONT_SM, FONT_MU
    FONT_H1  = ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
    FONT_H2  = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
    FONT_SEC = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
    FONT_SM  = ctk.CTkFont(family="Segoe UI", size=10)
    FONT_MU  = ctk.CTkFont(family="Segoe UI", size=9)


def _btn(parent, text, command, accent=False, danger=False, small=False, **kw):
    defaults = {
        "fg_color":      ACCENT if accent else ("#7f1d1d" if danger else SURF3),
        "hover_color":   ACCHOV if accent else ("#991b1b" if danger else SURF2),
        "text_color":    TEXT,
        "font":          FONT_SM if small else FONT_H2,
        "corner_radius": 8,
    }
    defaults.update(kw)
    return ctk.CTkButton(parent, text=text, command=command, **defaults)


def _card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=SURF2, corner_radius=10,
                        border_color=BORDER, border_width=1, **kw)


def _sep(parent):
    ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0).pack(
        fill="x", padx=12, pady=(8, 0))


def _format_size(n: float) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


# ── Tooltip simple ───────────────────────────────────────────────────────────

class _Tooltip:
    """Tooltip minimaliste — apparaît après 500ms, disparaît au Leave."""

    NAMES = {
        "⚡": "Presets",
        "🎵": "Ambiance · Vinyle · Texte",
        "🎨": "Fond · Dégradé · Flottant",
        "📊": "Spectre · Couleur",
        "🚀": "Export",
    }

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text   = text
        self._tip: tk.Toplevel | None = None
        self._job: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel,   add="+")

    def _schedule(self, _=None) -> None:
        self._cancel()
        self._job = self._widget.after(500, self._show)

    def _cancel(self, _=None) -> None:
        if self._job:
            self._widget.after_cancel(self._job)
            self._job = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _show(self) -> None:
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.configure(bg="#1e1e1e")
        tk.Label(self._tip, text=self._text, bg="#1e1e1e", fg="#e4e4e7",
                 font=("Segoe UI", 9), padx=10, pady=5,
                 relief="flat").pack()
        self._tip.wm_geometry(f"+{x - 60}+{y}")


class App(PagesMixin, EditorMixin, PreviewMixin, TurboMixin, TurboV2Mixin, ExportMixin,
          YoutubeMixin,
          ctk.CTk if not _DND_AVAILABLE else TkinterDnD.Tk):

    def __init__(self) -> None:
        super().__init__()
        _init_fonts()

        self.title("TAC MP4 Studio")
        self.configure(bg=BG) if _DND_AVAILABLE else self.configure(fg_color=BG)
        try:
            _icon_path = Path(__file__).resolve().parent.parent.parent / "img" / "icone.png"
            self._app_icon = ImageTk.PhotoImage(Image.open(_icon_path))
            self.wm_iconphoto(True, self._app_icon)
        except Exception:
            pass
        try:
            self.config_data = load_config()
        except ConfigError as exc:
            log_exception(exc, context="App.__init__ load_config")
            messagebox.showwarning("Configuration", exc.message)
            from app.config import default_config
            self.config_data = default_config()
        settings = self.config_data.get("settings", {})
        self.geometry(settings.get("window_geometry", "1300x820+60+30"))
        self.minsize(1180, 760)
        self.after(10, lambda: self.state("zoomed"))  # plein écran au démarrage

        # ── State ─────────────────────────────────────────────────────────────
        self.audio_path   = ""
        self.image_path   = ""
        self.output_path  = ""
        self.project_root = self.config_data.get("project_root", str(DEFAULT_CREATIONS_DIR))
        Path(self.project_root).mkdir(parents=True, exist_ok=True)
        self.history: list[dict] = self.config_data.get("history", [])
        self.turbo_v2_history: dict = self.config_data.get("turbo_v2_history", {})
        if not isinstance(self.turbo_v2_history, dict):
            self.turbo_v2_history = {}
        self._turbo_v2_last_folder: str = self.config_data.get("turbo_v2_last_folder", "")

        # YouTube
        self.youtube_profiles: dict = self.config_data.get("youtube_profiles", {})
        self.youtube_history: dict = self.config_data.get("youtube_history", {})
        self.youtube_last_scheduled_date: str = self.config_data.get("youtube_last_scheduled_date", "")
        self._youtube_active_profile: str = next(iter(self.youtube_profiles), "")
        self._youtube_queue: list[dict] = []

        # ── Tkinter vars ───────────────────────────────────────────────────────
        self.title_text       = tk.StringVar(value=settings.get("title_text", ""))
        self.artist_text      = tk.StringVar(value=settings.get("artist_text", ""))
        self.status_var       = tk.StringVar(value="Prêt")
        self.project_root_var = tk.StringVar(value=self.project_root)
        self.global_preset    = tk.StringVar(value=settings.get("global_preset",   "Dark Premium"))
        self.particle_preset  = tk.StringVar(value=settings.get("particle_preset", "Premium"))
        self.smoke_preset     = tk.StringVar(value=settings.get("smoke_preset",    "Cinématique"))
        self.smoke_color      = tk.StringVar(value=settings.get("smoke_color",     "Blanc"))
        self.spectrum_style   = tk.StringVar(value=settings.get("spectrum_style",  "Cercle radial"))
        self.spectrum_size    = tk.DoubleVar(value=float(settings.get("spectrum_size",  1.05)))
        self.spectrum_y       = tk.DoubleVar(value=float(settings.get("spectrum_y",     0.90)))
        self.image_zoom       = tk.DoubleVar(value=float(settings.get("image_zoom",     1.00)))
        self.pulse_strength   = tk.DoubleVar(value=float(settings.get("pulse_strength", 1.10)))
        self.text_x           = tk.DoubleVar(value=float(settings.get("text_x",         0.50)))
        self.text_y           = tk.DoubleVar(value=float(settings.get("text_y",         0.70)))
        self.preview_start    = tk.StringVar(value=settings.get("preview_start", "0"))
        self.project_name_var = tk.StringVar()
        self.export_mode      = tk.StringVar(value=settings.get("export_mode", "COMPLET"))

        # Update 3 — fond dégradé
        self.bg_mode         = tk.StringVar(value=settings.get("bg_mode", "photo"))
        self.bg_image_path   = settings.get("bg_image_path", "")
        self.gradient_top    = settings.get("gradient_top",    "#1a1a2e")
        self.gradient_bottom = settings.get("gradient_bottom", "#0f3460")

        # Update 4 — disque vinyle
        self.vinyl_mode  = tk.BooleanVar(value=bool(settings.get("vinyl_mode", False)))
        self.vinyl_black = tk.BooleanVar(value=bool(settings.get("vinyl_black", False)))
        self.vinyl_angle: float = 0.0

        # Presets utilisateur
        self.user_presets: dict = self.config_data.get("user_presets", {})
        self.hidden_builtin_presets: set = set(self.config_data.get("hidden_builtin_presets", []))

        # Update 5 — couleur spectre + fond flottant
        self.spectrum_color      = settings.get("spectrum_color", "#ffffff")
        self.spectrum_color_auto = tk.BooleanVar(value=bool(settings.get("spectrum_color_auto", False)))
        self.floating_bg         = tk.BooleanVar(value=bool(settings.get("floating_bg", False)))
        self.bg_oscillate        = tk.BooleanVar(value=bool(settings.get("bg_oscillate", False)))
        self.background_blur       = tk.DoubleVar(value=float(settings.get("background_blur", 8.0)))
        self.background_brightness = tk.DoubleVar(value=float(settings.get("background_brightness", 0.85)))

        # Police du texte (Update 8b)
        self.font_name = tk.StringVar(value=settings.get("font_name", "Défaut"))

        # v1.8 — Texte amélioré
        self.show_text        = tk.BooleanVar(value=bool(settings.get("show_text", True)))
        self.font_size_scale  = tk.DoubleVar(value=float(settings.get("font_size_scale",  1.0)))
        self.subtitle_text    = tk.StringVar(value=settings.get("subtitle_text", ""))
        self.shadow_intensity = tk.DoubleVar(value=float(settings.get("shadow_intensity", 0.5)))
        self.shadow_color     = settings.get("shadow_color", "#000000")
        self.shadow_offset_x  = tk.DoubleVar(value=float(settings.get("shadow_offset_x",  4.0)))
        self.shadow_offset_y  = tk.DoubleVar(value=float(settings.get("shadow_offset_y",  4.0)))

        # Turbo / Favoris
        self.user_preset_favorites: set = set(self.config_data.get("user_preset_favorites", []))
        self._turbo_queue: list[dict]   = []
        self._turbo_stop:  bool         = False
        self._turbo_running: bool       = False
        self._turbo_image: str          = ""
        self._turbo_bg_image: str       = ""
        self._turbo_view_active: bool   = False
        self._turbo_v2_view_active: bool = False
        self._turbo_mode: str           = "v1"

        # Update 7 — spectre 3 couleurs + réactivité
        self.spectrum_color_mid  = settings.get("spectrum_color_mid",  "#ffffff")
        self.spectrum_color_high = settings.get("spectrum_color_high", "#ffffff")
        self.spectrum_tricolor   = tk.BooleanVar(value=bool(settings.get("spectrum_tricolor", False)))
        self.spectrum_reactive   = tk.BooleanVar(value=bool(settings.get("spectrum_reactive", False)))

        # Fichiers de test preset (persistés, indépendants du projet courant)
        _test_dir = Path(__file__).parent.parent.parent / "Test"
        self.test_audio_path = settings.get("test_audio_path",
                                            str(_test_dir / "Cobblestone Rain.wav"))
        self.test_image_path = settings.get("test_image_path",
                                            str(_test_dir / "Cover.png"))

        # ── Preview state ──────────────────────────────────────────────────────
        self.preview_is_vertical  = False
        self.preview_ready        = False
        self.preview_running      = False
        self.audio_playing        = False
        self.preview_started_at: float | None = None
        self.ffplay_process       = None
        self.preview_index        = 0
        self.preview_features: dict | None    = None
        self.preview_bg: np.ndarray | None    = None
        self.preview_cover: np.ndarray | None = None
        self.preview_particles: list = []
        self.preview_smoke: list     = []
        self.preview_smoothed        = np.zeros(84, dtype=np.float32)
        self.photo: ImageTk.PhotoImage | None = None
        self.is_rendering            = False
        self._preview_job: str | None = None
        self._persist_job: str | None = None
        self._export_overlay_frame: ctk.CTkFrame | None = None
        self._ffmpeg_banner: ctk.CTkFrame | None = None

        # Waveform
        self.waveform_data: np.ndarray | None = None
        self.audio_total_duration: float = 0.0
        self._waveform_canvas: tk.Canvas | None = None

        # Update 3 — plein écran
        self._fullscreen_win: ctk.CTkToplevel | None   = None
        self._fullscreen_label: tk.Label | None         = None
        self._fullscreen_photo: ImageTk.PhotoImage | None = None
        self._fullscreen_running: bool = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.bind("<space>",  lambda e: self._kb_play_pause())
        self.bind("<r>",      lambda e: self._prepare_preview())
        self.bind("<R>",      lambda e: self._prepare_preview())
        self.bind("<Escape>", lambda e: self._kb_escape())
        self.bind("<F11>",    lambda e: self._open_fullscreen())

        if _DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)

        self.show_home()
        self.after(400, self._check_ffmpeg)

    # ══════════════════════════════════════════════════════════════════════════
    # RACCOURCIS
    # ══════════════════════════════════════════════════════════════════════════

    def _kb_play_pause(self):
        if not hasattr(self, "preview_label") or not self.preview_label:
            return
        if self.audio_playing:
            self._pause_preview_audio()
        else:
            self._play_preview_audio()

    def _kb_escape(self):
        if self._fullscreen_win:
            self._close_fullscreen()
        elif hasattr(self, "preview_label") and self.preview_label:
            self.show_home()


    # ══════════════════════════════════════════════════════════════════════════
    # FFMPEG CHECK
    # ══════════════════════════════════════════════════════════════════════════

    def _check_ffmpeg(self):
        missing = [t for t in ("ffmpeg", "ffplay") if not shutil.which(t)]
        if not missing:
            return
        tools = " et ".join(missing)
        banner = ctk.CTkFrame(self, fg_color="#431407", corner_radius=0, height=40)
        banner.pack(fill="x", side="bottom")
        banner.pack_propagate(False)
        ctk.CTkLabel(banner, text=f"⚠  {tools} introuvable — export et preview audio indisponibles.",
                     text_color=WARN, font=FONT_SM).pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(banner, text="→ Installe FFmpeg et ajoute-le au PATH",
                     text_color="#fdba74", font=FONT_MU).pack(side="left")
        _btn(banner, "✕", banner.destroy, small=True, width=32, height=24,
             fg_color="transparent", hover_color="#7c2d12").pack(side="right", padx=12)

    # ══════════════════════════════════════════════════════════════════════════
    # DRAG & DROP
    # ══════════════════════════════════════════════════════════════════════════

    def _on_drop(self, event):
        raw = event.data.strip()
        paths = re.findall(r"\{([^}]+)\}", raw) if raw.startswith("{") else raw.split()

        # Routage Turbo : si la vue Turbo est active, déléguer
        if self._turbo_view_active:
            self._turbo_add_paths(paths)
            return

        audio_found = image_found = ""
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext in AUDIO_EXTS and not audio_found:
                audio_found = p
            elif ext in IMAGE_EXTS and not image_found:
                image_found = p
        if not audio_found and not image_found:
            self._set_status("Format non reconnu", DANGER)
            return
        if audio_found:
            self.audio_path = audio_found
            self._parse_audio_filename(audio_found)
        if image_found:
            self.image_path = image_found
        if self.audio_path and self.image_path:
            self.show_editor()
        elif self.audio_path:
            self.show_step_image()

    # ══════════════════════════════════════════════════════════════════════════
    # UI BUILD
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, height=58, fg_color=SURF, corner_radius=0)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="TAC", font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color=ACCLT).pack(side="left", padx=(20, 0), pady=14)
        ctk.CTkLabel(hdr, text=" Studio", font=ctk.CTkFont("Segoe UI", 20, "bold"),
                     text_color=TEXT).pack(side="left", pady=14)
        ctk.CTkLabel(hdr, text="  ⌨  Espace · R · Échap · F11",
                     text_color=MUTED, font=FONT_MU).pack(side="left", padx=20)
        self._status_dot = ctk.CTkLabel(hdr, text="●", text_color=MUTED,
                                        font=ctk.CTkFont("Segoe UI", 11))
        self._status_dot.pack(side="right", padx=(0, 8))
        self._status_lbl = ctk.CTkLabel(hdr, textvariable=self.status_var,
                                        text_color=MUTED, font=FONT_SM)
        self._status_lbl.pack(side="right", padx=(0, 4))

        # Bouton réglages ⚙
        gear = ctk.CTkButton(hdr, text="⚙", width=34, height=34,
                             fg_color="transparent", hover_color=SURF2,
                             text_color=MUTED, font=ctk.CTkFont("Segoe UI", 16),
                             corner_radius=8, command=self._open_settings_window)
        gear.pack(side="right", padx=(0, 4), pady=12)
        _Tooltip(gear, "Réglages & raccourcis")

        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.pack(fill="both", expand=True)

    def _clear_main(self):
        self._turbo_view_active = False
        self._turbo_v2_view_active = False
        # Annuler l'animation de l'accueil (fix fuite mémoire Update 8)
        if hasattr(self, "_home_anim_job") and self._home_anim_job:
            try:
                self.after_cancel(self._home_anim_job)
            except Exception:
                pass
            self._home_anim_job = None
        self._stop_audio()
        self.preview_running = False
        self._waveform_canvas = None
        self._close_fullscreen()
        # Supprimer les traces StringVar des CTkEntry avant destruction.
        # Sinon le _textvariable_callback interne de CTkEntry se déclenche
        # sur un widget détruit à chaque .set() ultérieur → TclError.
        for _var in ("artist_text", "title_text", "subtitle_text",
                     "preview_start", "project_name_var"):
            _sv = getattr(self, _var, None)
            if _sv is None:
                continue
            for _mode, _cbname in list(_sv.trace_info()):
                try:
                    _sv.trace_remove(_mode, _cbname)
                except Exception:
                    pass
        for child in self.main.winfo_children():
            child.destroy()

    def _set_status(self, text, color=MUTED):
        self.status_var.set(text)
        if hasattr(self, "_status_dot"):
            self._status_dot.configure(text_color=color)
            self._status_lbl.configure(text_color=color)

    def _on_close(self):
        try:
            self._persist_now()
            self._stop_audio()
            self._close_fullscreen()
        finally:
            self.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    # PAGES — voir app/ui/pages.py (PagesMixin)
    # ══════════════════════════════════════════════════════════════════════════

    # ── Éditeur ───────────────────────────────────────────────────────────────

    def show_editor(self):
        self._clear_main()
        self._set_status("Preview", SUCCESS)

        if self.audio_path:
            self._load_waveform(self.audio_path)

        # Suspendre le rendu tkinter pendant la construction de l'UI
        self.main.update_idletasks()

        left = ctk.CTkFrame(self.main, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=16)
        right_outer = ctk.CTkFrame(self.main, fg_color=BG, width=380)
        right_outer.pack(side="right", fill="y", padx=(0, 16), pady=16)
        right_outer.pack_propagate(False)

        # Preview
        preview_wrap = ctk.CTkFrame(left, fg_color="#000000", corner_radius=12,
                                    border_color=BORDER, border_width=1)
        preview_wrap.pack(fill="both", expand=True)
        self.preview_wrap = preview_wrap   # référence pour lire les dimensions

        self.preview_label = tk.Label(preview_wrap, bg="#000000", bd=0, highlightthickness=0)
        self.preview_label.pack(fill="both", expand=True)
        self.preview_label.bind("<Double-Button-1>", lambda e: self._open_fullscreen())

        # Waveform
        wf_frame = ctk.CTkFrame(left, fg_color=SURF, corner_radius=8,
                                 border_color=BORDER, border_width=1, height=WAVEFORM_H)
        wf_frame.pack(fill="x", pady=(6, 0))
        wf_frame.pack_propagate(False)
        self._waveform_canvas = tk.Canvas(wf_frame, bg="#0d0d0d", bd=0,
                                          highlightthickness=0, height=WAVEFORM_H - 4)
        self._waveform_canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self._waveform_canvas.bind("<Button-1>", self._on_waveform_click)
        self._waveform_canvas.bind("<Configure>", lambda e: self._draw_waveform())
        ctk.CTkLabel(wf_frame, text="Clic = déplacer preview · Zone violette = durée preview · Double-clic preview = plein écran",
                     text_color=MUTED, font=FONT_MU).pack(side="bottom", pady=1)

        # Contrôles
        ctrl = ctk.CTkFrame(left, fg_color="transparent")
        ctrl.pack(fill="x", pady=(8, 0))
        _btn(ctrl, "▶ Preview", self._play_preview_audio,
             accent=True, width=110, height=34, small=True).pack(side="left", padx=(0, 6))
        _btn(ctrl, "⏸", self._pause_preview_audio,
             width=42, height=34, small=True).pack(side="left", padx=(0, 6))
        _btn(ctrl, "⟲ Recharger", self._prepare_preview,
             width=110, height=34, small=True).pack(side="left", padx=(0, 6))
        _btn(ctrl, "📷 Rendu HD", self._capture_hd_frame,
             width=110, height=34, small=True,
             fg_color="#1a1a2e", hover_color="#2a2a4e").pack(side="left", padx=(0, 12))
        _btn(ctrl, "⛶ Plein écran", self._open_fullscreen,
             width=120, height=34, small=True).pack(side="left", padx=(0, 12))
        self._fmt_btn = _btn(ctrl,
                             "9:16 → 16:9" if self.preview_is_vertical else "16:9 → 9:16",
                             self._toggle_preview_format,
                             width=120, height=34, small=True,
                             fg_color=ACCENT if self.preview_is_vertical else SURF3,
                             hover_color=ACCHOV if self.preview_is_vertical else SURF2)
        self._fmt_btn.pack(side="left")
        _btn(ctrl, "← Accueil", self.show_home,
             width=100, height=34, small=True).pack(side="right")

        # ── Panneau droit : Fichiers (fixe) + TabView ───────────────────────

        # Fichiers — toujours visible en haut, hors onglets
        fc = _card(right_outer)
        fc.pack(fill="x", padx=4, pady=(0, 6))
        ctk.CTkLabel(fc, text=self._short_name(self.audio_path),
                     text_color=ACCLT, font=FONT_SM, anchor="w").pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(fc, text=self._short_name(self.image_path),
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(fill="x", padx=14, pady=(0, 6))
        br = ctk.CTkFrame(fc, fg_color="transparent")
        br.pack(fill="x", padx=10, pady=(0, 8))
        _btn(br, "🎵 Musique", self.show_step_audio, small=True, height=28).pack(
            side="left", padx=(0, 6), fill="x", expand=True)
        _btn(br, "🖼 Pochette", self.show_step_image, small=True, height=28).pack(
            side="left", fill="x", expand=True)

        # TabView 5 onglets — construit dans un frame caché pour éviter le rendu progressif
        _build_cover = ctk.CTkFrame(right_outer, fg_color=BG)
        _build_cover.place(relx=0, rely=0, relwidth=1, relheight=1)

        tabs = ctk.CTkTabview(right_outer,
                              fg_color=SURF2,
                              segmented_button_fg_color=SURF3,
                              segmented_button_selected_color=ACCENT,
                              segmented_button_selected_hover_color=ACCHOV,
                              segmented_button_unselected_color=SURF3,
                              segmented_button_unselected_hover_color=SURF2,
                              text_color=TEXT,
                              corner_radius=10, border_width=1, border_color=BORDER)
        tabs.pack(fill="both", expand=True, padx=4)
        for tab_name in ["⚡", "📸", "✨", "📊", "📝", "🚀"]:
            tabs.add(tab_name)

        # Agrandir les boutons d'onglets
        try:
            tabs._segmented_button.configure(
                font=ctk.CTkFont("Segoe UI", 17),
                height=44,
            )
        except Exception:
            pass

        def mkscroll(tab_name):
            s = ctk.CTkScrollableFrame(tabs.tab(tab_name), fg_color="transparent",
                                       scrollbar_button_color=SURF3,
                                       scrollbar_button_hover_color=ACCENT)
            s.pack(fill="both", expand=True)
            return s

        # Tooltips sur les onglets
        _tab_tips = {
            "⚡": "Presets",
            "📸": "Image · Vinyle · Fond",
            "✨": "Effets · Particules · Atmosphère",
            "📊": "Spectre · Couleur",
            "📝": "Texte · Police · Ombre",
            "🚀": "Export",
        }
        try:
            for tab_name, tip_text in _tab_tips.items():
                btn = tabs._segmented_button._buttons_dict.get(tab_name)
                if btn:
                    _Tooltip(btn, tip_text)
        except Exception:
            pass

        # ── ⚡ Presets ────────────────────────────────────────────────────────────
        tp = mkscroll("⚡")

        # Sauvegarder les réglages actuels
        self._user_preset_name = tk.StringVar()
        save_row = ctk.CTkFrame(tp, fg_color="transparent")
        save_row.pack(fill="x", pady=(8, 4))
        ctk.CTkEntry(save_row, textvariable=self._user_preset_name,
                     placeholder_text="Sauvegarder les réglages actuels...",
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_SM).pack(side="left", fill="x", expand=True, padx=(0, 6))
        _btn(save_row, "💾", self._save_user_preset, small=True, height=32,
             accent=True).pack(side="right")

        _sep(tp)

        # Bibliothèque unifiée (intégrés + perso)
        self._presets_library_frame = ctk.CTkScrollableFrame(
            tp, fg_color="transparent", height=340,
            scrollbar_button_color=SURF3, scrollbar_button_hover_color=ACCENT,
        )
        self._presets_library_frame.pack(fill="x", pady=(6, 4))
        self._refresh_presets_library()

        # Restauration
        _btn(tp, "↩  Restaurer les presets intégrés", self._restore_builtin_presets,
             small=True, height=28).pack(fill="x", pady=(4, 0))

        # ── 📸 Image ──────────────────────────────────────────────────────────
        ti = mkscroll("📸")

        ctk.CTkLabel(ti, text="Pochette", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(8, 2))
        self._slider_row(ti, "Taille", self.image_zoom, 0.65, 1.35)
        self._pulse_frame = ctk.CTkFrame(ti, fg_color="transparent")
        self._pulse_frame.pack(fill="x")
        self._slider_row(self._pulse_frame, "Réactivité", self.pulse_strength, 0.0, 2.2)

        _sep(ti)
        vr = ctk.CTkFrame(ti, fg_color="transparent")
        vr.pack(fill="x", pady=(10, 2))
        ctk.CTkLabel(vr, text="🎵  Disque vinyle", text_color=TEXT, font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(vr, text="", variable=self.vinyl_mode, command=self._on_vinyl_mode_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(ti, text="Sort à droite de la pochette, réactif aux beats",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 4))
        self._vinyl_opts = ctk.CTkFrame(ti, fg_color="transparent")
        self._vinyl_opts.pack(fill="x", pady=(0, 6))
        for val, lbl in [(False, "🖼 Image"), (True, "⚫ Noir classique")]:
            ctk.CTkRadioButton(self._vinyl_opts, text=lbl, variable=self.vinyl_black, value=val,
                               command=self._on_setting_changed,
                               fg_color=ACCENT, hover_color=ACCHOV,
                               text_color=TEXT, font=FONT_SM).pack(side="left", padx=(0, 14))
        self._refresh_vinyl_opts()

        _sep(ti)
        ctk.CTkLabel(ti, text="Fond", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(8, 2))
        mr = ctk.CTkFrame(ti, fg_color="transparent")
        mr.pack(fill="x", pady=(0, 8))
        for val, label in [("photo", "📷 Photo floue"), ("gradient", "🌈 Dégradé"), ("custom", "📂 Image perso")]:
            ctk.CTkRadioButton(mr, text=label, variable=self.bg_mode, value=val,
                               command=self._on_bg_mode_changed,
                               fg_color=ACCENT, hover_color=ACCHOV,
                               text_color=TEXT, font=FONT_SM).pack(side="left", padx=(0, 14))

        self._photo_frame = ctk.CTkFrame(ti, fg_color="transparent")
        self._photo_frame.pack(fill="x")
        self._slider_row(self._photo_frame, "Flou",       self.background_blur,       0.0, 25.0)
        self._slider_row(self._photo_frame, "Luminosité", self.background_brightness, 0.20, 1.0)

        self._custom_bg_row = ctk.CTkFrame(self._photo_frame, fg_color="transparent")
        _cbg_btn = ctk.CTkFrame(self._custom_bg_row, fg_color="transparent")
        _cbg_btn.pack(fill="x", pady=(0, 2))
        _btn(_cbg_btn, "📂  Choisir l'image de fond", self._pick_bg_image,
             small=True, height=28).pack(side="left")
        self._bg_image_label = ctk.CTkLabel(
            self._custom_bg_row,
            text=self._bg_image_display_name(),
            text_color=MUTED, font=FONT_MU, anchor="w",
        )
        self._bg_image_label.pack(anchor="w", pady=(0, 4))
        _sep(self._photo_frame)
        _pf1 = ctk.CTkFrame(self._photo_frame, fg_color="transparent")
        _pf1.pack(fill="x", pady=(6, 2))
        ctk.CTkLabel(_pf1, text="🌊  Fond flottant", text_color=TEXT, font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(_pf1, text="", variable=self.floating_bg, command=self._on_setting_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(self._photo_frame, text="Dérive sinusoïdale réactive aux basses",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 4))
        _pf2 = ctk.CTkFrame(self._photo_frame, fg_color="transparent")
        _pf2.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(_pf2, text="🎞️  Micro-oscillation", text_color=TEXT, font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(_pf2, text="", variable=self.bg_oscillate, command=self._on_setting_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(self._photo_frame, text="Très légers mouvements synchronisés à la musique",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 8))

        self._gradient_frame = ctk.CTkFrame(ti, fg_color="transparent")
        self._gradient_frame.pack(fill="x")
        self._build_gradient_pickers(self._gradient_frame)
        _btn(self._gradient_frame, "🎲  Couleurs aléatoires", self._randomize_gradient_colors,
             small=True, height=28).pack(fill="x", pady=(6, 0))
        self._refresh_bg_mode_visibility()

        # ── ✨ Effets ──────────────────────────────────────────────────────────
        tx = mkscroll("✨")
        self._combo_row(tx, "Particules", self.particle_preset, list(PARTICLE_PRESETS.keys()))
        self._combo_row(tx, "Atmosphère", self.smoke_preset, list(SMOKE_PRESETS.keys()),
                        command=self._on_smoke_changed)
        self._smoke_color_frame = ctk.CTkFrame(tx, fg_color="transparent")
        self._smoke_color_frame.pack(fill="x")
        self._combo_row(self._smoke_color_frame, "Couleur", self.smoke_color,
                        list(SMOKE_COLORS.keys()))
        self._refresh_smoke_opts()

        # ── 📝 Texte ──────────────────────────────────────────────────────────
        tt = mkscroll("📝")
        tx_hdr = ctk.CTkFrame(tt, fg_color="transparent")
        tx_hdr.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(tx_hdr, text="📝  Texte", text_color=TEXT, font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(tx_hdr, text="Afficher", variable=self.show_text,
                      command=self._on_setting_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(tt, text="Artiste", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(4, 2))
        ctk.CTkEntry(tt, textvariable=self.artist_text,
                     placeholder_text="Artiste (optionnel)",
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_SM).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(tt, text="Titre", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w")
        ctk.CTkEntry(tt, textvariable=self.title_text,
                     placeholder_text="Titre (optionnel)",
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_SM).pack(fill="x", pady=(2, 4))
        self._text_preview_lbl = ctk.CTkLabel(tt, text="", text_color=ACCLT, font=FONT_MU, anchor="w")
        self._text_preview_lbl.pack(anchor="w", pady=(0, 2))
        if hasattr(self, "_text_trace_ids"):
            for var, tid in self._text_trace_ids:
                try: var.trace_remove("write", tid)
                except Exception: pass
        def _on_text_change(*_):
            self._update_text_preview()
            self._auto_fill_project_name()
        tid1 = self.artist_text.trace_add("write", _on_text_change)
        tid2 = self.title_text.trace_add("write",  _on_text_change)
        self._text_trace_ids = [(self.artist_text, tid1), (self.title_text, tid2)]
        self._update_text_preview()
        _sep(tt)
        ctk.CTkLabel(tt, text="Police", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(8, 2))
        font_names = get_font_names()
        ctk.CTkComboBox(tt, variable=self.font_name,
                        values=font_names,
                        command=lambda _: self._on_setting_changed(),
                        fg_color=SURF3, border_color=BORDER,
                        button_color=SURF2, button_hover_color=BORDER,
                        dropdown_fg_color=SURF2, text_color=TEXT,
                        font=FONT_SM).pack(fill="x", pady=(0, 6))
        self._slider_row(tt, "Taille texte", self.font_size_scale, 0.5, 2.0)
        _sep(tt)
        self._slider_row(tt, "Position X", self.text_x, 0.05, 0.95)
        self._slider_row(tt, "Position Y", self.text_y, 0.15, 0.92)
        _sep(tt)
        ctk.CTkLabel(tt, text="Ombre", text_color=TEXT, font=FONT_H2, anchor="w").pack(anchor="w", pady=(8, 2))
        self._slider_row(tt, "Intensité", self.shadow_intensity, 0.0, 1.0)
        _sh_row = ctk.CTkFrame(tt, fg_color="transparent")
        _sh_row.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(_sh_row, text="Couleur", text_color=MUTED, font=FONT_MU, anchor="w").pack(side="left")
        self._shadow_swatch = tk.Label(_sh_row, bg=self.shadow_color, width=3, relief="flat")
        self._shadow_swatch.pack(side="right", padx=(4, 0))
        self._shadow_hex_lbl = ctk.CTkLabel(_sh_row, text=self.shadow_color, text_color=TEXT, font=FONT_MU, width=65, anchor="e")
        self._shadow_hex_lbl.pack(side="right")
        _btn(_sh_row, "Choisir", self._pick_shadow_color, small=True, width=70, height=24).pack(side="right", padx=(0, 6))
        self._slider_row(tt, "Décalage X", self.shadow_offset_x, 0.0, 20.0)
        self._slider_row(tt, "Décalage Y", self.shadow_offset_y, 0.0, 20.0)

        # ── 📊 Spectre ─────────────────────────────────────────────────────────
        ts = mkscroll("📊")
        self._combo_row(ts, "Style", self.spectrum_style, SPECTRUM_STYLES)
        _sep(ts)
        self._slider_row(ts, "Taille",     self.spectrum_size, 0.55, 1.65)
        self._slider_row(ts, "Position Y", self.spectrum_y,   0.62, 0.95)
        _sep(ts)
        ctk.CTkLabel(ts, text="Couleur principale", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(8, 2))
        cr = ctk.CTkFrame(ts, fg_color="transparent")
        cr.pack(fill="x", pady=(0, 4))
        self._spec_swatch = tk.Label(cr, bg=self.spectrum_color, width=5, relief="flat",
                                     bd=1, highlightbackground=BORDER, highlightthickness=1)
        self._spec_swatch.pack(side="left", padx=(0, 6))
        self._spec_hex_lbl = ctk.CTkLabel(cr, text=self.spectrum_color,
                                           text_color=TEXT, font=FONT_MU, width=65, anchor="w")
        self._spec_hex_lbl.pack(side="left")
        _btn(cr, "Choisir", self._pick_spectrum_color, small=True, width=70, height=26).pack(side="left", padx=(6, 0))
        _btn(cr, "⬜", lambda: self._set_spectrum_color("#ffffff"), small=True, width=36, height=26).pack(side="left", padx=(4, 0))
        ar = ctk.CTkFrame(ts, fg_color="transparent")
        ar.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(ar, text="Auto depuis pochette", text_color=MUTED, font=FONT_MU, anchor="w").pack(side="left")
        ctk.CTkSwitch(ar, text="", variable=self.spectrum_color_auto,
                      command=self._on_spectrum_color_auto,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")

        # ── Update 7 — Spectre 3 couleurs ─────────────────────────────────────
        _sep(ts)
        tri_hdr = ctk.CTkFrame(ts, fg_color="transparent")
        tri_hdr.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(tri_hdr, text="🎨  Mode 3 couleurs", text_color=TEXT,
                     font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(tri_hdr, text="", variable=self.spectrum_tricolor,
                      command=self._on_tricolor_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(ts, text="Grave → Médiums → Aigus, chaque bande a sa couleur",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 6))

        # Color pickers mid + high — cachés si tricolor OFF
        self._tricolor_frame = ctk.CTkFrame(ts, fg_color="transparent")
        self._tricolor_frame.pack(fill="x", pady=(0, 4))
        for attr, label, swatch_attr, hex_attr, pick_fn, reset_fn in [
            ("spectrum_color_mid",  "Médiums (centre)",
             "_spec_swatch_mid",  "_spec_hex_mid",
             lambda: self._pick_spectrum_color_band("mid"),
             lambda: self._set_spectrum_color_band("mid", "#ffffff")),
            ("spectrum_color_high", "Aigus (droite)",
             "_spec_swatch_high", "_spec_hex_high",
             lambda: self._pick_spectrum_color_band("high"),
             lambda: self._set_spectrum_color_band("high", "#ffffff")),
        ]:
            ctk.CTkLabel(self._tricolor_frame, text=label, text_color=MUTED,
                         font=FONT_MU, anchor="w").pack(anchor="w", pady=(2, 0))
            row = ctk.CTkFrame(self._tricolor_frame, fg_color="transparent")
            row.pack(fill="x", pady=(0, 4))
            color_val = getattr(self, attr)
            sw = tk.Label(row, bg=color_val, width=5, relief="flat",
                          bd=1, highlightbackground=BORDER, highlightthickness=1)
            sw.pack(side="left", padx=(0, 6))
            hl = ctk.CTkLabel(row, text=color_val, text_color=TEXT, font=FONT_MU, width=65, anchor="w")
            hl.pack(side="left")
            setattr(self, swatch_attr, sw)
            setattr(self, hex_attr, hl)
            _btn(row, "Choisir", pick_fn, small=True, width=70, height=26).pack(side="left", padx=(6, 0))
            _btn(row, "⬜", reset_fn, small=True, width=36, height=26).pack(side="left", padx=(4, 0))
        self._refresh_tricolor_opts()

        # Mode réactif
        react_row = ctk.CTkFrame(ts, fg_color="transparent")
        react_row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(react_row, text="⚡  Flash sur les beats", text_color=TEXT,
                     font=FONT_H2, anchor="w").pack(side="left")
        ctk.CTkSwitch(react_row, text="", variable=self.spectrum_reactive,
                      command=self._on_setting_changed,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT, width=44, height=22).pack(side="right")
        ctk.CTkLabel(ts, text="Le spectre flashe blanc sur chaque kick",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 4))

        # ── 🚀 Export ──────────────────────────────────────────────────────────
        te = mkscroll("🚀")
        ctk.CTkLabel(te, text="Dossier de sortie", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(8, 2))
        rr = ctk.CTkFrame(te, fg_color="transparent")
        rr.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(rr, textvariable=self.project_root_var,
                     text_color=MUTED, font=FONT_MU, anchor="w", wraplength=220).pack(side="left", fill="x", expand=True)
        _btn(rr, "...", self._choose_project_root, small=True, width=36, height=26).pack(side="right")
        ctk.CTkLabel(te, text="Nom du projet *", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w")
        self._proj_name_entry = ctk.CTkEntry(te, textvariable=self.project_name_var,
                                              placeholder_text="ex : MonSon_RageMix  (obligatoire)",
                                              fg_color=SURF3, border_color=BORDER,
                                              text_color=TEXT, font=FONT_SM)
        self._proj_name_entry.pack(fill="x", pady=(2, 2))
        self._auto_fill_project_name()   # remplir depuis Artiste + Titre si dispo
        self._proj_name_error = ctk.CTkLabel(te, text="", text_color=DANGER, font=FONT_MU, anchor="w")
        self._proj_name_error.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(te, text="Preview départ (sec)", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w")
        prow = ctk.CTkFrame(te, fg_color="transparent")
        prow.pack(fill="x", pady=(2, 10))
        ctk.CTkEntry(prow, textvariable=self.preview_start,
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_SM, width=80).pack(side="left")
        _btn(prow, "Analyser", self._prepare_preview, small=True, width=90, height=28).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(te, text="Type d'export", text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(0, 6))

        # Grille 2×2 de cards — sélection par clic
        self._duration_cards: dict[str, tuple] = {}

        _modes = [
            ("SHORT",    "📱", "SHORT",    "1080 × 1920",  "1 min",      ACCLT),
            ("VERTICAL", "📱", "VERTICAL", "1080 × 1920",  "Complet",    "#a855f7"),
            ("COMPLET",  "🎬", "COMPLET",  "1920 × 1080",  "Complet",    SUCCESS),
            ("DUAL",     "⚡", "DUAL",     "16:9 + 9:16",  "2 fichiers", ACCENT),
        ]

        _grid = ctk.CTkFrame(te, fg_color="transparent")
        _grid.pack(fill="x", pady=(0, 8))
        _grid.columnconfigure(0, weight=1)
        _grid.columnconfigure(1, weight=1)

        for idx, (val, icon, title, res, dur, badge_color) in enumerate(_modes):
            r, c = divmod(idx, 2)
            card = ctk.CTkFrame(_grid, fg_color=SURF3, corner_radius=10,
                                border_color=BORDER, border_width=1)
            card.grid(row=r, column=c,
                      padx=(0, 3) if c == 0 else (3, 0),
                      pady=(0, 3) if r == 0 else (3, 0),
                      sticky="nsew")

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=11, pady=10)

            # Ligne haute : icône + badge durée
            top_row = ctk.CTkFrame(inner, fg_color="transparent")
            top_row.pack(fill="x")
            icon_lbl = ctk.CTkLabel(top_row, text=icon,
                                    font=ctk.CTkFont("Segoe UI", 18),
                                    text_color=badge_color)
            icon_lbl.pack(side="left")
            dur_lbl = ctk.CTkLabel(top_row, text=dur,
                                   fg_color=SURF2, corner_radius=5,
                                   font=ctk.CTkFont("Segoe UI", 8, "bold"),
                                   text_color=MUTED)
            dur_lbl.pack(side="right", ipadx=5, ipady=2)

            # Titre
            title_lbl = ctk.CTkLabel(inner, text=title,
                                     text_color=MUTED,
                                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                                     anchor="w")
            title_lbl.pack(anchor="w", pady=(4, 0))

            # Résolution
            res_lbl = ctk.CTkLabel(inner, text=res,
                                   text_color="#383838",
                                   font=ctk.CTkFont("Segoe UI", 8),
                                   anchor="w")
            res_lbl.pack(anchor="w")

            # Click sur toute la card
            def _click(e, v=val): self._set_export_mode(v)
            for w in (card, inner, top_row, icon_lbl, dur_lbl, title_lbl, res_lbl):
                try:
                    w.bind("<Button-1>", _click)
                    w.configure(cursor="hand2")
                except Exception:
                    pass

            self._duration_cards[val] = (card, title_lbl, badge_color)

        self._refresh_mode_btns()

        ctk.CTkFrame(te, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", pady=(10, 0))
        _btn(te, "  ▶  GÉNÉRER", self._start_export,
             accent=True, height=50, font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(fill="x", pady=(10, 0))

        # Tout est construit — retirer le masque et rafraîchir en une seule passe
        self.main.update_idletasks()
        try:
            _build_cover.destroy()
        except Exception:
            pass
        self.main.update_idletasks()

        self._prepare_preview()

    # ── Fond dégradé UI ───────────────────────────────────────────────────────

    def _current_visual_snapshot(self) -> dict:
        """Capture tous les réglages visuels actuels pour un preset."""
        return {
            "particle_preset":       self.particle_preset.get(),
            "smoke_preset":          self.smoke_preset.get(),
            "smoke_color":           self.smoke_color.get(),
            "spectrum_style":        self.spectrum_style.get(),
            "spectrum_size":         float(self.spectrum_size.get()),
            "spectrum_y":            float(self.spectrum_y.get()),
            "image_zoom":            float(self.image_zoom.get()),
            "pulse_strength":        float(self.pulse_strength.get()),
            "vinyl_mode":            bool(self.vinyl_mode.get()),
            "vinyl_black":           bool(self.vinyl_black.get()),
            "spectrum_color":        self.spectrum_color,
            "spectrum_color_auto":   bool(self.spectrum_color_auto.get()),
            "spectrum_color_mid":    self.spectrum_color_mid,
            "spectrum_color_high":   self.spectrum_color_high,
            "spectrum_tricolor":     bool(self.spectrum_tricolor.get()),
            "spectrum_reactive":     bool(self.spectrum_reactive.get()),
            "floating_bg":           bool(self.floating_bg.get()),
            "bg_oscillate":          bool(self.bg_oscillate.get()),
            "background_blur":       float(self.background_blur.get()),
            "background_brightness": float(self.background_brightness.get()),
            "bg_mode":               self.bg_mode.get(),
            "bg_image_path":         self.bg_image_path,
            "gradient_top":          self.gradient_top,
            "gradient_bottom":       self.gradient_bottom,
            "show_text":             bool(self.show_text.get()),
            "font_name":             self.font_name.get(),
            "font_size_scale":       float(self.font_size_scale.get()),
            "subtitle_text":         self.subtitle_text.get().strip(),
            "shadow_intensity":      float(self.shadow_intensity.get()),
            "shadow_color":          self.shadow_color,
            "shadow_offset_x":       float(self.shadow_offset_x.get()),
            "shadow_offset_y":       float(self.shadow_offset_y.get()),
        }

    def _toggle_favorite(self, name: str):
        if name in self.user_preset_favorites:
            self.user_preset_favorites.discard(name)
        else:
            self.user_preset_favorites.add(name)
        self._persist_now()
        self._refresh_presets_library()

    def _open_settings_window(self):
        win = ctk.CTkToplevel(self)
        win.title("Réglages")
        win.configure(fg_color=BG)
        win.geometry("560x600")
        win.minsize(520, 560)
        win.resizable(True, True)
        win.grab_set()

        # ── Scrollable container ──────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(win, fg_color=BG, scrollbar_button_color=SURF3)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Header
        hdr_row = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr_row.pack(fill="x", padx=28, pady=(22, 4))
        ctk.CTkLabel(hdr_row, text="Réglages", font=FONT_H1, text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hdr_row, text=f"v{VERSION}", text_color=ACCLT,
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     fg_color=SURF2, corner_radius=6).pack(side="right", padx=(0, 4), ipadx=8, ipady=4)
        ctk.CTkLabel(scroll, text="TAC MP4 Studio — Générateur de vidéos musicales réactives",
                     text_color=MUTED, font=FONT_MU).pack(anchor="w", padx=28, pady=(0, 18))

        ctk.CTkFrame(scroll, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", padx=28)

        # ── Raccourcis clavier ────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Raccourcis clavier", text_color=ACCLT,
                     font=FONT_SEC).pack(anchor="w", padx=28, pady=(18, 8))

        shortcuts = [
            ("Espace",       "Play / Pause la preview audio"),
            ("R",            "Recharger la preview"),
            ("F11",          "Ouvrir la preview en plein écran"),
            ("Échap",        "Fermer le plein écran / Retour accueil"),
            ("Double-clic",  "Ouvrir la preview en plein écran"),
        ]
        for key, desc in shortcuts:
            row = ctk.CTkFrame(scroll, fg_color=SURF2, corner_radius=8)
            row.pack(fill="x", padx=28, pady=3)
            ctk.CTkLabel(row, text=key, text_color=ACCLT, font=FONT_SEC,
                         width=130, anchor="w").pack(side="left", padx=14, pady=9)
            ctk.CTkLabel(row, text=desc, text_color=TEXT, font=FONT_SM,
                         anchor="w").pack(side="left", padx=(0, 14), fill="x", expand=True)

        ctk.CTkFrame(scroll, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=28, pady=(18, 0))

        # ── Réseaux sociaux ───────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Retrouve-nous", text_color=ACCLT,
                     font=FONT_SEC).pack(anchor="w", padx=28, pady=(18, 8))

        socials = [
            ("🟣  Twitch — DoktorP3st",       "https://www.twitch.tv/doktorp3st"),
            ("🟣  Twitch — Paglorieux",        "https://www.twitch.tv/paglorieux"),
            ("🔴  YouTube — TheAuraliaCryia",  "https://www.youtube.com/@TheAuraliaCryia"),
            ("🔴  YouTube — Paglorieux",       "https://www.youtube.com/@Paglorieux"),
        ]
        for label, url in socials:
            row = ctk.CTkFrame(scroll, fg_color=SURF2, corner_radius=8)
            row.pack(fill="x", padx=28, pady=3)
            ctk.CTkLabel(row, text=label, text_color=TEXT, font=FONT_SM,
                         anchor="w").pack(side="left", padx=14, pady=9, fill="x", expand=True)
            def _open(u=url):
                import webbrowser
                webbrowser.open(u)
            ctk.CTkButton(row, text="Ouvrir ↗", command=_open,
                          fg_color="transparent", hover_color=SURF3,
                          text_color=ACCLT, font=FONT_MU,
                          width=80, height=28, corner_radius=6).pack(side="right", padx=10)

        ctk.CTkFrame(scroll, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=28, pady=(18, 0))

        # ── Données ───────────────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="🗑  Données", text_color=ACCLT,
                     font=FONT_SEC).pack(anchor="w", padx=28, pady=(18, 4))
        ctk.CTkLabel(scroll,
                     text="Purge sélective — coche ce que tu veux effacer, rien "
                          "n'est supprimé sans confirmation.",
                     text_color=MUTED, font=FONT_MU, justify="left",
                     anchor="w").pack(anchor="w", padx=28, pady=(0, 8))

        purge_vars: dict[str, tk.BooleanVar] = {}
        purge_options = [
            ("history", "🎬 Historique de génération",
             "Métadonnées des créations — les fichiers vidéo restent sur le disque."),
            ("youtube_history", "📺 Historique de publication YouTube",
             "Anti-doublon local — les vidéos restent en ligne sur YouTube."),
            ("files", "💾 Fichiers vidéo générés (dossier Creations)",
             "Supprime les fichiers eux-mêmes du disque — irréversible."),
            ("logs", "📄 Journal de l'application (tac.log)",
             "Fichier de diagnostic technique."),
        ]
        for key, label, desc in purge_options:
            var = tk.BooleanVar(value=False)
            purge_vars[key] = var
            row = ctk.CTkFrame(scroll, fg_color=SURF2, corner_radius=8)
            row.pack(fill="x", padx=28, pady=3)
            ctk.CTkCheckBox(row, text=label, variable=var, text_color=TEXT, font=FONT_SM,
                            fg_color=ACCENT, hover_color=ACCHOV, border_color=BORDER,
                            checkbox_width=20, checkbox_height=20).pack(
                anchor="w", padx=14, pady=(9, 0))
            ctk.CTkLabel(row, text=desc, text_color=MUTED, font=FONT_MU,
                         anchor="w").pack(anchor="w", padx=(38, 14), pady=(0, 9))

        _btn(scroll, "🗑  Purger la sélection",
             lambda: self._confirm_purge_data(purge_vars),
             danger=True, height=38).pack(fill="x", padx=28, pady=(4, 0))

        ctk.CTkFrame(scroll, height=1, fg_color=BORDER, corner_radius=0).pack(
            fill="x", padx=28, pady=(18, 0))

        # ── À propos ──────────────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="À propos", text_color=ACCLT,
                     font=FONT_SEC).pack(anchor="w", padx=28, pady=(18, 6))
        about_text = (
            "TAC MP4 Studio est un générateur de vidéos musicales réactives,\n"
            "open source et gratuit. Alternative à Tuneform, 100% offline.\n\n"
            "Développé par DoktorP3st · Licence MIT"
        )
        ctk.CTkLabel(scroll, text=about_text, text_color=MUTED, font=FONT_MU,
                     justify="left", anchor="w").pack(anchor="w", padx=28, pady=(0, 18))

        # Fermer
        _btn(scroll, "Fermer", win.destroy, width=130, height=36, small=True).pack(pady=(4, 24))

    # ══════════════════════════════════════════════════════════════════════════
    # DONNÉES — purge sélective
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _data_folder_size(path) -> int:
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    def _confirm_purge_data(self, purge_vars: dict) -> None:
        selected = [k for k, v in purge_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Données", "Coche au moins une option à purger.")
            return

        labels = {
            "history":         "Historique de génération",
            "youtube_history": "Historique de publication YouTube",
            "files":           "Fichiers vidéo générés (dossier Creations)",
            "logs":            "Journal de l'application",
        }
        consequences = {
            "history":         "les créations disparaissent de l'Historique (fichiers conservés)",
            "youtube_history": "un futur \"upload dossier\" pourrait republier un fichier déjà envoyé",
            "files":           "les fichiers vidéo sont supprimés du disque, définitivement",
            "logs":            "les traces de diagnostic récentes sont perdues",
        }
        lines = [f"• {labels[k]} — {consequences[k]}" for k in selected]

        size_note = ""
        if "files" in selected:
            size = self._data_folder_size(self.project_root)
            size_note = f"\n\n💾 Espace concerné : {_format_size(size)}"

        if not messagebox.askyesno(
            "⚠ Confirmer la purge",
            "Tu es sur le point d'effacer :\n\n" + "\n".join(lines) + size_note +
            "\n\n⚠ Action irréversible. Confirmer ?",
            icon="warning",
        ):
            return

        done = []
        if "history" in selected:
            self.history.clear()
            done.append("historique de génération")
        if "youtube_history" in selected:
            self.youtube_history.clear()
            done.append("historique YouTube")
        if "files" in selected:
            self._purge_generated_files()
            done.append("fichiers vidéo")
        if "logs" in selected:
            from app.logger import purge_logs
            purge_logs()
            done.append("journal")

        self._persist_now()
        messagebox.showinfo("Données", "Purgé : " + ", ".join(done) + ".")

    def _purge_generated_files(self) -> None:
        root = Path(self.project_root)
        if not root.exists():
            return
        for child in root.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink()
            except OSError:
                pass

    def _capture_hd_frame(self):
        """Rend une frame unique en résolution réelle (1920×1080 ou 1080×1920)
        et l'affiche dans une fenêtre dédiée — aperçu exact du rendu final."""
        if not self.audio_path or not self.image_path:
            messagebox.showinfo("Rendu HD", "Charge une musique et une pochette d'abord.")
            return
        if not self.preview_features:
            messagebox.showinfo("Rendu HD", "Lance d'abord la preview (⟲ Recharger).")
            return

        self._set_status("Rendu HD en cours...", WARN)
        self.update_idletasks()

        _hd_mode = self.export_mode.get()
        is_vert  = _hd_mode in ("SHORT", "VERTICAL")
        out_w    = 1080 if is_vert else 1920
        out_h    = 1920 if is_vert else 1080

        s = self._current_settings(preview=False, short_mode=(_hd_mode == "SHORT"))
        s.output_path = ""

        def worker():
            try:
                bg, cover = load_cover_image(
                    s.image_path, s.background_blur, s.image_zoom,
                    out_w, out_h,
                    bg_mode=s.bg_mode,
                    gradient_top=s.gradient_top,
                    gradient_bottom=s.gradient_bottom,
                    background_brightness=s.background_brightness,
                    bg_image_path=s.bg_image_path,
                )
                # Utilise le frame courant de la preview
                i = self.preview_index % len(self.preview_features["rms"])
                metrics = {k: float(self.preview_features[k][i])
                           for k in ("rms", "kick", "bass", "mid", "high")}
                raw_f = self.preview_features["raw"][i] if "raw" in self.preview_features else None

                frame, _, _, _, _ = render_frame(
                    bg, cover, [], [],
                    self.preview_features["spec"][:, i],
                    metrics, np.zeros(84, dtype=np.float32),
                    s, vinyl_angle=self.vinyl_angle,
                    frame_idx=i, raw_frame=raw_f,
                )

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                self.after(0, lambda: self._show_hd_window(img, out_w, out_h))
                self.after(0, lambda: self._set_status("Rendu HD prêt", SUCCESS))
            except Exception as exc:
                msg = str(exc)
                self.after(0, lambda: messagebox.showerror("Rendu HD", msg))
                self.after(0, lambda: self._set_status("Erreur rendu HD", DANGER))

        threading.Thread(target=worker, daemon=True).start()

    def _show_hd_window(self, img: Image.Image, out_w: int, out_h: int):
        """Affiche l'image HD dans une fenêtre flottante avec zoom adaptatif."""
        win = ctk.CTkToplevel(self)
        win.title(f"Rendu HD — {out_w}×{out_h}  (fermer pour continuer)")
        win.configure(fg_color="#050505")
        win.attributes("-topmost", True)

        # Taille max = 85% de l'écran
        sw = int(self.winfo_screenwidth()  * 0.85)
        sh = int(self.winfo_screenheight() * 0.85)
        ratio = min(sw / out_w, sh / out_h)
        disp_w = int(out_w * ratio)
        disp_h = int(out_h * ratio)

        win.geometry(f"{disp_w}x{disp_h + 60}")

        # Image redimensionnée pour l'affichage
        disp_img = img.resize((disp_w, disp_h), Image.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=disp_img, dark_image=disp_img,
                               size=(disp_w, disp_h))
        ctk.CTkLabel(win, image=ctk_img, text="").pack()

        # Barre basse : résolution + bouton sauvegarder
        bar = ctk.CTkFrame(win, fg_color="#0d0d0d", height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text=f"Aperçu exact · {out_w}×{out_h}",
                     text_color=MUTED, font=FONT_MU).pack(side="left", padx=16, pady=18)

        def save_png():
            from tkinter import filedialog as _fd
            path = _fd.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG", "*.png")],
                title="Enregistrer le rendu HD",
                initialfile=f"render_hd_{out_w}x{out_h}.png",
            )
            if path:
                img.save(path)
                self._set_status(f"Sauvegardé : {Path(path).name}", SUCCESS)

        _btn(bar, "💾  Sauvegarder PNG", save_png,
             accent=True, small=True, height=32, width=160).pack(side="right", padx=16, pady=14)
        _btn(bar, "✕  Fermer", win.destroy,
             small=True, height=32, width=90).pack(side="right", padx=(0, 8), pady=14)

    def _auto_fill_project_name(self):
        """Remplit auto le nom de projet avec Artiste - Titre si le champ est vide."""
        try:
            artist = self.artist_text.get().strip()
            title  = self.title_text.get().strip()
        except Exception:
            return
        if artist and title:
            auto = f"{artist} - {title}"
        elif artist:
            auto = artist
        elif title:
            auto = title
        else:
            return
        current = self.project_name_var.get().strip()
        last_auto = getattr(self, "_last_auto_proj", "")
        if not current or current == last_auto:
            self._last_auto_proj = auto
            self.project_name_var.set(auto)

    def _update_preview_layout(self):
        """Conservé pour compatibilité — logique déplacée dans _tick_preview."""
        pass

    @staticmethod
    def _short_name(path, maxlen=35):
        if not path:
            return "—"
        name = Path(path).name
        return name if len(name) <= maxlen else "…" + name[-(maxlen - 1):]

    def _set_export_mode(self, val):
        self.export_mode.set(val)
        self._refresh_mode_btns()
        self._schedule_persist()

    def _refresh_mode_btns(self):
        sel = self.export_mode.get()
        if hasattr(self, "_duration_cards"):
            for val, (card, title_lbl, badge_color) in self._duration_cards.items():
                if val == sel:
                    card.configure(fg_color="#0e0a1a", border_color=badge_color, border_width=2)
                    title_lbl.configure(text_color=badge_color)
                else:
                    card.configure(fg_color=SURF3, border_color=BORDER, border_width=1)
                    title_lbl.configure(text_color=MUTED)
            return
        # Fallback ancien système CTkButton
        if hasattr(self, "_duration_btns"):
            for val, btn in self._duration_btns.items():
                if val == sel:
                    btn.configure(fg_color=ACCENT, hover_color=ACCHOV, text_color=TEXT)
                else:
                    btn.configure(fg_color=SURF3, hover_color=SURF2, text_color=MUTED)

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIG
    # ══════════════════════════════════════════════════════════════════════════

    def _schedule_persist(self):
        if self._persist_job:
            self.after_cancel(self._persist_job)
        self._persist_job = self.after(600, self._persist_now)

    def _persist_now(self):
        self._persist_job = None
        self.config_data["project_root"] = self.project_root
        self.config_data["history"]      = self.history
        self.config_data["turbo_v2_history"] = self.turbo_v2_history
        self.config_data["turbo_v2_last_folder"] = getattr(self, "_turbo_v2_last_folder", "")
        self.config_data["youtube_profiles"] = self.youtube_profiles
        self.config_data["youtube_history"] = self.youtube_history
        self.config_data["youtube_last_scheduled_date"] = self.youtube_last_scheduled_date
        self.config_data["settings"] = {
            "title_text":       self.title_text.get(),
            "artist_text":      self.artist_text.get(),
            "global_preset":    self.global_preset.get(),
            "particle_preset":  self.particle_preset.get(),
            "smoke_preset":     self.smoke_preset.get(),
            "smoke_color":      self.smoke_color.get(),
            "spectrum_style":   self.spectrum_style.get(),
            "spectrum_size":    self.spectrum_size.get(),
            "spectrum_y":       self.spectrum_y.get(),
            "image_zoom":       self.image_zoom.get(),
            "pulse_strength":   self.pulse_strength.get(),
            "preview_start":    self.preview_start.get(),
            "window_geometry":  self.geometry(),
            "text_x":           self.text_x.get(),
            "text_y":           self.text_y.get(),
            "export_mode":      self.export_mode.get(),
            "bg_mode":          self.bg_mode.get(),
            "bg_image_path":    self.bg_image_path,
            "gradient_top":     self.gradient_top,
            "gradient_bottom":  self.gradient_bottom,
            "vinyl_mode":       bool(self.vinyl_mode.get()),
            "vinyl_black":      bool(self.vinyl_black.get()),
            "spectrum_color":       self.spectrum_color,
            "spectrum_color_auto":  bool(self.spectrum_color_auto.get()),
            "floating_bg":          bool(self.floating_bg.get()),
            "bg_oscillate":         bool(self.bg_oscillate.get()),
            "background_blur":        float(self.background_blur.get()),
            "background_brightness":  float(self.background_brightness.get()),
            "spectrum_color_mid":   self.spectrum_color_mid,
            "spectrum_color_high":  self.spectrum_color_high,
            "spectrum_tricolor":    bool(self.spectrum_tricolor.get()),
            "spectrum_reactive":    bool(self.spectrum_reactive.get()),
            "font_name":            self.font_name.get(),
            "show_text":            bool(self.show_text.get()),
            "font_size_scale":      self.font_size_scale.get(),
            "subtitle_text":        self.subtitle_text.get(),
            "shadow_intensity":     self.shadow_intensity.get(),
            "shadow_color":         self.shadow_color,
            "shadow_offset_x":      self.shadow_offset_x.get(),
            "shadow_offset_y":      self.shadow_offset_y.get(),
            "test_audio_path":      self.test_audio_path,
            "test_image_path":      self.test_image_path,
        }
        self.config_data["user_presets"] = self.user_presets
        self.config_data["user_preset_favorites"] = list(self.user_preset_favorites)
        self.config_data["hidden_builtin_presets"] = list(self.hidden_builtin_presets)
        try:
            save_config(self.config_data)
        except ConfigError as exc:
            log_exception(exc, context="_persist_now")
            messagebox.showerror("Configuration", exc.message)

    def _apply_global_preset(self):
        p = GLOBAL_PRESETS[self.global_preset.get()]
        self.particle_preset.set(p["particle_preset"])
        self.smoke_preset.set(p["smoke_preset"])
        self.smoke_color.set(p["smoke_color"])
        self.spectrum_style.set(p["spectrum_style"])
        self.spectrum_size.set(p["spectrum_size"])
        self.spectrum_y.set(p["spectrum_y"])
        self.image_zoom.set(p["image_zoom"])
        self.pulse_strength.set(p["pulse_strength"])
        # Champs Update 4 + 5
        if "vinyl_mode" in p:
            self.vinyl_mode.set(p["vinyl_mode"])
        if "vinyl_black" in p:
            self.vinyl_black.set(p["vinyl_black"])
        if "spectrum_color" in p:
            self._set_spectrum_color(p["spectrum_color"])
        if "floating_bg" in p:
            self.floating_bg.set(p["floating_bg"])
        if "bg_oscillate" in p:
            self.bg_oscillate.set(p["bg_oscillate"])
        if "background_blur" in p:        self.background_blur.set(float(p["background_blur"]))
        if "background_brightness" in p:  self.background_brightness.set(float(p["background_brightness"]))
        if "bg_mode" in p:
            self.bg_mode.set(p["bg_mode"])
            self._refresh_gradient_visibility()
        if "bg_image_path" in p:
            self.bg_image_path = p["bg_image_path"]
            if hasattr(self, "_bg_image_label"):
                self._bg_image_label.configure(text=self._bg_image_display_name())
        if "gradient_top" in p:
            self.gradient_top = p["gradient_top"]
            self._update_gradient_ui()
        if "gradient_bottom" in p:
            self.gradient_bottom = p["gradient_bottom"]
            self._update_gradient_ui()
        self._schedule_persist()
        if not self.is_rendering:
            self._reload_visuals_only()

    # ══════════════════════════════════════════════════════════════════════════
    # FICHIERS
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_audio_filename(self, path: str) -> None:
        """Extrait Artiste / Titre depuis le nom de fichier audio."""
        stem = Path(path).stem
        if " - " in stem:
            left, right = stem.split(" - ", 1)
            self.artist_text.set(left.strip())
            self.title_text.set(right.strip())
        else:
            self.artist_text.set("")
            self.title_text.set(stem.strip())

    def _pick_audio(self):
        path = filedialog.askopenfilename(
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("Tous", "*.*")])
        if path:
            try:
                if not Path(path).exists():
                    raise AudioImportError("Fichier audio introuvable.", detail=f"path={path!r}")
                ext = Path(path).suffix.lower()
                if ext not in AUDIO_EXTS:
                    raise AudioImportError("Format audio non supporté.", detail=f"ext={ext!r}")
            except AudioImportError as exc:
                log_exception(exc, context="_pick_audio")
                messagebox.showerror("Audio", exc.message)
                return
            self.audio_path = path
            self._parse_audio_filename(path)
            self.show_step_image()

    def _pick_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("Tous", "*.*")])
        if path:
            try:
                if not Path(path).exists():
                    raise ImageImportError("Fichier image introuvable.", detail=f"path={path!r}")
                ext = Path(path).suffix.lower()
                if ext not in IMAGE_EXTS:
                    raise ImageImportError("Format d'image non supporté.", detail=f"ext={ext!r}")
                from PIL import Image as _PilImage
                _PilImage.open(path).verify()
            except ImageImportError as exc:
                log_exception(exc, context="_pick_image")
                messagebox.showerror("Image", exc.message)
                return
            except Exception as exc:
                img_err = ImageImportError(
                    "Impossible de lire le fichier image.",
                    detail=str(exc),
                )
                log_exception(img_err, context="_pick_image")
                messagebox.showerror("Image", img_err.message)
                return
            self.image_path = path
            self.show_editor()

    def _bg_image_display_name(self) -> str:
        if self.bg_image_path and Path(self.bg_image_path).exists():
            return Path(self.bg_image_path).name
        return "Aucune image sélectionnée"

    def _pick_bg_image(self):
        path = filedialog.askopenfilename(
            title="Image de fond",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tous", "*.*")])
        if not path:
            return
        try:
            if not Path(path).exists():
                raise ImageImportError("Fichier image introuvable.", detail=f"path={path!r}")
            ext = Path(path).suffix.lower()
            if ext not in IMAGE_EXTS:
                raise ImageImportError("Format d'image non supporté.", detail=f"ext={ext!r}")
            from PIL import Image as _PilImage
            _PilImage.open(path).verify()
        except ImageImportError as exc:
            log_exception(exc, context="_pick_bg_image")
            messagebox.showerror("Image de fond", exc.message)
            return
        except Exception as exc:
            img_err = ImageImportError("Impossible de lire le fichier image.", detail=str(exc))
            log_exception(img_err, context="_pick_bg_image")
            messagebox.showerror("Image de fond", img_err.message)
            return
        self.bg_image_path = path
        if hasattr(self, "_bg_image_label"):
            self._bg_image_label.configure(text=self._bg_image_display_name())
        self._on_setting_changed()

