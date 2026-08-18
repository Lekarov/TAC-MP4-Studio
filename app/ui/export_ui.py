"""ExportMixin — projet, settings courants, export simple/DUAL, export de test.

Extrait de app/ui/app.py.
"""
from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import soundfile as sf

from app.config import safe_name
from app.errors import AudioImportError, ExportError, FFmpegError
from app.exporter import render_video, open_file
from app.logger import log_exception
from app.models import RenderSettings
from app.presets import PREVIEW_SECONDS, SHORT_WIDTH, SHORT_HEIGHT


class ExportMixin:

    # ══════════════════════════════════════════════════════════════════════════
    # PROJET
    # ══════════════════════════════════════════════════════════════════════════

    def _choose_project_root(self):
        path = filedialog.askdirectory(title="Dossier racine des créations")
        if path:
            self.project_root = path
            Path(path).mkdir(parents=True, exist_ok=True)
            self.project_root_var.set(path)
            self._schedule_persist()

    # ══════════════════════════════════════════════════════════════════════════
    # TIMING / SETTINGS
    # ══════════════════════════════════════════════════════════════════════════

    def _get_audio_duration(self):
        try:
            info = sf.info(self.audio_path)
            return float(info.frames / info.samplerate)
        except Exception:
            return 0.0

    def _get_export_timing(self):
        mode = self.export_mode.get()
        if mode == "SHORT":
            total = self._get_audio_duration()
            if total <= 60:
                return None, 0.0
            return 60.0, max(0.0, (total / 2.0) - 30.0)
        # COMPLET, VERTICAL, DUAL → durée complète, pas d'offset
        return None, 0.0

    def _preview_dimensions(self):
        from app.ui.app import PREVIEW_W_V, PREVIEW_H_V, PREVIEW_W, PREVIEW_H
        return (PREVIEW_W_V, PREVIEW_H_V) if self.preview_is_vertical else (PREVIEW_W, PREVIEW_H)

    def _current_settings(self, preview=False, short_mode=False):
        if preview:
            duration_limit = float(PREVIEW_SECONDS)
            raw = self.preview_start.get().strip().replace(",", ".")
            start_offset = float(raw) if raw else 0.0
            # Clamp cursor so it never starts past the end of the file
            file_dur = self._get_audio_duration()
            if file_dur > 0 and start_offset >= file_dur:
                start_offset = max(0.0, file_dur - duration_limit)
                self.preview_start.set(f"{start_offset:.1f}")
            out_w, out_h = self._preview_dimensions()
        else:
            duration_limit, start_offset = self._get_export_timing()
            is_vert = short_mode or (self.export_mode.get() == "VERTICAL")
            out_w   = SHORT_WIDTH  if is_vert else 1920
            out_h   = SHORT_HEIGHT if is_vert else 1080

        return RenderSettings(
            audio_path=self.audio_path,
            image_path=self.image_path,
            output_path=self.output_path,
            title_text=self.title_text.get().strip(),
            artist_text=self.artist_text.get().strip(),
            duration_limit=duration_limit,
            start_offset=start_offset,
            particle_preset=self.particle_preset.get(),
            smoke_preset=self.smoke_preset.get(),
            smoke_color=self.smoke_color.get(),
            spectrum_style=self.spectrum_style.get(),
            spectrum_size=float(self.spectrum_size.get()),
            spectrum_y=float(self.spectrum_y.get()),
            image_zoom=float(self.image_zoom.get()),
            pulse_strength=float(self.pulse_strength.get()),
            background_blur=float(self.background_blur.get()),
            background_brightness=float(self.background_brightness.get()),
            output_width=out_w,
            output_height=out_h,
            text_x=float(self.text_x.get()),
            text_y=float(self.text_y.get()),
            bg_mode=self.bg_mode.get(),
            bg_image_path=self.bg_image_path,
            gradient_top=self.gradient_top,
            gradient_bottom=self.gradient_bottom,
            vinyl_mode=bool(self.vinyl_mode.get()),
            vinyl_black=bool(self.vinyl_black.get()),
            spectrum_color=self.spectrum_color,
            spectrum_color_auto=bool(self.spectrum_color_auto.get()),
            floating_bg=bool(self.floating_bg.get()),
            bg_oscillate=bool(self.bg_oscillate.get()),
            spectrum_color_mid=self.spectrum_color_mid,
            spectrum_color_high=self.spectrum_color_high,
            spectrum_tricolor=bool(self.spectrum_tricolor.get()),
            spectrum_reactive=bool(self.spectrum_reactive.get()),
            font_name=self.font_name.get(),
            show_text=bool(self.show_text.get()),
            font_size_scale=float(self.font_size_scale.get()),
            subtitle_text=self.subtitle_text.get().strip(),
            shadow_intensity=float(self.shadow_intensity.get()),
            shadow_color=self.shadow_color,
            shadow_offset_x=float(self.shadow_offset_x.get()),
            shadow_offset_y=float(self.shadow_offset_y.get()),
        )

    # ══════════════════════════════════════════════════════════════════════════
    # PROJET — nom / dossier / assets
    # ══════════════════════════════════════════════════════════════════════════

    def _validate_project_name(self):
        from app.ui.app import DANGER, BORDER
        name = self.project_name_var.get().strip()
        if not name:
            if hasattr(self, "_proj_name_error"):
                self._proj_name_error.configure(text="⚠  Nom du projet obligatoire avant de générer.")
            if hasattr(self, "_proj_name_entry"):
                self._proj_name_entry.configure(border_color=DANGER)
            return None
        if hasattr(self, "_proj_name_error"):
            self._proj_name_error.configure(text="")
        if hasattr(self, "_proj_name_entry"):
            self._proj_name_entry.configure(border_color=BORDER)
        return safe_name(name)

    def _ask_project_name_and_folder(self, suffix=""):
        clean = self._validate_project_name()
        if not clean:
            raise RuntimeError("Nom du projet obligatoire.")
        root = Path(self.project_root)
        root.mkdir(parents=True, exist_ok=True)
        folder = f"{clean}{suffix}"
        proj_dir = root / folder
        ctr = 2
        while proj_dir.exists():
            proj_dir = root / f"{folder}_{ctr}"
            ctr += 1
        proj_dir.mkdir(parents=True, exist_ok=True)
        return clean, proj_dir

    def _copy_assets(self, proj_dir, name):
        a   = Path(self.audio_path)
        img = Path(self.image_path)
        ad  = proj_dir / f"{name}{a.suffix.lower()}"
        id_ = proj_dir / f"{name}_cover{img.suffix.lower()}"
        shutil.copy2(a, ad)
        shutil.copy2(img, id_)
        return str(ad), str(id_)

    # ── Overlay export (popup simple) ────────────────────────────────────────

    def _show_export_overlay(self, label):
        import customtkinter as ctk
        from app.ui.app import SURF2, SURF3, BORDER, ACCENT, TEXT, MUTED, FONT_H2, FONT_MU
        if not hasattr(self, "preview_label") or not self.preview_label:
            return
        ov = ctk.CTkFrame(self.preview_wrap, fg_color="#050505", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._export_overlay_frame = ov
        box = ctk.CTkFrame(ov, fg_color=SURF2, corner_radius=14,
                           border_color=BORDER, border_width=1,
                           width=360, height=160)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)
        ctk.CTkLabel(box, text=label, font=FONT_H2, text_color=TEXT).pack(pady=(22, 8))
        self._exp_bar = ctk.CTkProgressBar(box, progress_color=ACCENT, fg_color=SURF3)
        self._exp_bar.pack(fill="x", padx=32, pady=6)
        self._exp_bar.set(0)
        self._exp_detail = ctk.CTkLabel(box, text="Préparation...", text_color=MUTED, font=FONT_MU)
        self._exp_detail.pack(pady=(4, 0))
        self.update_idletasks()

    def _update_export_overlay(self, text):
        from app.ui.app import WARN
        self._set_status(text, WARN)
        if hasattr(self, "_exp_detail") and self._exp_detail:
            try:
                self._exp_detail.configure(text=text)
            except Exception:
                pass
        if hasattr(self, "_exp_bar") and self._exp_bar:
            try:
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)%", text)
                if m:
                    self._exp_bar.set(float(m.group(1)) / 100)
                elif "Encodage" in text:
                    self._exp_bar.set(0.97)
                elif "Terminé" in text:
                    self._exp_bar.set(1.0)
            except Exception:
                pass
        self.update_idletasks()

    def _hide_export_overlay(self):
        if hasattr(self, "_export_overlay_frame") and self._export_overlay_frame:
            try:
                self._export_overlay_frame.destroy()
            except Exception:
                pass
            self._export_overlay_frame = None
        self._exp_bar    = None
        self._exp_detail = None

    # ══════════════════════════════════════════════════════════════════════════
    # EXPORT
    # ══════════════════════════════════════════════════════════════════════════

    def _start_export(self):
        from app.ui.app import WARN, DANGER, SUCCESS
        if self.is_rendering:
            return
        if not self.audio_path or not self.image_path:
            messagebox.showerror("Erreur", "Musique ou pochette manquante.")
            return
        if not self._validate_project_name():
            return

        mode        = self.export_mode.get()
        is_short    = (mode == "SHORT")
        is_vertical = (mode == "VERTICAL")
        is_dual     = (mode == "DUAL")

        try:
            if is_short:
                suffix = "_SHORT"
            elif is_vertical:
                suffix = "_VERTICAL"
            else:
                suffix = ""
            proj_name, proj_dir = self._ask_project_name_and_folder(suffix=suffix)
            if is_short:
                file_name = f"{proj_name}_SHORT"
            elif is_vertical:
                file_name = f"{proj_name}_VERTICAL"
            else:
                file_name = proj_name
            self.audio_path, self.image_path = self._copy_assets(proj_dir, file_name)
            self.output_path = str(proj_dir / f"{file_name}.mp4")
            self._persist_now()
        except Exception as exc:
            messagebox.showerror("Export", str(exc))
            return

        label_map = {
            "SHORT":    "SHORT — 1min vertical",
            "VERTICAL": "VERTICAL — 9:16 complet",
            "COMPLET":  "COMPLET",
            "DUAL":     "COMPLET + SHORT",
        }
        label = label_map.get(mode, mode)

        self.preview_running = False
        self._stop_audio()
        self.is_rendering = True
        self._set_status(f"Export {label}...", WARN)
        self._show_export_overlay(f"Export {label}")

        def _on_error(exc_obj, kind):
            log_exception(exc_obj, context="_start_export worker")
            msg = getattr(exc_obj, "message", str(exc_obj))
            self.after(0, lambda: messagebox.showerror(kind, msg))
            self.after(0, self._hide_export_overlay)
            self.after(0, lambda: self._set_status("Erreur export", DANGER))

        if is_dual:
            # ── Double export : COMPLET (16:9) puis SHORT (1min vertical) ──────
            import copy as _copy
            import time
            from app.presets import SHORT_WIDTH as _SW, SHORT_HEIGHT as _SH

            # Settings COMPLET
            settings_complet = self._current_settings(preview=False, short_mode=False)
            settings_complet.output_path = self.output_path

            # Settings SHORT dérivés du COMPLET (même visuels, format + timing différents)
            total_dur = self._get_audio_duration()
            if total_dur > 60:
                short_dur    = 60.0
                short_offset = max(0.0, (total_dur / 2.0) - 30.0)
            else:
                short_dur    = None
                short_offset = 0.0

            settings_short = _copy.copy(settings_complet)
            settings_short.output_path    = str(proj_dir / f"{file_name}_SHORT.mp4")
            settings_short.output_width   = _SW
            settings_short.output_height  = _SH
            settings_short.duration_limit = short_dur
            settings_short.start_offset   = short_offset

            print(f"[Export] DUAL — COMPLET + SHORT offset={short_offset:.1f}s durée={short_dur}s")

            def worker():
                try:
                    # ── 1/2 COMPLET ──
                    self.after(0, lambda: self._update_export_overlay("[1/2] Complet…"))
                    render_video(settings_complet,
                                 progress_callback=lambda t: self.after(
                                     0, lambda txt=t: self._update_export_overlay(f"[1/2] {txt}")))
                    self.history.append({
                        "name":       file_name,
                        "folder":     str(proj_dir),
                        "video":      settings_complet.output_path,
                        "audio":      settings_complet.audio_path,
                        "image":      settings_complet.image_path,
                        "type":       "complet",
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })

                    # ── 2/2 SHORT ──
                    self.after(0, lambda: self._update_export_overlay("[2/2] Short…"))
                    render_video(settings_short,
                                 progress_callback=lambda t: self.after(
                                     0, lambda txt=t: self._update_export_overlay(f"[2/2] {txt}")))
                    self.history.append({
                        "name":       f"{file_name}_SHORT",
                        "folder":     str(proj_dir),
                        "video":      settings_short.output_path,
                        "audio":      settings_short.audio_path,
                        "image":      settings_short.image_path,
                        "type":       "short",
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })

                    self._persist_now()
                    self.after(0, lambda: messagebox.showinfo(
                        "Terminé ✓",
                        f"2 vidéos créées dans :\n{proj_dir}\n\n"
                        f"• {file_name}.mp4\n"
                        f"• {file_name}_SHORT.mp4"))
                    self.after(0, self._hide_export_overlay)
                    self.after(0, lambda: open_file(str(proj_dir)))
                    self.after(0, lambda: self._set_status("Export DUAL terminé ✓", SUCCESS))
                except FFmpegError as exc:
                    _on_error(exc, "FFmpeg")
                except ExportError as exc:
                    _on_error(exc, "Export")
                except AudioImportError as exc:
                    _on_error(exc, "Audio")
                except Exception as exc:
                    _on_error(ExportError("Export interrompu.", detail=str(exc)), "Erreur export")
                finally:
                    self.is_rendering = False

        else:
            # ── Export simple ──────────────────────────────────────────────────
            import time
            settings = self._current_settings(preview=False, short_mode=is_short)
            settings.output_path = self.output_path

            if is_short:
                print(f"[Export] SHORT offset={settings.start_offset:.1f}s durée={settings.duration_limit}s")

            def worker():
                try:
                    render_video(settings,
                                 progress_callback=lambda t: self.after(
                                     0, lambda txt=t: self._update_export_overlay(txt)))
                    self.history.append({
                        "name":       file_name,
                        "folder":     str(proj_dir),
                        "video":      settings.output_path,
                        "audio":      settings.audio_path,
                        "image":      settings.image_path,
                        "type":       mode.lower(),
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    self._persist_now()
                    self.after(0, lambda: messagebox.showinfo(
                        "Terminé ✓", f"Vidéo créée :\n{settings.output_path}"))
                    self.after(0, self._hide_export_overlay)
                    self.after(0, lambda: open_file(str(proj_dir)))
                    self.after(0, lambda: self._set_status("Export terminé ✓", SUCCESS))
                except FFmpegError as exc:
                    _on_error(exc, "FFmpeg")
                except ExportError as exc:
                    _on_error(exc, "Export")
                except AudioImportError as exc:
                    _on_error(exc, "Audio")
                except Exception as exc:
                    _on_error(ExportError("Export interrompu.", detail=str(exc)), "Erreur export")
                finally:
                    self.is_rendering = False

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # EXPORT DE TEST
    # ══════════════════════════════════════════════════════════════════════════

    def _pick_test_audio(self):
        from app.ui.app import TEXT
        path = filedialog.askopenfilename(
            title="Audio pour le test",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma"), ("Tous", "*.*")],
        )
        if path:
            self.test_audio_path = path
            self._test_audio_lbl.configure(text=Path(path).name, text_color=TEXT)
            self._persist_now()

    def _pick_test_image(self):
        from app.ui.app import TEXT
        path = filedialog.askopenfilename(
            title="Pochette pour le test",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Tous", "*.*")],
        )
        if path:
            self.test_image_path = path
            self._test_image_lbl.configure(text=Path(path).name, text_color=TEXT)
            self._persist_now()

    def _start_test_export(self):
        from app.ui.app import MUTED, SUCCESS, DANGER
        if self.is_rendering:
            return

        if not self.test_audio_path or not Path(self.test_audio_path).exists():
            messagebox.showwarning("Test", "Sélectionne d'abord un fichier audio.")
            return
        if not self.test_image_path or not Path(self.test_image_path).exists():
            messagebox.showwarning("Test", "Sélectionne d'abord une image pochette.")
            return

        import tempfile
        tmp_dir = Path(tempfile.gettempdir()) / "tac_test_check"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(tmp_dir / "check_preview.mp4")

        settings = self._current_settings(preview=False, short_mode=False)
        settings.audio_path = self.test_audio_path
        settings.image_path = self.test_image_path
        settings.output_path = out_path
        settings.duration_limit = 15.0
        settings.start_offset = 0.0
        settings.output_width = 1920
        settings.output_height = 1080
        settings.title_text = ""
        settings.artist_text = ""
        settings.subtitle_text = ""

        self._test_btn.configure(state="disabled")
        self._test_bar.set(0)
        self._test_bar.pack(fill="x", pady=(0, 4))
        self._test_detail.configure(text="Préparation...", text_color=MUTED)
        self._test_detail.pack(anchor="w")
        self._test_open_btn.pack_forget()
        self.is_rendering = True

        def _progress(text):
            self._test_detail.configure(text=text)
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)%", text)
            if m:
                self._test_bar.set(float(m.group(1)) / 100)
            elif "Encodage" in text:
                self._test_bar.set(0.97)
            elif "Terminé" in text:
                self._test_bar.set(1.0)

        def worker():
            try:
                render_video(settings,
                             progress_callback=lambda t: self.after(0, lambda txt=t: _progress(txt)))
                def _done():
                    self._test_detail.configure(text="Terminé ✓", text_color=SUCCESS)
                    self._test_open_btn.configure(command=lambda: open_file(out_path))
                    self._test_open_btn.pack(fill="x", pady=(4, 0))
                self.after(0, _done)
            except FFmpegError as exc:
                log_exception(exc, context="_start_test_export worker")
                msg = exc.message
                self.after(0, lambda: self._test_detail.configure(
                    text=f"Erreur : {msg[:80]}", text_color=DANGER))
            except ExportError as exc:
                log_exception(exc, context="_start_test_export worker")
                msg = exc.message
                self.after(0, lambda: self._test_detail.configure(
                    text=f"Erreur : {msg[:80]}", text_color=DANGER))
            except AudioImportError as exc:
                log_exception(exc, context="_start_test_export worker")
                msg = exc.message
                self.after(0, lambda: self._test_detail.configure(
                    text=f"Erreur : {msg[:80]}", text_color=DANGER))
            except Exception as exc:
                export_err = ExportError("Export interrompu.", detail=str(exc))
                log_exception(export_err, context="_start_test_export worker")
                msg = export_err.message
                self.after(0, lambda: self._test_detail.configure(
                    text=f"Erreur : {msg[:80]}", text_color=DANGER))
            finally:
                self.is_rendering = False
                self.after(0, lambda: self._test_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
