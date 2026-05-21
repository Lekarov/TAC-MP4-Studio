"""EditorMixin — méthodes de l'éditeur de visuels.

Extrait de app/ui/app.py.
"""
from __future__ import annotations

import colorsys
import random
from tkinter import colorchooser


class EditorMixin:

    # ── Fond dégradé UI ───────────────────────────────────────────────────────

    def _build_gradient_pickers(self, parent):
        import customtkinter as ctk
        from app.ui.app import MUTED, BORDER, TEXT, FONT_MU, _btn
        self._grad_swatches: dict = {}
        self._grad_hex_lbls: dict = {}

        import tkinter as tk
        for label, attr in [("Couleur haut", "gradient_top"), ("Couleur bas", "gradient_bottom")]:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=label, text_color=MUTED, font=FONT_MU,
                         anchor="w").pack(side="left")

            color_val = getattr(self, attr)

            swatch = tk.Label(row, bg=color_val, width=5, relief="flat",
                              bd=1, highlightbackground=BORDER, highlightthickness=1)
            swatch.pack(side="right", padx=(6, 0))

            hex_lbl = ctk.CTkLabel(row, text=color_val, text_color=TEXT,
                                   font=FONT_MU, width=65, anchor="e")
            hex_lbl.pack(side="right")

            self._grad_swatches[attr] = swatch
            self._grad_hex_lbls[attr] = hex_lbl

            def pick(a=attr):
                current = getattr(self, a)
                result = colorchooser.askcolor(color=current, title="Choisir la couleur")
                if result and result[1]:
                    setattr(self, a, result[1])
                    self._grad_swatches[a].configure(bg=result[1])
                    self._grad_hex_lbls[a].configure(text=result[1])
                    self._schedule_persist()
                    self._reload_visuals_only()

            _btn(row, "Choisir", pick, small=True, width=70, height=24).pack(side="right", padx=(0, 6))

    # ── Couleur spectre ───────────────────────────────────────────────────────

    def _pick_spectrum_color(self):
        result = colorchooser.askcolor(color=self.spectrum_color, title="Couleur du spectre — Basses")
        if result and result[1]:
            self._set_spectrum_color(result[1])

    def _pick_spectrum_color_band(self, band: str):
        attr = f"spectrum_color_{band}"
        current = getattr(self, attr, "#ffffff")
        label = "Médiums" if band == "mid" else "Aigus"
        result = colorchooser.askcolor(color=current, title=f"Couleur spectre — {label}")
        if result and result[1]:
            self._set_spectrum_color_band(band, result[1])

    def _set_spectrum_color_band(self, band: str, hex_color: str):
        setattr(self, f"spectrum_color_{band}", hex_color)
        swatch_attr = f"_spec_swatch_{band}"
        hex_attr    = f"_spec_hex_{band}"
        if hasattr(self, swatch_attr):
            try: getattr(self, swatch_attr).configure(bg=hex_color)
            except Exception: pass
        if hasattr(self, hex_attr):
            try: getattr(self, hex_attr).configure(text=hex_color)
            except Exception: pass
        self._schedule_persist()
        if self.preview_ready:
            self._reload_visuals_only()

    def _pick_shadow_color(self):
        result = colorchooser.askcolor(color=self.shadow_color, title="Couleur de l'ombre du texte")
        if result and result[1]:
            self.shadow_color = result[1]
            try: self._shadow_swatch.configure(bg=result[1])
            except Exception: pass
            try: self._shadow_hex_lbl.configure(text=result[1])
            except Exception: pass
            self._schedule_persist()
            if self.preview_ready:
                self._reload_visuals_only()

    def _set_spectrum_color(self, hex_color: str):
        self.spectrum_color = hex_color
        if hasattr(self, "_spec_swatch"):
            self._spec_swatch.configure(bg=hex_color)
        if hasattr(self, "_spec_hex_lbl"):
            self._spec_hex_lbl.configure(text=hex_color)
        self._schedule_persist()
        if self.preview_ready:
            self._reload_visuals_only()

    def _on_spectrum_color_auto(self):
        if self.spectrum_color_auto.get() and self.preview_cover is not None:
            from app.renderer import extract_dominant_color
            auto_c = extract_dominant_color(self.preview_cover)
            self._set_spectrum_color(auto_c)
        self._schedule_persist()

    def _randomize_gradient_colors(self):
        h  = random.random()
        h2 = (h + 0.08 + random.random() * 0.22) % 1.0
        s1 = 0.80 + random.random() * 0.20
        s2 = 0.70 + random.random() * 0.25
        v1 = 0.55 + random.random() * 0.40
        v2 = 0.40 + random.random() * 0.35
        def to_hex(r, g, b):
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        c1 = to_hex(*colorsys.hsv_to_rgb(h,  s1, v1))
        c2 = to_hex(*colorsys.hsv_to_rgb(h2, s2, v2))
        self.gradient_top    = c1
        self.gradient_bottom = c2
        self._update_gradient_ui()
        self.bg_mode.set("gradient")
        self._refresh_gradient_visibility()
        self._schedule_persist()
        self._reload_visuals_only()

    def _update_gradient_ui(self):
        if hasattr(self, "_grad_swatches"):
            for attr, color in [("gradient_top", self.gradient_top),
                                 ("gradient_bottom", self.gradient_bottom)]:
                if attr in self._grad_swatches:
                    try:
                        self._grad_swatches[attr].configure(bg=color)
                    except Exception:
                        pass
                if attr in self._grad_hex_lbls:
                    try:
                        self._grad_hex_lbls[attr].configure(text=color)
                    except Exception:
                        pass

    # ── Presets ───────────────────────────────────────────────────────────────

    def _save_user_preset(self):
        name = self._user_preset_name.get().strip()
        if not name:
            return
        self.user_presets[name] = self._current_visual_snapshot()
        self._user_preset_name.set("")
        self._persist_now()
        self._refresh_presets_library()

    def _apply_preset_data(self, p: dict):
        """Applique un dict de preset (intégré ou perso) aux réglages courants."""
        self.particle_preset.set(p.get("particle_preset", self.particle_preset.get()))
        self.smoke_preset.set(p.get("smoke_preset", self.smoke_preset.get()))
        self.smoke_color.set(p.get("smoke_color", self.smoke_color.get()))
        self.spectrum_style.set(p.get("spectrum_style", self.spectrum_style.get()))
        self.spectrum_size.set(float(p.get("spectrum_size", self.spectrum_size.get())))
        self.spectrum_y.set(float(p.get("spectrum_y", self.spectrum_y.get())))
        self.image_zoom.set(float(p.get("image_zoom", self.image_zoom.get())))
        self.pulse_strength.set(float(p.get("pulse_strength", self.pulse_strength.get())))
        if "vinyl_mode" in p:       self.vinyl_mode.set(p["vinyl_mode"])
        if "vinyl_black" in p:      self.vinyl_black.set(p["vinyl_black"])
        if "spectrum_color" in p:   self._set_spectrum_color(p["spectrum_color"])
        if "floating_bg" in p:      self.floating_bg.set(p["floating_bg"])
        if "bg_oscillate" in p:     self.bg_oscillate.set(p["bg_oscillate"])
        if "background_blur" in p:        self.background_blur.set(float(p["background_blur"]))
        if "background_brightness" in p:  self.background_brightness.set(float(p["background_brightness"]))
        if "bg_mode" in p:
            self.bg_mode.set(p["bg_mode"])
            self._refresh_gradient_visibility()
        if "gradient_top" in p:     self.gradient_top = p["gradient_top"]
        if "gradient_bottom" in p:  self.gradient_bottom = p["gradient_bottom"]
        self._update_gradient_ui()
        if "spectrum_color_mid"  in p: self._set_spectrum_color_band("mid",  p["spectrum_color_mid"])
        if "spectrum_color_high" in p: self._set_spectrum_color_band("high", p["spectrum_color_high"])
        if "spectrum_tricolor"   in p: self.spectrum_tricolor.set(p["spectrum_tricolor"])
        if "spectrum_reactive"   in p: self.spectrum_reactive.set(p["spectrum_reactive"])
        if "bg_image_path" in p:
            self.bg_image_path = p["bg_image_path"]
            if hasattr(self, "_bg_image_label"):
                self._bg_image_label.configure(text=self._bg_image_display_name())
            if p["bg_image_path"] and self.bg_mode.get() != "custom":
                self.bg_mode.set("custom")
                self._refresh_gradient_visibility()
        self._schedule_persist()
        if not self.is_rendering:
            self._reload_visuals_only()

    def _apply_user_preset(self, name: str):
        p = self.user_presets.get(name, {})
        if not p:
            return
        self._apply_preset_data(p)

    def _apply_builtin_preset(self, name: str):
        from app.presets import GLOBAL_PRESETS
        p = GLOBAL_PRESETS.get(name, {})
        if not p:
            return
        self.global_preset.set(name)
        self._apply_preset_data(p)

    def _delete_user_preset(self, name: str):
        self.user_presets.pop(name, None)
        self.user_preset_favorites.discard(name)
        self._persist_now()
        self._refresh_presets_library()

    def _hide_builtin_preset(self, name: str):
        self.hidden_builtin_presets.add(name)
        self._persist_now()
        self._refresh_presets_library()

    def _restore_builtin_presets(self):
        if not self.hidden_builtin_presets:
            return
        self.hidden_builtin_presets.clear()
        self._persist_now()
        self._refresh_presets_library()

    def _refresh_user_presets_ui(self):
        self._refresh_presets_library()

    def _refresh_presets_library(self):
        """Rendu de la bibliothèque unifiée : intégrés visibles + presets perso."""
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import (
            MUTED, TEXT, SURF2, SURF3, BORDER, ACCENT, ACCLT, FONT_MU, FONT_SM, FONT_H2, _btn,
        )
        from app.presets import GLOBAL_PRESETS

        if not hasattr(self, "_presets_library_frame"):
            return
        for child in self._presets_library_frame.winfo_children():
            child.destroy()

        # Construire la liste : (name, kind, is_fav)
        entries: list[tuple[str, str, bool]] = []
        for name in GLOBAL_PRESETS:
            if name not in self.hidden_builtin_presets:
                entries.append((name, "builtin", name in self.user_preset_favorites))
        for name in self.user_presets:
            entries.append((name, "user", name in self.user_preset_favorites))

        # Favoris en premier, puis intégrés, puis perso, puis alphabétique
        entries.sort(key=lambda x: (not x[2], x[1] == "user", x[0].lower()))

        if not entries:
            ctk.CTkLabel(
                self._presets_library_frame,
                text="Aucun preset — restaurez les intégrés ou créez-en un.",
                text_color=MUTED, font=FONT_MU, wraplength=220,
            ).pack(pady=16)
            return

        for name, kind, is_fav in entries:
            p_data = GLOBAL_PRESETS.get(name) if kind == "builtin" else self.user_presets.get(name, {})
            dot_color = (
                p_data.get("spectrum_color")
                or p_data.get("gradient_top")
                or ACCENT
            )

            card = ctk.CTkFrame(
                self._presets_library_frame,
                fg_color=SURF3, corner_radius=8,
                border_color=BORDER, border_width=1,
            )
            card.pack(fill="x", pady=2, padx=1)

            # Bande couleur à gauche
            dot = tk.Label(card, bg=dot_color, width=3, relief="flat", bd=0)
            dot.pack(side="left", fill="y", ipadx=3)

            # Infos (nom + badge)
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=5)

            ctk.CTkLabel(info, text=name, text_color=TEXT, font=FONT_SM, anchor="w").pack(anchor="w")
            badge_color = MUTED if kind == "builtin" else ACCLT
            badge_text  = "intégré" if kind == "builtin" else "perso"
            ctk.CTkLabel(info, text=badge_text, text_color=badge_color,
                         font=FONT_MU, anchor="w").pack(anchor="w")

            # Boutons
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(side="right", padx=(0, 6))

            star_fg = "#f59e0b" if is_fav else "#2a2a2a"
            _btn(btns, "★", lambda n=name: self._toggle_favorite(n),
                 small=True, width=28, height=26,
                 fg_color=star_fg, hover_color="#d97706").pack(side="left", padx=(0, 2))

            if kind == "builtin":
                _btn(btns, "▶", lambda n=name: self._apply_builtin_preset(n),
                     small=True, width=28, height=26, accent=True).pack(side="left", padx=(0, 2))
                _btn(btns, "✕", lambda n=name: self._hide_builtin_preset(n),
                     small=True, width=28, height=26, danger=True).pack(side="left")
            else:
                _btn(btns, "▶", lambda n=name: self._apply_user_preset(n),
                     small=True, width=28, height=26, accent=True).pack(side="left", padx=(0, 2))
                _btn(btns, "✕", lambda n=name: self._delete_user_preset(n),
                     small=True, width=28, height=26, danger=True).pack(side="left")

    # ── Visibilité des options ────────────────────────────────────────────────

    def _on_setting_changed(self):
        self._schedule_persist()
        if not self.is_rendering:
            self._reload_visuals_only()

    def _on_bg_mode_changed(self):
        self._refresh_bg_mode_visibility()
        self._schedule_persist()
        self._reload_visuals_only()

    def _refresh_bg_mode_visibility(self):
        if not hasattr(self, "_photo_frame") or not hasattr(self, "_gradient_frame"):
            return
        mode = self.bg_mode.get()
        if mode == "gradient":
            self._photo_frame.pack_forget()
            self._gradient_frame.pack(fill="x")
        else:
            self._gradient_frame.pack_forget()
            self._photo_frame.pack(fill="x")
        if hasattr(self, "_custom_bg_row"):
            if mode == "custom":
                self._custom_bg_row.pack(fill="x", pady=(0, 4))
            else:
                self._custom_bg_row.pack_forget()

    def _refresh_gradient_visibility(self):
        self._refresh_bg_mode_visibility()

    def _on_vinyl_mode_changed(self):
        self._refresh_vinyl_opts()
        self._on_setting_changed()

    def _refresh_vinyl_opts(self):
        if not hasattr(self, "_vinyl_opts"):
            return
        if self.vinyl_mode.get():
            self._vinyl_opts.pack(fill="x", pady=(0, 6))
            # Réactivité / Pulse sans effet en mode vinyle
            if hasattr(self, "_pulse_frame"):
                self._pulse_frame.pack_forget()
        else:
            self._vinyl_opts.pack_forget()
            if hasattr(self, "_pulse_frame"):
                self._pulse_frame.pack(fill="x")

    def _on_smoke_changed(self, _=None):
        self._refresh_smoke_opts()
        self._on_setting_changed()

    def _refresh_smoke_opts(self):
        if not hasattr(self, "_smoke_color_frame"):
            return
        from app.presets import SMOKE_PRESETS
        preset = SMOKE_PRESETS.get(self.smoke_preset.get(), {})
        if preset.get("density", 0) <= 0:
            self._smoke_color_frame.pack_forget()
        else:
            self._smoke_color_frame.pack(fill="x")

    def _on_tricolor_changed(self, _=None):
        self._refresh_tricolor_opts()
        self._on_setting_changed()

    def _refresh_tricolor_opts(self):
        if not hasattr(self, "_tricolor_frame"):
            return
        if self.spectrum_tricolor.get():
            self._tricolor_frame.pack(fill="x", pady=(0, 4))
        else:
            self._tricolor_frame.pack_forget()

    # ── Update text preview ───────────────────────────────────────────────────

    def _update_text_preview(self):
        try:
            artist   = self.artist_text.get().strip()
            title    = self.title_text.get().strip()
            subtitle = self.subtitle_text.get().strip()
        except Exception:
            return
        if artist and title:
            preview = f'"{artist}" · "{title}"'
        elif artist:
            preview = f'"{artist}"'
        elif title:
            preview = f'"{title}"'
        else:
            preview = "Aucun texte affiché"
        if subtitle:
            preview += f' · "{subtitle}"'
        if hasattr(self, "_text_preview_lbl"):
            try:
                self._text_preview_lbl.configure(text=f"→ {preview}")
            except Exception:
                pass

    def _toggle_preview_format(self):
        from app.ui.app import ACCENT, ACCHOV, SURF3, SURF2
        self.preview_is_vertical = not self.preview_is_vertical
        label = "9:16 → 16:9" if self.preview_is_vertical else "16:9 → 9:16"
        fg    = ACCENT if self.preview_is_vertical else SURF3
        hov   = ACCHOV if self.preview_is_vertical else SURF2
        if hasattr(self, "_fmt_btn") and self._fmt_btn:
            self._fmt_btn.configure(text=label, fg_color=fg, hover_color=hov)
        self._prepare_preview()

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _section_title(self, parent, text):
        import customtkinter as ctk
        from app.ui.app import FONT_SEC, ACCLT
        ctk.CTkLabel(parent, text=text, font=FONT_SEC, text_color=ACCLT, anchor="w").pack(
            anchor="w", pady=(14, 4), padx=4)

    def _combo_row(self, parent, label, var, values, command=None):
        import customtkinter as ctk
        from app.ui.app import MUTED, FONT_MU, SURF3, BORDER, SURF2, TEXT, FONT_SM
        cmd = command if command is not None else lambda _: self._on_setting_changed()
        ctk.CTkLabel(parent, text=label, text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(4, 0))
        ctk.CTkComboBox(parent, variable=var, values=values,
                        command=cmd,
                        fg_color=SURF3, border_color=BORDER,
                        button_color=SURF2, button_hover_color=BORDER,
                        dropdown_fg_color=SURF2, text_color=TEXT,
                        font=FONT_SM).pack(fill="x", pady=(2, 6))

    def _slider_row(self, parent, label, var, minv, maxv):
        import customtkinter as ctk
        from app.ui.app import MUTED, TEXT, FONT_MU, ACCENT, ACCLT
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(row, text=label, text_color=MUTED, font=FONT_MU, anchor="w").pack(side="left")
        val_lbl = ctk.CTkLabel(row, text=f"{var.get():.2f}", text_color=TEXT, font=FONT_MU, width=38, anchor="e")
        val_lbl.pack(side="right")

        def on_slide(v):
            val_lbl.configure(text=f"{float(v):.2f}")
            self._schedule_persist()
            if self.preview_ready:
                self._reload_visuals_only()

        ctk.CTkSlider(parent, from_=minv, to=maxv, variable=var, command=on_slide,
                      progress_color=ACCENT, button_color=ACCLT,
                      button_hover_color=ACCENT).pack(fill="x", pady=(2, 6))
