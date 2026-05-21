"""PagesMixin — méthodes de navigation et pages.

Extrait de app/ui/app.py.
"""
from __future__ import annotations

import math
import random
import time

from tkinter import messagebox, filedialog


class PagesMixin:

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE ACCUEIL
    # ══════════════════════════════════════════════════════════════════════════

    def show_home(self):
        import tkinter as tk
        import customtkinter as ctk
        from app.ui.app import (
            BG, SURF2, BORDER, ACCENT, ACCLT, TEXT, MUTED, FONT_H2, FONT_SM,
            FONT_MU, VERSION, _btn,
        )
        self._clear_main()
        self._set_status("Accueil")

        canvas = tk.Canvas(self.main, bg="#080808", highlightthickness=0)
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        _rng = random.Random(1337)
        _base_heights = [
            (math.sin(i / 95 * math.pi) ** 1.4
             * (0.55 + 0.45 * math.sin(i / 95 * math.pi * 7 + 0.9))
             * (0.7 + 0.3 * _rng.random()))
            for i in range(96)
        ]
        _anim_t = [0.0]

        def _draw_bg(t=0.0):
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w < 50:
                return

            cx, cy = w // 2, h // 2

            pulse = 1.0 + 0.06 * math.sin(t * 0.8)
            for i in range(22, 0, -1):
                r = i / 22 * pulse
                rw = int(w * 0.48 * r)
                rh = int(h * 0.58 * r)
                hue_shift = math.sin(t * 0.25) * 0.15
                rc = int(max(0, min(255, 30 + (i / 22) * 55 * (1 + hue_shift))))
                gc = 0
                bc = int(max(0, min(255, 60 + (i / 22) * 110)))
                canvas.create_oval(cx - rw, cy - rh, cx + rw, cy + rh,
                                   fill=f"#{rc:02x}{gc:02x}{bc:02x}", outline="")

            n = 96
            bar_w = w / n
            for i in range(n):
                ti = i / (n - 1)
                phase = t * 1.4 + i * 0.18
                anim = 0.55 + 0.45 * math.sin(phase)
                val = _base_heights[i] * anim
                bar_h = int(val * h * 0.34)
                if bar_h < 2:
                    continue
                x0 = int(i * bar_w)
                x1 = max(x0 + 1, int((i + 1) * bar_w) - 1)

                hue = (ti + t * 0.04) % 1.0
                if hue < 0.5:
                    rc = int(40 + (1 - hue * 2) * 160)
                    gc = int(hue * 2 * 30)
                    bc = int(100 + hue * 2 * 155)
                else:
                    rc = int(40 + (hue - 0.5) * 2 * 160)
                    gc = int((1 - (hue - 0.5) * 2) * 30)
                    bc = int(255 - (hue - 0.5) * 2 * 100)
                intensity = int(val * 0.85 + 0.15)
                rc = int(min(255, rc * intensity))
                gc = int(min(255, gc * intensity))
                bc = int(min(255, bc * intensity))

                canvas.create_rectangle(x0, h, x1, h - bar_h,
                                        fill=f"#{rc:02x}{gc:02x}{bc:02x}",
                                        outline="")

                if bar_h > 8:
                    tip_r = min(rc + 80, 255)
                    tip_g = min(gc + 40, 255)
                    tip_b = min(bc + 80, 255)
                    canvas.create_rectangle(x0, h - bar_h, x1, h - bar_h + 2,
                                            fill=f"#{tip_r:02x}{tip_g:02x}{tip_b:02x}",
                                            outline="")

            canvas.create_line(0, h - 1, w, h - 1, fill="#141414", width=1)

        def _anim_loop():
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            _anim_t[0] += 0.045
            _draw_bg(_anim_t[0])
            self._home_anim_job = self.after(42, _anim_loop)

        canvas.bind("<Configure>", lambda e: _draw_bg(_anim_t[0]))
        self.after(30, _anim_loop)

        card = ctk.CTkFrame(self.main, fg_color="#0f0f0f",
                            corner_radius=20, border_color="#1e1e1e", border_width=1,
                            width=420)
        card.place(relx=0.5, rely=0.46, anchor="center")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=36)

        from pathlib import Path
        import numpy as _np
        from PIL import Image
        _logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "tac.png"
        _logo_ok = False
        if _logo_path.exists():
            try:
                _logo_img = Image.open(str(_logo_path)).convert("RGBA")
                _arr = _np.array(_logo_img)
                _black = (_arr[:,:,0] < 18) & (_arr[:,:,1] < 18) & (_arr[:,:,2] < 18)
                _arr[:,:,3] = _np.where(_black, 0, _arr[:,:,3])
                _logo_img = Image.fromarray(_arr)
                _ctk_logo = ctk.CTkImage(
                    light_image=_logo_img,
                    dark_image=_logo_img,
                    size=(130, 130),
                )
                ctk.CTkLabel(inner, image=_ctk_logo, text="").pack(pady=(0, 14))
                _logo_ok = True
            except Exception:
                pass

        if not _logo_ok:
            icon_frame = ctk.CTkFrame(inner, fg_color=ACCENT, corner_radius=14,
                                      width=54, height=54)
            icon_frame.pack(pady=(0, 18))
            icon_frame.pack_propagate(False)
            ctk.CTkLabel(icon_frame, text="▶",
                         font=ctk.CTkFont("Segoe UI", 22, "bold"),
                         text_color="#ffffff").place(relx=0.52, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="TAC MP4 Studio",
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=TEXT).pack()
        ctk.CTkLabel(inner, text="Music Visualizer",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(pady=(2, 24))

        ctk.CTkFrame(inner, height=1, fg_color="#1e1e1e", corner_radius=0).pack(
            fill="x", pady=(0, 24))

        _btn(inner, "  ✦  NOUVELLE CRÉATION", self.show_step_audio,
             accent=True, height=48, width=340,
             font=ctk.CTkFont("Segoe UI", 13, "bold")).pack(pady=(0, 10))

        hist_btn = ctk.CTkButton(inner, text="Historique",
                                 command=self.show_history,
                                 fg_color="transparent",
                                 hover_color="#161616",
                                 text_color=MUTED,
                                 border_color="#1e1e1e", border_width=1,
                                 font=FONT_SM, corner_radius=8,
                                 height=40, width=340)
        hist_btn.pack(pady=(0, 6))
        ctk.CTkButton(inner, text="⚡ TURBO — Production rapide",
                      command=self.show_turbo,
                      fg_color="transparent",
                      hover_color="#161616",
                      text_color="#f59e0b",
                      border_color="#2a2000", border_width=1,
                      font=FONT_SM, corner_radius=8,
                      height=40, width=340).pack()

        ctk.CTkFrame(inner, height=1, fg_color="#1e1e1e", corner_radius=0).pack(
            fill="x", pady=(22, 16))

        feat_row = ctk.CTkFrame(inner, fg_color="transparent")
        feat_row.pack()
        for text in ["10 spectres", "Vinyle", "Oscilloscope", "Dégradé"]:
            dot = ctk.CTkLabel(feat_row, text=f"● {text}",
                               text_color="#333333",
                               font=ctk.CTkFont("Segoe UI", 9))
            dot.pack(side="left", padx=7)

        ctk.CTkLabel(inner, text=f"v{VERSION}",
                     text_color="#252525",
                     font=ctk.CTkFont("Segoe UI", 8)).pack(pady=(10, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE ÉTAPE AUDIO
    # ══════════════════════════════════════════════════════════════════════════

    def show_step_audio(self):
        import customtkinter as ctk
        from app.ui.app import TEXT, MUTED, FONT_SM, _btn
        self._clear_main()
        self._set_status("Étape 1 / 2 — Audio")
        center = ctk.CTkFrame(self.main, fg_color="transparent")
        center.place(relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(center, text="Choisir la musique",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"), text_color=TEXT).pack(pady=(0, 6))
        ctk.CTkLabel(center, text="MP3 · WAV · FLAC · OGG · M4A",
                     text_color=MUTED, font=FONT_SM).pack(pady=(0, 32))
        _btn(center, "  🎵  Importer un fichier audio", self._pick_audio,
             accent=True, width=300, height=50).pack(pady=6)
        _btn(center, "← Retour", self.show_home, small=True, width=140).pack(pady=(16, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE ÉTAPE IMAGE
    # ══════════════════════════════════════════════════════════════════════════

    def show_step_image(self):
        import customtkinter as ctk
        from pathlib import Path
        from app.ui.app import TEXT, MUTED, ACCLT, FONT_SM, FONT_MU, _btn, _card
        self._clear_main()
        self._set_status("Étape 2 / 2 — Pochette")
        center = ctk.CTkFrame(self.main, fg_color="transparent")
        center.place(relx=0.5, rely=0.44, anchor="center")
        ctk.CTkLabel(center, text="Choisir la pochette",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"), text_color=TEXT).pack(pady=(0, 6))
        fname_card = _card(center)
        fname_card.pack(fill="x", pady=(0, 28), ipady=8, ipadx=12)
        ctk.CTkLabel(fname_card, text="🎵  " + Path(self.audio_path).name,
                     text_color=ACCLT, font=FONT_SM).pack(padx=16, pady=8)
        _btn(center, "  🖼  Importer une image", self._pick_image,
             accent=True, width=300, height=50).pack(pady=6)
        ctk.CTkLabel(center, text="PNG · JPG · JPEG · WEBP",
                     text_color=MUTED, font=FONT_MU).pack(pady=(4, 16))
        _btn(center, "← Retour", self.show_step_audio, small=True, width=140).pack()

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE HISTORIQUE
    # ══════════════════════════════════════════════════════════════════════════

    def show_history(self):
        import customtkinter as ctk
        from pathlib import Path
        from PIL import Image
        from app.exporter import open_file
        from app.ui.app import (
            BG, SURF3, BORDER, ACCENT, ACCLT, TEXT, MUTED, SUCCESS, WARN, DANGER,
            FONT_H1, FONT_H2, FONT_SEC, FONT_SM, FONT_MU, _btn, _card,
        )
        self._clear_main()
        self._set_status("Historique")
        _cover = ctk.CTkFrame(self.main, fg_color=BG)
        _cover.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.main.update_idletasks()
        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(top, text="Historique", font=FONT_H1, text_color=TEXT).pack(side="left")
        _btn(top, "← Accueil", self.show_home, small=True, width=120).pack(side="right")
        _btn(top, "🗑  Vider l'historique", self._clear_all_history,
             small=True, width=160, danger=True).pack(side="right", padx=(0, 8))

        items = self._sorted_history()
        if not items:
            ctk.CTkLabel(outer, text="Aucune création pour l'instant.",
                         text_color=MUTED, font=FONT_SM).pack(pady=40)
            return

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent",
                                        scrollbar_button_color=SURF3,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.pack(fill="both", expand=True)

        self.main.update_idletasks()
        try:
            _cover.destroy()
        except Exception:
            pass

        for item in items:
            card = _card(scroll)
            card.pack(fill="x", pady=5, padx=2)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)

            thumb_path = Path(item.get("folder", "")) / "_thumb.jpg"
            if not thumb_path.exists():
                vid = item.get("video", "")
                if vid:
                    thumb_path = Path(vid).parent / (Path(vid).stem + "_thumb.jpg")

            if thumb_path.exists():
                try:
                    thumb_img = Image.open(thumb_path).convert("RGB")
                    thumb_img.thumbnail((160, 90))
                    ctk_img = ctk.CTkImage(light_image=thumb_img, dark_image=thumb_img,
                                           size=(160, 90))
                    ctk.CTkLabel(inner, image=ctk_img, text="").pack(side="left", padx=(0, 14))
                except Exception:
                    self._thumb_placeholder(inner)
            else:
                self._thumb_placeholder(inner)

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            kind = item.get("type", "complet").upper()
            kind_color = {"SHORT": ACCLT, "VERTICAL": "#a855f7", "COMPLET": SUCCESS, "DUAL": ACCENT}.get(kind, TEXT)

            row1 = ctk.CTkFrame(info, fg_color="transparent")
            row1.pack(fill="x", anchor="w")
            ctk.CTkLabel(row1, text=item.get("name", "Sans nom"),
                         font=FONT_H2, text_color=TEXT, anchor="w").pack(side="left")
            ctk.CTkLabel(row1, text=f"  [{kind}]",
                         font=FONT_SEC, text_color=kind_color).pack(side="left")

            ctk.CTkLabel(info, text=item.get("created_at", ""),
                         font=FONT_MU, text_color=MUTED, anchor="w").pack(anchor="w", pady=(2, 8))

            btns = ctk.CTkFrame(info, fg_color="transparent")
            btns.pack(anchor="w")
            _btn(btns, "📂 Ouvrir dossier",
                 lambda f=item.get("folder", ""): open_file(f),
                 small=True, width=130, height=28).pack(side="left", padx=(0, 6))
            _btn(btns, "▶ Ouvrir vidéo",
                 lambda v=item.get("video", ""): open_file(v),
                 small=True, width=110, height=28).pack(side="left", padx=(0, 6))
            _btn(btns, "✕ Supprimer",
                 lambda i=item: self._delete_history_item(i),
                 small=True, width=100, height=28, danger=True).pack(side="left")

    def _thumb_placeholder(self, parent):
        import customtkinter as ctk
        from app.ui.app import SURF3, MUTED
        ph = ctk.CTkFrame(parent, fg_color=SURF3, corner_radius=6,
                          width=160, height=90)
        ph.pack(side="left", padx=(0, 14))
        ph.pack_propagate(False)
        ctk.CTkLabel(ph, text="🎵", font=ctk.CTkFont("Segoe UI", 28),
                     text_color=MUTED).place(relx=0.5, rely=0.5, anchor="center")

    def _sorted_history(self):
        return sorted(self.history, key=lambda x: x.get("created_at", ""), reverse=True)

    def _clear_all_history(self):
        if not self.history:
            return
        n = len(self.history)
        if messagebox.askyesno(
            "Vider l historique",
            f"Supprimer les {n} entrees ? Les fichiers restent sur le disque.",
            icon="warning"
        ):
            self.history.clear()
            self._persist_now()
            self.show_history()

    def _delete_history_item(self, item):
        if messagebox.askyesno("Historique",
                               f"Supprimer '{item.get('name')}' de l'historique ?\n(Fichiers conservés.)"):
            self.history = [h for h in self.history if h.get("folder") != item.get("folder")]
            self._persist_now()
            self.show_history()

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE TURBO
    # ══════════════════════════════════════════════════════════════════════════

    def show_turbo(self):
        import customtkinter as ctk
        import tkinter as tk
        from pathlib import Path
        from app.ui.app import (
            BG, SURF2, SURF3, BORDER, ACCENT, ACCLT, TEXT, MUTED, WARN,
            FONT_H1, FONT_SM, FONT_MU, AUDIO_EXTS, _btn, _card,
        )
        self._clear_main()
        self._turbo_view_active = True
        self._set_status("⚡ Turbo")

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(top, text="⚡ Turbo", font=FONT_H1, text_color="#f59e0b").pack(side="left")
        _btn(top, "← Accueil", self.show_home, small=True, width=120).pack(side="right")
        ctk.CTkLabel(top, text="Production rapide · sans preview",
                     text_color=MUTED, font=FONT_MU).pack(side="left", padx=(14, 0))

        ctrl = _card(outer)
        ctrl.pack(fill="x", pady=(0, 10))
        ci = ctk.CTkFrame(ctrl, fg_color="transparent")
        ci.pack(fill="x", padx=16, pady=12)

        r1 = ctk.CTkFrame(ci, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(r1, text="Pochette", text_color=MUTED, font=FONT_MU, width=60, anchor="w").pack(side="left")
        self._turbo_img_var = tk.StringVar(value=Path(self._turbo_image).name if self._turbo_image else "")
        turbo_img_entry = ctk.CTkEntry(r1, textvariable=self._turbo_img_var,
                                        placeholder_text="Obligatoire pour l'export",
                                        fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                                        font=FONT_MU, width=210, state="readonly")
        turbo_img_entry.pack(side="left", padx=(4, 0))
        _btn(r1, "📂", self._turbo_pick_image, small=True, width=32, height=28).pack(side="left", padx=(4, 24))

        ctk.CTkLabel(r1, text="Fond", text_color=MUTED, font=FONT_MU, width=38, anchor="w").pack(side="left")
        self._turbo_bg_var = tk.StringVar(value=Path(self._turbo_bg_image).name if self._turbo_bg_image else "")
        ctk.CTkEntry(r1, textvariable=self._turbo_bg_var,
                     placeholder_text="Image de fond (optionnel)",
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_MU, width=180, state="readonly").pack(side="left", padx=(4, 0))
        _btn(r1, "📂", self._turbo_pick_bg, small=True, width=32, height=28).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(r1, text="Preset ★", text_color=MUTED, font=FONT_MU, width=60, anchor="w").pack(side="left")
        fav_names = [n for n in self.user_presets if n in self.user_preset_favorites]
        if not fav_names:
            fav_names = list(self.user_presets.keys())
        turbo_preset_values = fav_names if fav_names else ["(aucun preset — créez-en un)"]
        self._turbo_preset_var = tk.StringVar(value=turbo_preset_values[0])
        ctk.CTkComboBox(r1, variable=self._turbo_preset_var,
                        values=turbo_preset_values,
                        fg_color=SURF3, border_color=BORDER,
                        button_color=SURF2, button_hover_color=BORDER,
                        dropdown_fg_color=SURF2, text_color=TEXT,
                        font=FONT_SM, width=190).pack(side="left", padx=(4, 6))
        self._turbo_text_badge = ctk.CTkLabel(
            r1, text="● Texte ON", text_color=MUTED, font=FONT_MU, width=72, anchor="w")
        self._turbo_text_badge.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(r1, text="Format", text_color=MUTED, font=FONT_MU, width=50, anchor="w").pack(side="left")
        self._turbo_format_var = tk.StringVar(value="COMPLET")
        ctk.CTkComboBox(r1, variable=self._turbo_format_var,
                        values=["COMPLET", "SHORT", "VERTICAL"],
                        fg_color=SURF3, border_color=BORDER,
                        button_color=SURF2, button_hover_color=BORDER,
                        dropdown_fg_color=SURF2, text_color=TEXT,
                        font=FONT_SM, width=130).pack(side="left", padx=(4, 0))

        self._turbo_preset_var.trace_add("write", lambda *_: self._turbo_update_text_ui())
        self._turbo_update_text_ui()

        r2 = ctk.CTkFrame(ci, fg_color="transparent")
        r2.pack(fill="x", pady=(6, 0))
        _btn(r2, "➕ Ajouter des fichiers", self._turbo_pick_files,
             small=True, height=32, width=185).pack(side="left")
        self._turbo_stop_btn = _btn(r2, "⏹ Stopper", self._turbo_stop_fn,
                                     height=32, width=110, danger=True)
        self._turbo_stop_btn.pack(side="right", padx=(6, 0))
        self._turbo_launch_btn = _btn(r2, "▶ Lancer", self._turbo_start,
                                       accent=True, height=32, width=110)
        self._turbo_launch_btn.pack(side="right")
        _btn(r2, "🖼 Aperçu", self._turbo_preview,
             small=True, height=32, width=100).pack(side="right", padx=(0, 6))

        hdr = ctk.CTkFrame(outer, fg_color=SURF3, corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
        for col_txt, col_w in [("Fichier audio", 168), ("Pochette", 52),
                                ("Artiste", 138), ("Titre", 168), ("Statut", 86)]:
            ctk.CTkLabel(hdr, text=col_txt, text_color=MUTED, font=FONT_MU,
                         width=col_w, anchor="w").pack(side="left", padx=6, pady=5)
        ctk.CTkLabel(hdr, text="", width=42).pack(side="right")

        self._turbo_scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent",
                                                     scrollbar_button_color=SURF3,
                                                     scrollbar_button_hover_color=ACCENT)
        self._turbo_scroll.pack(fill="both", expand=True, pady=(0, 0))

        if self._turbo_queue:
            for item in self._turbo_queue:
                self._turbo_add_row_ui(item)
        else:
            self._turbo_empty_lbl = ctk.CTkLabel(self._turbo_scroll,
                                                  text="Ajoutez des fichiers audio ou glissez-déposez ici.",
                                                  text_color=MUTED, font=FONT_SM)
            self._turbo_empty_lbl.pack(pady=40)

        self._turbo_bottom_bar = ctk.CTkFrame(outer, fg_color="transparent")
        self._turbo_bottom_bar.pack(fill="x", pady=(6, 0))
        if any(it["status"].startswith("✅") for it in self._turbo_queue):
            self._turbo_show_open_folder_btn()

    def _turbo_add_row_ui(self, item: dict):
        import customtkinter as ctk
        from tkinter import filedialog
        from pathlib import Path
        from app.ui.app import SURF3, SURF2, BORDER, TEXT, MUTED, SUCCESS, DANGER, FONT_MU, _btn

        row = ctk.CTkFrame(self._turbo_scroll, fg_color=SURF2, corner_radius=6)
        row.pack(fill="x", pady=2, padx=2)
        item["_row"] = row

        fname = Path(item["audio"]).name
        short = (fname[:22] + "…") if len(fname) > 24 else fname
        ctk.CTkLabel(row, text=short, text_color=TEXT, font=FONT_MU,
                     width=168, anchor="w").pack(side="left", padx=(6, 0))

        def _pick_item_img(i=item):
            path = filedialog.askopenfilename(
                title="Pochette", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("Tous", "*.*")])
            if path:
                i["image"] = path
                try:
                    i["_img_btn"].configure(text="✅", text_color=SUCCESS)
                except Exception:
                    pass

        img_btn = _btn(row, "✅" if item.get("image") else "📂", _pick_item_img,
                       small=True, width=44, height=28)
        img_btn.pack(side="left", padx=4)
        item["_img_btn"] = img_btn

        artist_entry = ctk.CTkEntry(row, textvariable=item["artist_var"],
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_MU, width=130, height=28)
        artist_entry.pack(side="left", padx=(0, 4))
        item["_artist_entry"] = artist_entry

        title_entry = ctk.CTkEntry(row, textvariable=item["title_var"],
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_MU, width=160, height=28)
        title_entry.pack(side="left", padx=(0, 4))
        item["_title_entry"] = title_entry

        # Zone statut : label + bouton dossier (affiché uniquement après complétion)
        status_frame = ctk.CTkFrame(row, fg_color="transparent", width=130)
        status_frame.pack(side="left")
        status_frame.pack_propagate(False)

        status_lbl = ctk.CTkLabel(status_frame, text=item["status"], text_color=MUTED,
                                   font=FONT_MU, anchor="w")
        status_lbl.pack(side="left")
        item["_status_lbl"] = status_lbl

        folder_btn = ctk.CTkButton(
            status_frame, text="📂", width=28, height=22,
            fg_color="transparent", hover_color=SURF3,
            text_color=SUCCESS, font=FONT_MU, corner_radius=4,
            command=lambda: None
        )
        item["_folder_btn"] = folder_btn
        item["_folder_btn_packed"] = False

        def _remove(i=item, r=row):
            if i in self._turbo_queue:
                self._turbo_queue.remove(i)
            try:
                r.destroy()
            except Exception:
                pass

        _btn(row, "✕", _remove, small=True, width=34, height=28, danger=True).pack(
            side="right", padx=(0, 4))

        # Appliquer l'état texte du preset sélectionné
        if hasattr(self, "_turbo_preset_var"):
            _preset = self.user_presets.get(self._turbo_preset_var.get(), {})
            if not bool(_preset.get("show_text", True)):
                try:
                    artist_entry.configure(state="disabled")
                    title_entry.configure(state="disabled")
                except Exception:
                    pass

    def _turbo_add_paths(self, paths: list[str]):
        import tkinter as tk
        from pathlib import Path
        from app.ui.app import AUDIO_EXTS, MUTED, FONT_SM
        import customtkinter as ctk
        added = 0
        for p in paths:
            ext = Path(p).suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            stem = Path(p).stem
            if " - " in stem:
                left, right = stem.split(" - ", 1)
                artist_val, title_val = left.strip(), right.strip()
            else:
                artist_val, title_val = "", stem.strip()
            item = {
                "audio":      p,
                "image":      "",
                "artist_var": tk.StringVar(value=artist_val),
                "title_var":  tk.StringVar(value=title_val),
                "status":     "⏳ En attente",
                "_status_lbl": None,
                "_img_btn":    None,
            }
            self._turbo_queue.append(item)
            if self._turbo_view_active and hasattr(self, "_turbo_scroll"):
                if hasattr(self, "_turbo_empty_lbl") and self._turbo_empty_lbl:
                    try:
                        self._turbo_empty_lbl.destroy()
                    except Exception:
                        pass
                    self._turbo_empty_lbl = None
                self._turbo_add_row_ui(item)
            added += 1
        if added:
            self._set_status(f"⚡ Turbo — {len(self._turbo_queue)} fichier(s)")

    def show_presets(self):
        pass

    def _presets_refresh_list(self):
        pass

    def _presets_show_placeholder(self):
        pass

    def _presets_show_editor(self, preset_data, preset_name: str):
        pass

    def _presets_delete(self, name: str):
        pass

    def _apply_global_preset_by_name(self, name: str):
        self._apply_builtin_preset(name)
