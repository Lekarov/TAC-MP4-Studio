"""TurboMixin — méthodes du mode Turbo (export par lot).

Extrait de app/ui/app.py.
"""
from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.config import safe_name
from app.exporter import render_video, open_file
from app.models import RenderSettings
from app.presets import WIDTH, HEIGHT, SHORT_WIDTH, SHORT_HEIGHT


class TurboMixin:

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO — sélection fichiers
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_pick_image(self):
        path = filedialog.askopenfilename(
            title="Pochette globale Turbo",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tous", "*.*")])
        if not path:
            return
        self._turbo_image = path
        if hasattr(self, "_turbo_img_var"):
            self._turbo_img_var.set(Path(path).name)

    def _turbo_pick_bg(self):
        path = filedialog.askopenfilename(
            title="Image de fond Turbo",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tous", "*.*")])
        if not path:
            return
        self._turbo_bg_image = path
        if hasattr(self, "_turbo_bg_var"):
            self._turbo_bg_var.set(Path(path).name)

    def _turbo_pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Fichiers audio pour Turbo",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma"), ("Tous", "*.*")])
        if paths:
            self._turbo_add_paths(list(paths))

    def _turbo_stop_fn(self):
        from app.ui.app import WARN
        self._turbo_stop = True
        self._set_status("⏹ Turbo stoppé", WARN)

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO — rendu par lot
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_build_settings(self, preset: dict, audio: str, image: str, output: str,
                               title: str, artist: str, is_short: bool,
                               is_vertical: bool = False, **_ignored):
        if is_short:
            out_w, out_h, dur = SHORT_WIDTH, SHORT_HEIGHT, 60.0
        elif is_vertical:
            out_w, out_h, dur = SHORT_WIDTH, SHORT_HEIGHT, None
        else:
            out_w, out_h, dur = WIDTH, HEIGHT, None

        bg_mode = preset.get("bg_mode", "photo")
        bg_img  = self._turbo_bg_image
        if bg_img and Path(bg_img).exists():
            bg_mode = "custom"

        return RenderSettings(
            audio_path=audio, image_path=image, output_path=output,
            title_text=title, artist_text=artist,
            duration_limit=dur, start_offset=0.0,
            particle_preset=preset.get("particle_preset", "Premium"),
            smoke_preset=preset.get("smoke_preset", "Cinématique"),
            smoke_color=preset.get("smoke_color", "Blanc"),
            spectrum_style=preset.get("spectrum_style", "Cercle radial"),
            spectrum_size=float(preset.get("spectrum_size", 1.05)),
            spectrum_y=float(preset.get("spectrum_y", 0.90)),
            image_zoom=float(preset.get("image_zoom", 1.00)),
            pulse_strength=float(preset.get("pulse_strength", 1.10)),
            background_blur=float(preset.get("background_blur", 8.0)),
            background_brightness=float(preset.get("background_brightness", 0.85)),
            output_width=out_w, output_height=out_h,
            bg_mode=bg_mode,
            bg_image_path=bg_img or preset.get("bg_image_path", ""),
            gradient_top=preset.get("gradient_top", "#1a1a2e"),
            gradient_bottom=preset.get("gradient_bottom", "#0f3460"),
            vinyl_mode=bool(preset.get("vinyl_mode", False)),
            vinyl_black=bool(preset.get("vinyl_black", False)),
            spectrum_color=preset.get("spectrum_color", "#ffffff"),
            spectrum_color_auto=bool(preset.get("spectrum_color_auto", False)),
            floating_bg=bool(preset.get("floating_bg", False)),
            bg_oscillate=bool(preset.get("bg_oscillate", False)),
            spectrum_color_mid=preset.get("spectrum_color_mid", "#ffffff"),
            spectrum_color_high=preset.get("spectrum_color_high", "#ffffff"),
            spectrum_tricolor=bool(preset.get("spectrum_tricolor", False)),
            spectrum_reactive=bool(preset.get("spectrum_reactive", False)),
            font_name=preset.get("font_name", "Défaut"),
            show_text=bool(preset.get("show_text", True)),
            font_size_scale=float(preset.get("font_size_scale", 1.0)),
            subtitle_text=preset.get("subtitle_text", ""),
            shadow_intensity=float(preset.get("shadow_intensity", 0.5)),
            shadow_color=preset.get("shadow_color", "#000000"),
            shadow_offset_x=float(preset.get("shadow_offset_x", 4.0)),
            shadow_offset_y=float(preset.get("shadow_offset_y", 4.0)),
        )

    def _turbo_start(self):
        from app.ui.app import WARN, DANGER, SUCCESS
        if self.is_rendering:
            return
        pending = [it for it in self._turbo_queue if not it["status"].startswith("✅")]
        if not pending:
            messagebox.showwarning("Turbo", "Aucun fichier en attente.")
            return

        preset_name = self._turbo_preset_var.get() if hasattr(self, "_turbo_preset_var") else ""
        preset = self.user_presets.get(preset_name, {})
        fmt = self._turbo_format_var.get() if hasattr(self, "_turbo_format_var") else "COMPLET"
        is_short    = (fmt == "SHORT")
        is_vertical = (fmt == "VERTICAL")

        self._turbo_stop = False
        self.is_rendering = True
        self._set_status(f"⚡ Turbo — 0/{len(pending)}", WARN)

        def _make_progress_cb(i):
            def _cb(txt):
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)%", txt)
                if m:
                    label = f"{float(m.group(1)):.0f}%"
                elif "Encodage" in txt:
                    label = "Encodage…"
                elif "Analyse" in txt:
                    label = "Analyse…"
                else:
                    return
                self.after(0, lambda lbl=label, it=i: it["_status_lbl"] and
                           it["_status_lbl"].configure(text=lbl, text_color=WARN))
            return _cb

        def worker():
            done = 0
            for item in pending:
                if self._turbo_stop:
                    break
                audio = item["audio"]
                image = item.get("image") or self._turbo_image
                if not image or not Path(image).exists():
                    self.after(0, lambda i=item: i["_status_lbl"] and
                               i["_status_lbl"].configure(text="❌ Manquante", text_color=DANGER))
                    item["status"] = "❌ Image manquante"
                    continue

                title  = item["title_var"].get().strip()  or Path(audio).stem
                artist = item["artist_var"].get().strip()
                safe   = safe_name((f"{artist} - {title}") if artist else title)
                proj_dir = Path(self.project_root) / "Turbo" / safe
                proj_dir.mkdir(parents=True, exist_ok=True)
                output = str(proj_dir / f"{safe}.mp4")

                self.after(0, lambda i=item: i["_status_lbl"] and
                           i["_status_lbl"].configure(text="0%", text_color=WARN))

                try:
                    settings = self._turbo_build_settings(
                        preset=preset, audio=audio, image=image, output=output,
                        title=title, artist=artist, is_short=is_short,
                        is_vertical=is_vertical)
                    render_video(settings, progress_callback=_make_progress_cb(item))
                    done += 1
                    item["status"] = "✅ OK"
                    out_dir = str(proj_dir)
                    self.after(0, lambda i=item, d=out_dir: self._turbo_on_item_done(i, d))
                    self.after(0, lambda n=done: self._set_status(
                        f"⚡ Turbo — {n}/{len(pending)}", WARN))
                except Exception as exc:
                    item["status"] = "❌ Erreur"
                    msg = str(exc)[:30]
                    self.after(0, lambda i=item, m=msg: i["_status_lbl"] and
                               i["_status_lbl"].configure(text=f"❌ {m}", text_color=DANGER))

            self.is_rendering = False
            self.after(0, lambda n=done: self._set_status(
                f"⚡ Turbo terminé — {n}/{len(pending)} ✓", SUCCESS))

        threading.Thread(target=worker, daemon=True).start()

    def _turbo_on_item_done(self, item: dict, output_dir: str):
        from app.ui.app import SUCCESS
        try:
            if item.get("_status_lbl"):
                item["_status_lbl"].configure(text="✅ OK", text_color=SUCCESS)
            btn = item.get("_folder_btn")
            if btn and not item.get("_folder_btn_packed"):
                btn.configure(command=lambda d=output_dir: open_file(d))
                btn.pack(side="left", padx=(2, 0))
                item["_folder_btn_packed"] = True
        except Exception:
            pass

    def _turbo_update_text_ui(self):
        from app.ui.app import SUCCESS, MUTED
        preset_name = self._turbo_preset_var.get() if hasattr(self, "_turbo_preset_var") else ""
        preset = self.user_presets.get(preset_name, {})
        show_text = bool(preset.get("show_text", True))

        if hasattr(self, "_turbo_text_badge"):
            try:
                if show_text:
                    self._turbo_text_badge.configure(text="● Texte ON", text_color=SUCCESS)
                else:
                    self._turbo_text_badge.configure(text="● Texte OFF", text_color=MUTED)
            except Exception:
                pass

        entry_state = "normal" if show_text else "disabled"
        for item in self._turbo_queue:
            for key in ("_artist_entry", "_title_entry"):
                w = item.get(key)
                if w:
                    try:
                        w.configure(state=entry_state)
                    except Exception:
                        pass

    def _turbo_preview(self):
        from app.ui.app import ACCENT, SURF3, TEXT, MUTED, FONT_H2, FONT_MU, _btn
        if self.is_rendering:
            messagebox.showwarning("Aperçu", "Un rendu est déjà en cours.")
            return
        if not self._turbo_queue:
            messagebox.showwarning("Aperçu", "Ajoutez au moins un fichier audio.")
            return

        first = self._turbo_queue[0]
        audio = first["audio"]
        image = first.get("image") or self._turbo_image
        if not image or not Path(image).exists():
            messagebox.showwarning("Aperçu", "Aucune pochette définie pour le premier fichier.")
            return

        preset_name = self._turbo_preset_var.get() if hasattr(self, "_turbo_preset_var") else ""
        preset = self.user_presets.get(preset_name, {})
        title  = first["title_var"].get().strip() or Path(audio).stem
        artist = first["artist_var"].get().strip()

        import tempfile
        tmp_dir   = Path(tempfile.mkdtemp(prefix="tac_preview_"))
        tmp_video = str(tmp_dir / "preview.mp4")
        tmp_frame = str(tmp_dir / "frame.jpg")

        settings = self._turbo_build_settings(
            preset=preset, audio=audio, image=image, output=tmp_video,
            title=title, artist=artist, is_short=False)
        settings.duration_limit = 3.0
        settings.start_offset   = 0.0

        popup = ctk.CTkToplevel(self)
        popup.title("Aperçu Turbo")
        popup.geometry("400x150")
        popup.resizable(False, False)
        popup.grab_set()
        ctk.CTkLabel(popup, text="Génération de l'aperçu…",
                     font=FONT_H2, text_color=TEXT).pack(pady=(22, 8))
        pbar = ctk.CTkProgressBar(popup, progress_color=ACCENT, fg_color=SURF3, width=340)
        pbar.pack(pady=4)
        pbar.set(0)
        plbl = ctk.CTkLabel(popup, text="Analyse audio…", text_color=MUTED, font=FONT_MU)
        plbl.pack()

        def _upd(txt):
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)%", txt)
            if m:
                pct = float(m.group(1)) / 100
                self.after(0, lambda v=pct: pbar.set(v))
                self.after(0, lambda p=float(m.group(1)): plbl.configure(text=f"{p:.0f}%"))
            elif "Encodage" in txt:
                self.after(0, lambda: pbar.set(0.95))
                self.after(0, lambda: plbl.configure(text="Encodage…"))

        def worker():
            try:
                render_video(settings, progress_callback=_upd)
                import subprocess
                ffmpeg_bin = shutil.which("ffmpeg")
                if ffmpeg_bin:
                    subprocess.run(
                        [ffmpeg_bin, "-y", "-i", tmp_video,
                         "-ss", "1.5", "-frames:v", "1", "-q:v", "2", tmp_frame],
                        capture_output=True, check=False
                    )
                if Path(tmp_frame).exists():
                    from PIL import Image as _Img
                    frame_img = _Img.open(tmp_frame).convert("RGB")
                    fw, fh = frame_img.size
                    ratio = min(900 / fw, 506 / fh)
                    nw, nh = int(fw * ratio), int(fh * ratio)
                    frame_img = frame_img.resize((nw, nh), _Img.LANCZOS)
                    ctk_img = ctk.CTkImage(
                        light_image=frame_img, dark_image=frame_img, size=(nw, nh))

                    def _show():
                        try:
                            popup.destroy()
                        except Exception:
                            pass
                        win = ctk.CTkToplevel(self)
                        win.title(f"Aperçu — {title}")
                        win.geometry(f"{nw + 40}x{nh + 90}")
                        win.resizable(False, False)
                        ctk.CTkLabel(win, text=f"Aperçu : {title}",
                                     font=FONT_H2, text_color=TEXT).pack(pady=(12, 4))
                        ctk.CTkLabel(win, image=ctk_img, text="").pack(padx=20)
                        ctk.CTkLabel(win, text="Rendu final réel · preset appliqué",
                                     text_color=MUTED, font=FONT_MU).pack(pady=(6, 0))
                        _btn(win, "Fermer", win.destroy, small=True, width=100).pack(pady=8)

                    self.after(0, _show)
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "Aperçu", "Impossible d'extraire un frame de la vidéo."))
                    self.after(0, lambda: popup.destroy() if popup.winfo_exists() else None)
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Aperçu", str(e)[:140]))
                self.after(0, lambda: popup.destroy() if popup.winfo_exists() else None)
            finally:
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()
