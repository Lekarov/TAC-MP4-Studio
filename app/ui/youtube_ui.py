"""YoutubeMixin — upload programmé de vidéos vers YouTube.

Deux points d'entrée depuis l'accueil : upload manuel (un fichier) ou upload
dossier (scan + anti-doublon). Avant publication : édition titre/description/
tags/date par vidéo, avec des "profils" (description + tags par défaut)
réutilisables. La date de publication de chaque vidéo suivante = J+1 par
rapport à la précédente.
"""
from __future__ import annotations

import heapq
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox

import requests

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

DATE_FMT = "%Y-%m-%d"
NO_PLAYLIST_KEY = "__no_playlist__"
NO_PLAYLIST_LABEL = "Sans playlist"


def _clean_title(stem: str) -> str:
    return " ".join(stem.replace("_", " ").replace("-", " ").split())


def _parse_publish_at(value: str) -> datetime:
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    if "." in v:  # microsecondes éventuelles (ex: 2026-09-20T09:00:00.000+00:00)
        head, tail = v.split(".", 1)
        sign_idx = max(tail.find("+"), tail.find("-"))
        v = head + (tail[sign_idx:] if sign_idx != -1 else "")
    return datetime.fromisoformat(v)


def _format_publish_at(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _diversify_order(groups: dict[str, list]) -> list:
    """Réordonne les éléments en alternant les groupes autant que possible,
    sans jamais répéter un même groupe consécutivement tant qu'une
    alternative existe (algorithme glouton par tas, type « Reorganize
    String »). Les répétitions ne surviennent que si un groupe est trop
    dominant pour être totalement étalé."""
    heap = []
    queues: dict[str, deque] = {}
    for key, items in groups.items():
        if not items:
            continue
        queues[key] = deque(items)
        heapq.heappush(heap, (-len(items), key))

    result = []
    prev = None
    while heap:
        count, key = heapq.heappop(heap)
        result.append(queues[key].popleft())
        count += 1
        if prev is not None:
            heapq.heappush(heap, prev)
        prev = (count, key) if count < 0 else None
    if prev is not None:
        result.extend(queues[prev[1]])
    return result


def _format_youtube_error(exc) -> str:
    """Extrait le message d'erreur détaillé de Google (JSON) si présent,
    pour afficher la vraie cause plutôt qu'un message générique."""
    import json
    base = getattr(exc, "message", str(exc))
    detail = getattr(exc, "detail", "") or ""
    try:
        body = json.loads(detail)
        err = body.get("error", {})
        errors = err.get("errors", [])
        reason = errors[0].get("reason", "") if errors else ""
        msg = err.get("message", "")
        if msg:
            return f"{base}\n\n{msg}" + (f"\n(reason: {reason})" if reason else "")
    except (ValueError, AttributeError):
        pass
    if detail:
        return f"{base}\n\n{detail[:400]}"
    return base


def _history_key(path: str) -> str:
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        size = 0
    return f"{p.name}|{size}"


class YoutubeMixin:

    # ══════════════════════════════════════════════════════════════════════════
    # CHOIX
    # ══════════════════════════════════════════════════════════════════════════

    def show_youtube_choice(self):
        import customtkinter as ctk
        from app.ui.app import (
            BG, SURF2, BORDER, TEXT, MUTED, FONT_H1, FONT_H2, FONT_SM, FONT_MU, _btn,
        )
        self._clear_main()
        self._set_status("📺 YouTube")

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", padx=32, pady=(20, 0))
        _btn(top, "← Accueil", self.show_home, small=True, width=120).pack(side="right")
        _btn(top, "👤 Profils", self.show_youtube_profiles, small=True, width=120).pack(side="right", padx=(0, 8))

        center = ctk.CTkFrame(outer, fg_color="transparent")
        center.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(center, text="📺 Publier sur YouTube", font=FONT_H1,
                     text_color=TEXT).pack(pady=(0, 4))
        ctk.CTkLabel(center, text="Choisissez comment sélectionner vos vidéos",
                     text_color=MUTED, font=FONT_SM).pack(pady=(0, 26))

        row = ctk.CTkFrame(center, fg_color="transparent")
        row.pack()

        def _choice_card(parent, title, desc, command):
            card = ctk.CTkFrame(parent, fg_color=SURF2, corner_radius=14,
                                border_color=BORDER, border_width=1,
                                width=260, height=180)
            card.pack(side="left", padx=12)
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=title, font=FONT_H2, text_color=TEXT,
                         wraplength=220, justify="center").pack(pady=(24, 8), padx=16)
            ctk.CTkLabel(card, text=desc, text_color=MUTED, font=FONT_MU,
                         wraplength=210, justify="center").pack(padx=16)
            _btn(card, "Choisir", command, accent=True, width=160,
                 height=36).pack(side="bottom", pady=16)
            return card

        _choice_card(
            row, "🎬 Upload manuel",
            "Sélectionnez un fichier vidéo précis à publier.",
            self._youtube_pick_manual)
        _choice_card(
            row, "📁 Upload dossier",
            "Choisissez un dossier : seules les vidéos jamais publiées "
            "sont proposées.",
            self._youtube_pick_folder)
        _choice_card(
            row, "📚 Mes vidéos",
            "Parcourez vos playlists et vidéos déjà en ligne "
            "(privées, programmées...) et modifiez titre/description/tags.",
            self.show_youtube_library)

        if not self._youtube_authorized():
            warn = ctk.CTkFrame(center, fg_color="#431407", corner_radius=8)
            warn.pack(fill="x", pady=(24, 0))
            ctk.CTkLabel(warn, text="⚠  Compte YouTube non autorisé.",
                         text_color="#fdba74", font=FONT_SM).pack(side="left", padx=12, pady=8)
            _btn(warn, "Autoriser", self.show_youtube_auth, small=True, width=110,
                 fg_color="transparent", hover_color="#7c2d12").pack(side="right", padx=10)

    def _youtube_pick_manual(self):
        path = filedialog.askopenfilename(
            title="Choisir une vidéo",
            filetypes=[("Vidéos", " ".join(f"*{e}" for e in VIDEO_EXTS)), ("Tous", "*.*")],
        )
        if not path:
            return
        self._youtube_queue = []
        self._youtube_add_to_queue(path)
        self.show_youtube_queue()

    def _youtube_pick_folder(self):
        folder = filedialog.askdirectory(title="Choisir un dossier de vidéos")
        if not folder:
            return
        history = self.youtube_history
        found = []
        skipped = 0
        for p in sorted(Path(folder).iterdir()):
            if p.suffix.lower() not in VIDEO_EXTS:
                continue
            if _history_key(str(p)) in history:
                skipped += 1
                continue
            found.append(str(p))

        if not found:
            messagebox.showinfo(
                "Upload dossier",
                f"Aucune vidéo nouvelle dans ce dossier.\n"
                f"({skipped} déjà publiée(s) précédemment.)" if skipped else
                "Aucune vidéo trouvée dans ce dossier.")
            return

        self._youtube_queue = []
        for p in found:
            self._youtube_add_to_queue(p)
        self.show_youtube_queue()
        if skipped:
            self._set_status(f"📺 {len(found)} nouvelle(s), {skipped} déjà publiée(s)")

    def _youtube_add_to_queue(self, path: str):
        import tkinter as tk
        active = self.youtube_profiles.get(self._youtube_active_profile, {})
        item = {
            "path": path,
            "title_var": tk.StringVar(value=_clean_title(Path(path).stem)),
            "tags_var": tk.StringVar(value=", ".join(active.get("tags", []))),
            "date_var": tk.StringVar(value=""),
            "description": active.get("description", ""),
            "status": "En attente",
        }
        self._youtube_queue.append(item)

    # ══════════════════════════════════════════════════════════════════════════
    # FILE D'ATTENTE — édition avant publication
    # ══════════════════════════════════════════════════════════════════════════

    def show_youtube_queue(self):
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import (
            BG, SURF2, SURF3, BORDER, ACCENT, ACCLT, TEXT, MUTED, SUCCESS, WARN,
            FONT_H1, FONT_H2, FONT_SM, FONT_MU, _btn, _card,
        )
        self._clear_main()
        self._set_status(f"📺 {len(self._youtube_queue)} vidéo(s) à publier")

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(top, text="📺 File de publication", font=FONT_H1, text_color=TEXT).pack(side="left")
        _btn(top, "← YouTube", self.show_youtube_choice, small=True, width=120).pack(side="right")

        if not self._youtube_queue:
            ctk.CTkLabel(outer, text="File vide.", text_color=MUTED, font=FONT_SM).pack(pady=40)
            return

        # ── Réglages globaux : profil + date de départ ──────────────────────
        ctrl = _card(outer)
        ctrl.pack(fill="x", pady=(0, 10))
        ci = ctk.CTkFrame(ctrl, fg_color="transparent")
        ci.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(ci, text="Profil", text_color=MUTED, font=FONT_MU).pack(side="left", padx=(0, 6))
        profile_names = list(self.youtube_profiles.keys()) or ["(aucun — créez-en un)"]
        self._youtube_profile_var = tk.StringVar(value=self._youtube_active_profile or profile_names[0])
        ctk.CTkComboBox(ci, variable=self._youtube_profile_var, values=profile_names,
                        fg_color=SURF3, border_color=BORDER, button_color=SURF2,
                        button_hover_color=BORDER, dropdown_fg_color=SURF2,
                        text_color=TEXT, font=FONT_SM, width=180).pack(side="left", padx=(0, 6))
        _btn(ci, "Appliquer à tous", self._youtube_apply_profile_to_all,
             small=True, width=130, height=28).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(ci, text="Date de départ", text_color=MUTED, font=FONT_MU).pack(side="left", padx=(0, 6))
        default_start = self._youtube_next_start_date()
        self._youtube_start_date_var = tk.StringVar(value=default_start)
        ctk.CTkEntry(ci, textvariable=self._youtube_start_date_var,
                     placeholder_text="AAAA-MM-JJ", fg_color=SURF3, border_color=BORDER,
                     text_color=TEXT, font=FONT_SM, width=110).pack(side="left", padx=(0, 6))
        _btn(ci, "Appliquer J+1", self._youtube_apply_dates,
             small=True, width=120, height=28).pack(side="left", padx=(0, 20))

        self._youtube_sync_btn = _btn(ci, "🔄 Synchro YouTube", self._youtube_sync_last_date,
                                      small=True, width=170, height=28,
                                      fg_color="#0f3460", hover_color="#144272")
        self._youtube_sync_btn.pack(side="left")
        try:
            from app.ui.app import _Tooltip
            _Tooltip(self._youtube_sync_btn,
                     "Va chercher sur YouTube la date de ta dernière vidéo\n"
                     "déjà programmée, et règle le départ sur le lendemain.")
        except Exception:
            pass

        # ── Liste des vidéos ─────────────────────────────────────────────────
        hdr = ctk.CTkFrame(outer, fg_color=SURF3, corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
        for col_txt, col_w in [("Fichier", 200), ("Titre", 220), ("Tags", 180),
                                ("Date pub.", 100), ("Statut", 100)]:
            ctk.CTkLabel(hdr, text=col_txt, text_color=MUTED, font=FONT_MU,
                         width=col_w, anchor="w").pack(side="left", padx=6, pady=5)

        self._youtube_scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent",
                                                       scrollbar_button_color=SURF3,
                                                       scrollbar_button_hover_color=ACCENT)
        self._youtube_scroll.pack(fill="both", expand=True, pady=(0, 8))

        for item in self._youtube_queue:
            self._youtube_add_row_ui(item)

        self._youtube_apply_dates()

        bottom = ctk.CTkFrame(outer, fg_color="transparent")
        bottom.pack(fill="x")
        self._youtube_launch_btn = _btn(bottom, "▶ Publier tout", self._youtube_start_upload,
                                        accent=True, height=42, width=160)
        self._youtube_launch_btn.pack(side="right")

    def _youtube_add_row_ui(self, item: dict):
        import customtkinter as ctk
        from app.ui.app import SURF2, SURF3, BORDER, TEXT, MUTED, SUCCESS, FONT_MU, _btn

        row = ctk.CTkFrame(self._youtube_scroll, fg_color=SURF2, corner_radius=6)
        row.pack(fill="x", pady=2, padx=2)
        item["_row"] = row

        fname = Path(item["path"]).name
        short = (fname[:26] + "…") if len(fname) > 28 else fname
        ctk.CTkLabel(row, text=short, text_color=TEXT, font=FONT_MU,
                     width=200, anchor="w").pack(side="left", padx=(6, 0))

        ctk.CTkEntry(row, textvariable=item["title_var"], fg_color=SURF3,
                     border_color=BORDER, text_color=TEXT, font=FONT_MU,
                     width=220, height=28).pack(side="left", padx=(0, 4))

        ctk.CTkEntry(row, textvariable=item["tags_var"], fg_color=SURF3,
                     border_color=BORDER, text_color=TEXT, font=FONT_MU,
                     width=180, height=28).pack(side="left", padx=(0, 4))

        ctk.CTkEntry(row, textvariable=item["date_var"], fg_color=SURF3,
                     border_color=BORDER, text_color=TEXT, font=FONT_MU,
                     width=100, height=28).pack(side="left", padx=(0, 4))

        status_lbl = ctk.CTkLabel(row, text=item["status"], text_color=MUTED,
                                   font=FONT_MU, width=100, anchor="w")
        status_lbl.pack(side="left")
        item["_status_lbl"] = status_lbl

        def _edit_desc(i=item):
            self._youtube_edit_description(i)
        _btn(row, "📝", _edit_desc, small=True, width=32, height=28).pack(side="left", padx=(4, 0))

        def _remove(i=item, r=row):
            if i in self._youtube_queue:
                self._youtube_queue.remove(i)
            try:
                r.destroy()
            except Exception:
                pass

        _btn(row, "✕", _remove, small=True, width=32, height=28, danger=True).pack(
            side="right", padx=(4, 4))

    def _youtube_edit_description(self, item: dict):
        import customtkinter as ctk
        from app.ui.app import BG, SURF3, BORDER, TEXT, MUTED, FONT_H2, FONT_SM, _btn

        win = ctk.CTkToplevel(self)
        win.title(f"Description — {Path(item['path']).name}")
        win.configure(fg_color=BG)
        win.geometry("520x420")
        win.grab_set()

        ctk.CTkLabel(win, text="Description", font=FONT_H2, text_color=TEXT).pack(
            anchor="w", padx=16, pady=(16, 4))
        box = ctk.CTkTextbox(win, fg_color=SURF3, border_color=BORDER, border_width=1,
                             text_color=TEXT, font=FONT_SM, wrap="word")
        box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        box.insert("1.0", item.get("description", ""))

        def _save():
            item["description"] = box.get("1.0", "end-1c")
            win.destroy()

        _btn(win, "Enregistrer", _save, accent=True, height=36).pack(
            fill="x", padx=16, pady=(0, 16))

    # ── Profils : appliquer / dates ──────────────────────────────────────────

    def _youtube_apply_profile_to_all(self):
        name = self._youtube_profile_var.get()
        profile = self.youtube_profiles.get(name)
        if not profile:
            messagebox.showwarning("Profil", "Créez d'abord un profil (bouton Profils).")
            return
        self._youtube_active_profile = name
        for item in self._youtube_queue:
            item["tags_var"].set(", ".join(profile.get("tags", [])))
            item["description"] = profile.get("description", "")
        messagebox.showinfo("Profil", f"Profil « {name} » appliqué à {len(self._youtube_queue)} vidéo(s).")

    def _youtube_next_start_date(self) -> str:
        last = self.youtube_last_scheduled_date
        today = datetime.now().date()
        if last:
            try:
                last_date = datetime.strptime(last, DATE_FMT).date()
                candidate = last_date + timedelta(days=1)
                return max(candidate, today).strftime(DATE_FMT)
            except ValueError:
                pass
        return today.strftime(DATE_FMT)

    def _youtube_apply_dates(self):
        try:
            base = datetime.strptime(self._youtube_start_date_var.get().strip(), DATE_FMT).date()
        except ValueError:
            messagebox.showerror("Date", "Format attendu : AAAA-MM-JJ")
            return
        for idx, item in enumerate(self._youtube_queue):
            d = base + timedelta(days=idx)
            item["date_var"].set(d.strftime(DATE_FMT))

    def _youtube_sync_last_date(self):
        """Va chercher sur YouTube la date de la dernière vidéo encore programmée
        (privée + date future) et règle la date de départ sur le lendemain —
        évite de devoir retourner vérifier sur YouTube à la main."""
        if not self._youtube_authorized():
            messagebox.showwarning("YouTube", "Autorisez d'abord votre compte YouTube.")
            self.show_youtube_auth()
            return

        self._youtube_sync_btn.configure(state="disabled", text="🔄 Recherche...")

        def _reset_btn():
            self._youtube_sync_btn.configure(state="normal", text="🔄 Synchro YouTube")

        def worker():
            from app import youtube_api
            from app.errors import YoutubeAuthError, YoutubeError

            token = self._youtube_lib_token()
            if not token:
                self.after(0, self._youtube_lib_auth_expired)
                self.after(0, _reset_btn)
                return
            try:
                uploads_id = youtube_api.get_uploads_playlist_id(token)
                ids = youtube_api.list_playlist_video_ids(token, uploads_id)
                videos = youtube_api.get_videos_details(token, ids) if ids else []
            except YoutubeAuthError:
                self.after(0, self._youtube_lib_auth_expired)
                self.after(0, _reset_btn)
                return
            except YoutubeError as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Synchro YouTube", _format_youtube_error(e)))
                self.after(0, _reset_btn)
                return

            now = datetime.now(timezone.utc)
            future_dates = []
            for v in videos:
                if v["privacy_status"] != "private" or not v.get("publish_at"):
                    continue
                try:
                    dt = _parse_publish_at(v["publish_at"])
                except ValueError:
                    continue
                if dt > now:
                    future_dates.append(dt)

            if not future_dates:
                self.after(0, lambda: messagebox.showinfo(
                    "Synchro YouTube",
                    "Aucune vidéo programmée à venir trouvée sur la chaîne.\n"
                    "La date de départ n'a pas été modifiée."))
                self.after(0, _reset_btn)
                return

            last = max(future_dates).date()
            next_date = max(last + timedelta(days=1), datetime.now().date())

            def _apply():
                self._youtube_start_date_var.set(next_date.strftime(DATE_FMT))
                self._youtube_apply_dates()
                messagebox.showinfo(
                    "Synchro YouTube",
                    f"Dernière vidéo programmée trouvée : {last.strftime(DATE_FMT)}.\n"
                    f"Date de départ mise à jour : {next_date.strftime(DATE_FMT)}.")

            self.after(0, _apply)
            self.after(0, _reset_btn)

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # UPLOAD
    # ══════════════════════════════════════════════════════════════════════════

    def _youtube_authorized(self) -> bool:
        from app import youtube_auth
        return youtube_auth.has_refresh_token()

    def _youtube_start_upload(self):
        from app.ui.app import DANGER, SUCCESS, WARN

        if not self._youtube_queue:
            return
        if not self._youtube_authorized():
            messagebox.showwarning("YouTube", "Autorisez d'abord votre compte YouTube.")
            self.show_youtube_auth()
            return
        for item in self._youtube_queue:
            if not item["title_var"].get().strip():
                messagebox.showerror("Titre manquant", f"Titre vide pour {Path(item['path']).name}")
                return
            try:
                datetime.strptime(item["date_var"].get().strip(), DATE_FMT)
            except ValueError:
                messagebox.showerror("Date invalide", f"Date invalide pour {Path(item['path']).name}")
                return

        self._youtube_launch_btn.configure(state="disabled")
        items = list(self._youtube_queue)

        def worker():
            from app import youtube_auth, youtube_upload
            from app.errors import YoutubeError

            client_id = self.config_data.get("youtube_oauth_client_id", "")
            client_secret = self.config_data.get("youtube_oauth_client_secret", "")
            ok_count = 0
            last_date = self.youtube_last_scheduled_date

            for item in items:
                self.after(0, lambda i=item: self._youtube_set_row_status(i, "⏳ Upload...", WARN))
                access_token = youtube_auth.get_access_token(client_id, client_secret)
                if not access_token:
                    self.after(0, lambda i=item: self._youtube_set_row_status(i, "✕ Non autorisé", DANGER))
                    continue

                date_str = item["date_var"].get().strip()
                publish_dt = datetime.strptime(date_str, DATE_FMT)
                publish_at_iso = publish_dt.strftime("%Y-%m-%dT09:00:00Z")
                tags = [t.strip() for t in item["tags_var"].get().split(",") if t.strip()]

                try:
                    video_id = youtube_upload.upload_video(
                        access_token=access_token,
                        file_path=item["path"],
                        title=item["title_var"].get().strip(),
                        description=item.get("description", ""),
                        tags=tags,
                        publish_at_iso=publish_at_iso,
                        progress_callback=lambda p, i=item: self.after(
                            0, lambda: self._youtube_set_row_status(
                                i, f"⏳ {int(p * 100)}%", WARN)),
                    )
                except YoutubeError as exc:
                    self.after(0, lambda i=item, m=exc.message: self._youtube_set_row_status(i, f"✕ {m}", DANGER))
                    continue
                except Exception as exc:
                    self.after(0, lambda i=item, m=str(exc): self._youtube_set_row_status(i, f"✕ {m}", DANGER))
                    continue

                self.youtube_history[_history_key(item["path"])] = {
                    "title": item["title_var"].get().strip(),
                    "youtube_id": video_id,
                    "scheduled_date": date_str,
                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                last_date = date_str
                ok_count += 1
                self.after(0, lambda i=item: self._youtube_set_row_status(i, "✅ Publiée", SUCCESS))

            self.youtube_last_scheduled_date = last_date
            self.after(0, self._persist_now)
            self.after(0, lambda: self._youtube_launch_btn.configure(state="normal"))
            self.after(0, lambda: messagebox.showinfo(
                "Upload terminé", f"{ok_count}/{len(items)} vidéo(s) publiée(s) avec succès."))

        threading.Thread(target=worker, daemon=True).start()

    def _youtube_set_row_status(self, item: dict, text: str, color) -> None:
        item["status"] = text
        lbl = item.get("_status_lbl")
        if lbl is not None:
            try:
                lbl.configure(text=text, text_color=color)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # AUTORISATION
    # ══════════════════════════════════════════════════════════════════════════

    def show_youtube_auth(self):
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import BG, SURF2, BORDER, TEXT, MUTED, ACCLT, FONT_H1, FONT_H2, FONT_SM, _btn, _card

        self._clear_main()
        self._set_status("📺 Autorisation YouTube")

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True)
        _btn(outer, "← YouTube", self.show_youtube_choice, small=True, width=120).place(x=32, y=20)

        center = ctk.CTkFrame(outer, fg_color="transparent")
        center.place(relx=0.5, rely=0.44, anchor="center")

        ctk.CTkLabel(center, text="Autoriser l'accès YouTube", font=FONT_H1,
                     text_color=TEXT).pack(pady=(0, 16))

        client_id = self.config_data.get("youtube_oauth_client_id", "")
        client_secret = self.config_data.get("youtube_oauth_client_secret", "")
        if not client_id or not client_secret:
            ctk.CTkLabel(center,
                         text="Identifiants OAuth Google manquants.\n"
                              "Ajoutez youtube_oauth_client_id / youtube_oauth_client_secret\n"
                              "dans la configuration.",
                         text_color=MUTED, font=FONT_SM, justify="center").pack(pady=20)
            return

        info_card = _card(center)
        info_card.pack(pady=(0, 16), ipadx=16, ipady=16)
        info_inner = ctk.CTkFrame(info_card, fg_color="transparent")
        info_inner.pack(padx=20, pady=14)

        self._youtube_auth_status_lbl = ctk.CTkLabel(
            info_inner, text="Cliquez pour démarrer l'autorisation.",
            text_color=MUTED, font=FONT_SM, wraplength=380, justify="center")
        self._youtube_auth_status_lbl.pack(pady=(0, 10))

        # Lien + code copiables — cachés tant que l'autorisation n'a pas démarré
        self._youtube_auth_fields = ctk.CTkFrame(info_inner, fg_color="transparent")

        def _copyable_row(parent, label_text):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label_text, text_color=MUTED, font=FONT_SM,
                         width=50, anchor="w").pack(side="left")
            var = tk.StringVar(value="")
            entry = ctk.CTkEntry(row, textvariable=var, fg_color=SURF2,
                                  border_color=BORDER, text_color=TEXT,
                                  font=FONT_SM, width=260)
            entry.pack(side="left", padx=(4, 6))

            def _copy():
                self.clipboard_clear()
                self.clipboard_append(var.get())
                copy_btn.configure(text="✓ Copié")
                self.after(1500, lambda: copy_btn.configure(text="📋 Copier"))

            copy_btn = _btn(row, "📋 Copier", _copy, small=True, width=90, height=28)
            copy_btn.pack(side="left")
            return var, entry

        self._youtube_auth_url_var, url_entry = _copyable_row(self._youtube_auth_fields, "Lien")
        self._youtube_auth_code_var, code_entry = _copyable_row(self._youtube_auth_fields, "Code")
        for e in (url_entry, code_entry):
            e.bind("<FocusIn>", lambda ev, w=e: w.select_range(0, "end"))

        self._youtube_auth_btn = _btn(center, "Démarrer l'autorisation", self._youtube_start_auth,
                                       accent=True, width=260, height=44)
        self._youtube_auth_btn.pack()

    def _youtube_start_auth(self):
        from app import youtube_auth
        from app.errors import YoutubeError

        client_id = self.config_data.get("youtube_oauth_client_id", "")
        client_secret = self.config_data.get("youtube_oauth_client_secret", "")
        self._youtube_auth_btn.configure(state="disabled")

        try:
            device = youtube_auth.start_device_flow(client_id)
        except YoutubeError as exc:
            messagebox.showerror("Autorisation", exc.message)
            self._youtube_auth_btn.configure(state="normal")
            return

        url = device.get("verification_url", "https://google.com/device")
        code = device.get("user_code", "?")
        self._youtube_auth_url_var.set(url)
        self._youtube_auth_code_var.set(code)
        self._youtube_auth_fields.pack(pady=(0, 4))
        self._youtube_auth_status_lbl.configure(
            text="Ouvrez le lien, entrez le code, puis validez.\nEn attente de validation...")

        def worker():
            ok, message = youtube_auth.poll_for_token(
                client_id, client_secret,
                device.get("device_code", ""),
                int(device.get("interval", 5)),
                int(device.get("expires_in", 600)),
            )
            self.after(0, lambda: self._youtube_auth_status_lbl.configure(text=message))
            self.after(0, lambda: self._youtube_auth_btn.configure(state="normal"))
            if ok:
                self.after(0, lambda: messagebox.showinfo("YouTube", message))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # BIBLIOTHÈQUE — playlists + vidéos déjà en ligne (privé/programmé/...)
    # ══════════════════════════════════════════════════════════════════════════

    _PRIVACY_LABELS = {
        "public": "🌍 Publique",
        "unlisted": "🔗 Non répertoriée",
        "private": "🔒 Privée",
    }
    _FILTER_OPTIONS = ["Toutes", "🌍 Publique", "🔗 Non répertoriée", "🔒 Privée", "⏰ Programmée"]

    def show_youtube_library(self):
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import (
            BG, SURF2, SURF3, BORDER, ACCENT, TEXT, MUTED, FONT_H1, FONT_H2, FONT_SM, FONT_MU, _btn, _card,
        )

        if not self._youtube_authorized():
            messagebox.showwarning("YouTube", "Autorisez d'abord votre compte YouTube.")
            self.show_youtube_auth()
            return

        self._clear_main()
        self._set_status("📚 Mes vidéos YouTube")

        self._youtube_lib_videos: list[dict] = []
        self._youtube_lib_playlist_id: str | None = None  # None = uploads (toutes)

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(top, text="📚 Mes vidéos", font=FONT_H1, text_color=TEXT).pack(side="left")
        _btn(top, "← YouTube", self.show_youtube_choice, small=True, width=120).pack(side="right")
        _btn(top, "🔁 Rafraîchir", lambda: self._youtube_lib_load_playlists(),
             small=True, width=130).pack(side="right", padx=(0, 8))
        _btn(top, "🔀 Réorganiser (diversifier)", self._youtube_reschedule_start,
             small=True, width=210, accent=True).pack(side="right", padx=(0, 8))

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # ── Colonne gauche : playlists ───────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=SURF2, corner_radius=10,
                            border_color=BORDER, border_width=1, width=220)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="Playlists", text_color=MUTED, font=FONT_MU,
                     anchor="w").pack(fill="x", padx=12, pady=(12, 4))
        self._youtube_lib_playlist_scroll = ctk.CTkScrollableFrame(
            left, fg_color="transparent", scrollbar_button_color=SURF3,
            scrollbar_button_hover_color=ACCENT)
        self._youtube_lib_playlist_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # ── Colonne droite : filtre + vidéos ─────────────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        filter_row = ctk.CTkFrame(right, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 8))
        self._youtube_lib_title_lbl = ctk.CTkLabel(filter_row, text="Toutes les vidéos",
                                                    text_color=TEXT, font=FONT_H2)
        self._youtube_lib_title_lbl.pack(side="left")
        ctk.CTkLabel(filter_row, text="Filtre", text_color=MUTED, font=FONT_MU).pack(
            side="left", padx=(20, 6))
        self._youtube_lib_filter_var = tk.StringVar(value="Toutes")
        ctk.CTkComboBox(filter_row, variable=self._youtube_lib_filter_var,
                        values=self._FILTER_OPTIONS, command=lambda _: self._youtube_lib_render(),
                        fg_color=SURF3, border_color=BORDER, button_color=SURF2,
                        button_hover_color=BORDER, dropdown_fg_color=SURF2,
                        text_color=TEXT, font=FONT_SM, width=180).pack(side="left")

        self._youtube_lib_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", scrollbar_button_color=SURF3,
            scrollbar_button_hover_color=ACCENT)
        self._youtube_lib_scroll.pack(fill="both", expand=True)
        self._youtube_lib_loading_lbl = ctk.CTkLabel(
            self._youtube_lib_scroll, text="Chargement...", text_color=MUTED, font=FONT_SM)
        self._youtube_lib_loading_lbl.pack(pady=40)

        self._youtube_lib_load_playlists()

    def _youtube_lib_token(self) -> str | None:
        from app import youtube_auth
        client_id = self.config_data.get("youtube_oauth_client_id", "")
        client_secret = self.config_data.get("youtube_oauth_client_secret", "")
        return youtube_auth.get_access_token(client_id, client_secret)

    def _youtube_lib_load_playlists(self):
        import customtkinter as ctk
        from app.ui.app import SURF3, ACCENT, TEXT, MUTED, FONT_SM, _btn

        for w in self._youtube_lib_playlist_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._youtube_lib_playlist_scroll, text="Chargement...",
                     text_color=MUTED, font=FONT_SM).pack(pady=10)
        self._youtube_lib_select_playlist(None, "Toutes les vidéos")

        def worker():
            from app import youtube_api
            from app.errors import YoutubeAuthError, YoutubeError
            token = self._youtube_lib_token()
            if not token:
                self.after(0, lambda: self._youtube_lib_auth_expired())
                return
            try:
                playlists = youtube_api.list_playlists(token)
            except YoutubeAuthError:
                self.after(0, lambda: self._youtube_lib_auth_expired())
                return
            except YoutubeError as exc:
                self.after(0, lambda e=exc: self._youtube_lib_error(e))
                return
            self.after(0, lambda: self._youtube_lib_render_playlists(playlists))

        threading.Thread(target=worker, daemon=True).start()

    def _youtube_lib_render_playlists(self, playlists: list[dict]):
        import customtkinter as ctk
        from app.ui.app import SURF3, ACCENT, ACCLT, TEXT, MUTED, FONT_SM, FONT_MU, _btn

        for w in self._youtube_lib_playlist_scroll.winfo_children():
            w.destroy()

        def _entry(text, playlist_id):
            b = ctk.CTkButton(
                self._youtube_lib_playlist_scroll, text=text, anchor="w",
                fg_color="transparent", hover_color=SURF3, text_color=TEXT,
                font=FONT_SM, corner_radius=6, height=30,
                command=lambda: self._youtube_lib_select_playlist(playlist_id, text))
            b.pack(fill="x", pady=1)

        _entry("📼 Toutes les vidéos", None)
        for pl in playlists:
            label = f"{pl['title']} ({pl['item_count']})"
            _entry(label, pl["id"])

    def _youtube_lib_select_playlist(self, playlist_id: str | None, title: str):
        import customtkinter as ctk
        from app.ui.app import MUTED, FONT_SM

        self._youtube_lib_playlist_id = playlist_id
        self._youtube_lib_title_lbl.configure(text=title.split(" (")[0] if title else "Toutes les vidéos")

        for w in self._youtube_lib_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._youtube_lib_scroll, text="Chargement des vidéos...",
                     text_color=MUTED, font=FONT_SM).pack(pady=40)

        def worker():
            from app import youtube_api
            from app.errors import YoutubeAuthError, YoutubeError
            token = self._youtube_lib_token()
            if not token:
                self.after(0, lambda: self._youtube_lib_auth_expired())
                return
            try:
                if playlist_id:
                    video_ids = youtube_api.list_playlist_video_ids(token, playlist_id)
                else:
                    uploads_id = youtube_api.get_uploads_playlist_id(token)
                    video_ids = youtube_api.list_playlist_video_ids(token, uploads_id)
                videos = youtube_api.get_videos_details(token, video_ids) if video_ids else []
            except YoutubeAuthError:
                self.after(0, lambda: self._youtube_lib_auth_expired())
                return
            except YoutubeError as exc:
                self.after(0, lambda e=exc: self._youtube_lib_error(e))
                return

            # Téléchargement des miniatures (best-effort, thread déjà en arrière-plan)
            for v in videos:
                v["_thumb_bytes"] = None
                url = v.get("thumbnail_url")
                if url:
                    try:
                        r = requests.get(url, timeout=10)
                        if r.status_code == 200:
                            v["_thumb_bytes"] = r.content
                    except Exception:
                        pass

            self.after(0, lambda: self._youtube_lib_set_videos(videos))

        threading.Thread(target=worker, daemon=True).start()

    def _youtube_lib_set_videos(self, videos: list[dict]):
        self._youtube_lib_videos = videos
        self._youtube_lib_render()

    def _youtube_lib_auth_expired(self):
        if messagebox.askyesno(
                "Autorisation insuffisante",
                "Le compte YouTube n'a pas (ou plus) les droits nécessaires "
                "pour lire vos vidéos. Relancer l'autorisation maintenant ?"):
            from app import youtube_auth
            youtube_auth.forget_token()
            self.show_youtube_auth()
        else:
            self.show_youtube_choice()

    def _youtube_lib_error(self, exc):
        from app.logger import log_exception
        log_exception(exc, context="youtube_library")
        messagebox.showerror("YouTube", _format_youtube_error(exc))
        for w in self._youtube_lib_scroll.winfo_children():
            w.destroy()

    def _youtube_lib_render(self):
        import customtkinter as ctk
        from PIL import Image
        from app.ui.app import SURF2, SURF3, BORDER, ACCLT, TEXT, MUTED, SUCCESS, WARN, FONT_H2, FONT_SM, FONT_MU, _btn, _card

        for w in self._youtube_lib_scroll.winfo_children():
            w.destroy()

        filt = self._youtube_lib_filter_var.get()

        def _matches(v):
            if filt == "Toutes":
                return True
            if filt == "⏰ Programmée":
                return v["privacy_status"] == "private" and bool(v.get("publish_at"))
            return self._PRIVACY_LABELS.get(v["privacy_status"]) == filt

        shown = [v for v in self._youtube_lib_videos if _matches(v)]

        if not shown:
            ctk.CTkLabel(self._youtube_lib_scroll, text="Aucune vidéo pour ce filtre.",
                         text_color=MUTED, font=FONT_SM).pack(pady=40)
            return

        for v in shown:
            card = _card(self._youtube_lib_scroll)
            card.pack(fill="x", pady=5, padx=2)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)

            thumb_bytes = v.get("_thumb_bytes")
            if thumb_bytes:
                try:
                    import io
                    img = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
                    img.thumbnail((160, 90))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 90))
                    ctk.CTkLabel(inner, image=ctk_img, text="").pack(side="left", padx=(0, 14))
                except Exception:
                    self._thumb_placeholder(inner)
            else:
                self._thumb_placeholder(inner)

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            row1 = ctk.CTkFrame(info, fg_color="transparent")
            row1.pack(fill="x", anchor="w")
            ctk.CTkLabel(row1, text=v["title"], font=FONT_H2, text_color=TEXT,
                         anchor="w", wraplength=380).pack(side="left")

            badge_color = {"public": SUCCESS, "unlisted": ACCLT, "private": WARN}.get(
                v["privacy_status"], MUTED)
            badge_text = self._PRIVACY_LABELS.get(v["privacy_status"], v["privacy_status"])
            if v["privacy_status"] == "private" and v.get("publish_at"):
                badge_text = f"⏰ Programmée le {v['publish_at'][:10]}"
            ctk.CTkLabel(info, text=badge_text, text_color=badge_color, font=FONT_MU,
                         anchor="w").pack(anchor="w", pady=(2, 4))

            tags_preview = ", ".join(v.get("tags", []))[:90]
            ctk.CTkLabel(info, text=f"Tags : {tags_preview or '—'}", text_color=MUTED,
                         font=FONT_MU, anchor="w", wraplength=380).pack(anchor="w")

            _btn(inner, "✎ Modifier", lambda vid=v: self._youtube_lib_edit_video(vid),
                 small=True, width=110, height=30).pack(side="right", padx=(6, 0))

    def _youtube_lib_edit_video(self, video: dict):
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import BG, SURF3, BORDER, TEXT, MUTED, FONT_H2, FONT_SM, FONT_MU, _btn

        win = ctk.CTkToplevel(self)
        win.title("Modifier la vidéo")
        win.configure(fg_color=BG)
        win.geometry("560x640")
        win.grab_set()

        scroll = ctk.CTkScrollableFrame(win, fg_color=BG)
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(scroll, text="Titre", text_color=MUTED, font=FONT_MU, anchor="w").pack(
            anchor="w", pady=(0, 2))
        title_var = tk.StringVar(value=video["title"])
        ctk.CTkEntry(scroll, textvariable=title_var, fg_color=SURF3, border_color=BORDER,
                     text_color=TEXT, font=FONT_SM).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Tags (séparés par des virgules)", text_color=MUTED,
                     font=FONT_MU, anchor="w").pack(anchor="w")
        tags_var = tk.StringVar(value=", ".join(video.get("tags", [])))
        ctk.CTkEntry(scroll, textvariable=tags_var, fg_color=SURF3, border_color=BORDER,
                     text_color=TEXT, font=FONT_SM).pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(scroll, text="Description", text_color=MUTED, font=FONT_MU, anchor="w").pack(
            anchor="w")
        desc_box = ctk.CTkTextbox(scroll, fg_color=SURF3, border_color=BORDER, border_width=1,
                                  text_color=TEXT, font=FONT_SM, wrap="word", height=160)
        desc_box.pack(fill="x", pady=(2, 10))
        desc_box.insert("1.0", video.get("description", ""))

        ctk.CTkLabel(scroll, text="Visibilité", text_color=MUTED, font=FONT_MU, anchor="w").pack(
            anchor="w")
        privacy_values = list(self._PRIVACY_LABELS.values())
        privacy_var = tk.StringVar(value=self._PRIVACY_LABELS.get(
            video["privacy_status"], privacy_values[0]))
        privacy_combo = ctk.CTkComboBox(scroll, variable=privacy_var, values=privacy_values,
                        fg_color=SURF3, border_color=BORDER, button_color=SURF3,
                        button_hover_color=BORDER, dropdown_fg_color=SURF3,
                        text_color=TEXT, font=FONT_SM)
        privacy_combo.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(scroll, text="Date de programmation (si Privée, AAAA-MM-JJ, vide = immédiat)",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w")
        date_var = tk.StringVar(value=video.get("publish_at", "")[:10])
        ctk.CTkEntry(scroll, textvariable=date_var, placeholder_text="AAAA-MM-JJ",
                     fg_color=SURF3, border_color=BORDER, text_color=TEXT,
                     font=FONT_SM, width=140).pack(fill="x", pady=(2, 16))

        status_lbl = ctk.CTkLabel(scroll, text="", text_color=MUTED, font=FONT_MU)
        status_lbl.pack(pady=(0, 6))

        def _reverse_privacy(label: str) -> str:
            for k, v in self._PRIVACY_LABELS.items():
                if v == label:
                    return k
            return "private"

        def _save():
            privacy_status = _reverse_privacy(privacy_var.get())
            publish_at_iso = None
            date_str = date_var.get().strip()
            if privacy_status == "private" and date_str:
                try:
                    dt = datetime.strptime(date_str, DATE_FMT)
                    publish_at_iso = dt.strftime("%Y-%m-%dT09:00:00Z")
                except ValueError:
                    messagebox.showerror("Date invalide", "Format attendu : AAAA-MM-JJ")
                    return

            save_btn.configure(state="disabled")
            status_lbl.configure(text="Enregistrement...")

            def worker():
                from app import youtube_api
                from app.errors import YoutubeError
                token = self._youtube_lib_token()
                if not token:
                    self.after(0, lambda: status_lbl.configure(text="Token indisponible."))
                    self.after(0, lambda: save_btn.configure(state="normal"))
                    return
                try:
                    youtube_api.update_video(
                        token, video["id"],
                        title=title_var.get().strip(),
                        description=desc_box.get("1.0", "end-1c"),
                        tags=[t.strip() for t in tags_var.get().split(",") if t.strip()],
                        category_id=video.get("category_id", "22"),
                        privacy_status=privacy_status,
                        publish_at_iso=publish_at_iso,
                    )
                except YoutubeError as exc:
                    from app.logger import log_exception
                    log_exception(exc, context="youtube_edit_video")
                    self.after(0, lambda m=_format_youtube_error(exc): status_lbl.configure(text=f"Erreur : {m}"))
                    self.after(0, lambda: save_btn.configure(state="normal"))
                    return

                video.update({
                    "title": title_var.get().strip(),
                    "description": desc_box.get("1.0", "end-1c"),
                    "tags": [t.strip() for t in tags_var.get().split(",") if t.strip()],
                    "privacy_status": privacy_status,
                    "publish_at": publish_at_iso or "",
                })
                self.after(0, win.destroy)
                self.after(0, self._youtube_lib_render)

            threading.Thread(target=worker, daemon=True).start()

        save_btn = _btn(scroll, "💾 Enregistrer", _save, accent=True, height=40)
        save_btn.pack(fill="x")

    # ══════════════════════════════════════════════════════════════════════════
    # RÉORGANISATION — diversifier l'ordre des vidéos déjà programmées
    # ══════════════════════════════════════════════════════════════════════════

    def _youtube_reschedule_start(self):
        if not self._youtube_authorized():
            messagebox.showwarning("YouTube", "Autorisez d'abord votre compte YouTube.")
            self.show_youtube_auth()
            return

        wait = messagebox.askokcancel(
            "Réorganiser le planning",
            "Le logiciel va analyser toutes les vidéos privées avec une date de "
            "publication à venir, sur toutes vos playlists, puis proposer un "
            "nouvel ordre qui évite d'enchaîner plusieurs vidéos de la même "
            "playlist quand d'autres sont disponibles.\n\n"
            "Les dates utilisées restent les mêmes (aucune vidéo n'est avancée "
            "ou retardée dans le temps) — seul l'ordre change. Un aperçu vous "
            "sera montré avant tout envoi à YouTube.\n\n"
            "Continuer ?")
        if not wait:
            return

        self._set_status("🔀 Analyse du planning...")

        def worker():
            from app import youtube_api
            from app.errors import YoutubeAuthError, YoutubeError

            token = self._youtube_lib_token()
            if not token:
                self.after(0, self._youtube_lib_auth_expired)
                return

            try:
                playlists = youtube_api.list_playlists(token)
                membership: dict[str, str] = {}       # video_id -> group_key
                labels: dict[str, str] = {NO_PLAYLIST_KEY: NO_PLAYLIST_LABEL}
                for pl in playlists:
                    vids = youtube_api.list_playlist_video_ids(token, pl["id"])
                    labels[pl["id"]] = pl["title"]
                    for vid in vids:
                        membership.setdefault(vid, pl["id"])  # 1ère playlist trouvée

                uploads_id = youtube_api.get_uploads_playlist_id(token)
                all_ids = youtube_api.list_playlist_video_ids(token, uploads_id)
                all_videos = youtube_api.get_videos_details(token, all_ids) if all_ids else []
            except YoutubeAuthError:
                self.after(0, self._youtube_lib_auth_expired)
                return
            except YoutubeError as exc:
                self.after(0, lambda e=exc: self._youtube_lib_error(e))
                return

            now = datetime.now(timezone.utc)
            scheduled = []
            for v in all_videos:
                if v["privacy_status"] != "private" or not v.get("publish_at"):
                    continue
                try:
                    dt = _parse_publish_at(v["publish_at"])
                except ValueError:
                    continue
                if dt <= now:
                    continue
                v["_publish_dt"] = dt
                v["_group_key"] = membership.get(v["id"], NO_PLAYLIST_KEY)
                v["_group_label"] = labels.get(v["_group_key"], NO_PLAYLIST_LABEL)
                scheduled.append(v)

            self.after(0, lambda: self._set_status("📺 Mes vidéos YouTube"))

            if len(scheduled) < 2:
                self.after(0, lambda: messagebox.showinfo(
                    "Réorganiser", "Moins de 2 vidéos programmées à venir — rien à réorganiser."))
                return

            groups: dict[str, list] = {}
            for v in scheduled:
                groups.setdefault(v["_group_key"], []).append(v)
            for key in groups:
                groups[key].sort(key=lambda v: v["_publish_dt"])

            new_order = _diversify_order(groups)
            date_pool = sorted(v["_publish_dt"] for v in scheduled)

            plan = []
            for video, new_dt_slot in zip(new_order, date_pool):
                old_dt = video["_publish_dt"]
                new_dt = old_dt.astimezone(timezone.utc).replace(
                    year=new_dt_slot.year, month=new_dt_slot.month, day=new_dt_slot.day)
                plan.append({
                    "video": video,
                    "old_dt": old_dt,
                    "new_dt": new_dt,
                    "changed": new_dt.date() != old_dt.date(),
                })
            plan.sort(key=lambda p: p["new_dt"])

            self.after(0, lambda: self._youtube_reschedule_preview(plan))

        threading.Thread(target=worker, daemon=True).start()

    def _youtube_reschedule_preview(self, plan: list[dict]):
        import customtkinter as ctk
        from app.ui.app import (
            BG, SURF2, SURF3, BORDER, ACCENT, ACCLT, TEXT, MUTED, SUCCESS, WARN,
            FONT_H1, FONT_H2, FONT_SM, FONT_MU, _btn, _card,
        )

        changed = [p for p in plan if p["changed"]]

        win = ctk.CTkToplevel(self)
        win.title("Aperçu de la réorganisation")
        win.configure(fg_color=BG)
        win.geometry("720x600")
        win.grab_set()

        top = ctk.CTkFrame(win, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(top, text="Nouveau planning proposé", font=FONT_H1,
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(top, text=f"{len(changed)}/{len(plan)} vidéo(s) déplacée(s)",
                     text_color=MUTED, font=FONT_SM).pack(side="right")

        hdr = ctk.CTkFrame(win, fg_color=SURF3, corner_radius=6)
        hdr.pack(fill="x", padx=16)
        for txt, w in [("Nouvelle date", 100), ("Playlist", 160), ("Titre", 260), ("Ancienne date", 100)]:
            ctk.CTkLabel(hdr, text=txt, text_color=MUTED, font=FONT_MU, width=w, anchor="w").pack(
                side="left", padx=6, pady=5)

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent",
                                        scrollbar_button_color=SURF3,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        for p in plan:
            v = p["video"]
            row = ctk.CTkFrame(scroll, fg_color=SURF2 if p["changed"] else "transparent",
                               corner_radius=6)
            row.pack(fill="x", pady=1, padx=2)
            new_color = ACCLT if p["changed"] else MUTED
            ctk.CTkLabel(row, text=p["new_dt"].strftime(DATE_FMT), text_color=new_color,
                         font=FONT_SM, width=100, anchor="w").pack(side="left", padx=(6, 0))
            ctk.CTkLabel(row, text=v["_group_label"], text_color=TEXT, font=FONT_MU,
                         width=160, anchor="w").pack(side="left")
            title = v["title"] if len(v["title"]) <= 42 else v["title"][:40] + "…"
            ctk.CTkLabel(row, text=title, text_color=TEXT, font=FONT_MU,
                         width=260, anchor="w").pack(side="left")
            old_text = p["old_dt"].strftime(DATE_FMT) if p["changed"] else "—"
            ctk.CTkLabel(row, text=old_text, text_color=MUTED, font=FONT_MU,
                         width=100, anchor="w").pack(side="left")

        bottom = ctk.CTkFrame(win, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 16))
        status_lbl = ctk.CTkLabel(bottom, text="", text_color=MUTED, font=FONT_SM)
        status_lbl.pack(side="left")
        _btn(bottom, "Annuler", win.destroy, small=True, width=100).pack(side="right")
        apply_btn = _btn(bottom, f"✅ Appliquer ({len(changed)} vidéo(s))",
                         lambda: self._youtube_reschedule_apply(changed, win, status_lbl, apply_btn),
                         accent=True, width=220, height=36)
        apply_btn.pack(side="right", padx=(0, 8))
        if not changed:
            apply_btn.configure(state="disabled")

    def _youtube_reschedule_apply(self, changed: list[dict], win, status_lbl, apply_btn):
        apply_btn.configure(state="disabled")
        total = len(changed)

        def worker():
            from app import youtube_api
            from app.errors import YoutubeAuthError, YoutubeError
            from app.logger import log_exception

            token = self._youtube_lib_token()
            if not token:
                self.after(0, win.destroy)
                self.after(0, self._youtube_lib_auth_expired)
                return

            ok = 0
            for idx, p in enumerate(changed, start=1):
                v = p["video"]
                self.after(0, lambda i=idx: status_lbl.configure(
                    text=f"Mise à jour {i}/{total}..."))
                try:
                    youtube_api.update_video(
                        token, v["id"],
                        title=v["title"],
                        description=v.get("description", ""),
                        tags=v.get("tags", []),
                        category_id=v.get("category_id", "22"),
                        privacy_status="private",
                        publish_at_iso=_format_publish_at(p["new_dt"]),
                    )
                    v["_publish_dt"] = p["new_dt"]
                    v["publish_at"] = _format_publish_at(p["new_dt"])
                    ok += 1
                except YoutubeAuthError as exc:
                    log_exception(exc, context="youtube_reschedule")
                    self.after(0, win.destroy)
                    self.after(0, self._youtube_lib_auth_expired)
                    return
                except YoutubeError as exc:
                    log_exception(exc, context="youtube_reschedule")
                    self.after(0, lambda m=_format_youtube_error(exc): status_lbl.configure(
                        text=f"Erreur : {m}"))
                    self.after(0, lambda: apply_btn.configure(state="normal"))
                    return

            self.after(0, win.destroy)
            self.after(0, lambda: messagebox.showinfo(
                "Réorganisation terminée", f"{ok}/{total} vidéo(s) reprogrammée(s)."))
            self.after(0, lambda: self._youtube_lib_select_playlist(
                self._youtube_lib_playlist_id, self._youtube_lib_title_lbl.cget("text")))

        threading.Thread(target=worker, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # PROFILS
    # ══════════════════════════════════════════════════════════════════════════

    def show_youtube_profiles(self):
        import customtkinter as ctk
        from app.ui.app import BG, SURF2, SURF3, BORDER, ACCENT, TEXT, MUTED, FONT_H1, FONT_H2, FONT_SM, FONT_MU, _btn, _card

        self._clear_main()
        self._set_status("👤 Profils YouTube")

        outer = ctk.CTkFrame(self.main, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=32, pady=24)

        top = ctk.CTkFrame(outer, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(top, text="👤 Profils YouTube", font=FONT_H1, text_color=TEXT).pack(side="left")
        _btn(top, "← YouTube", self.show_youtube_choice, small=True, width=120).pack(side="right")
        _btn(top, "➕ Nouveau profil", lambda: self._youtube_edit_profile(None),
             small=True, width=150, accent=True).pack(side="right", padx=(0, 8))

        if not self.youtube_profiles:
            ctk.CTkLabel(outer, text="Aucun profil. Créez-en un pour pré-remplir "
                                      "description et tags par défaut.",
                         text_color=MUTED, font=FONT_SM).pack(pady=40)
            return

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent",
                                        scrollbar_button_color=SURF3,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.pack(fill="both", expand=True)

        for name, profile in self.youtube_profiles.items():
            card = _card(scroll)
            card.pack(fill="x", pady=5, padx=2)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=name, font=FONT_H2, text_color=TEXT, anchor="w").pack(anchor="w")
            tags_preview = ", ".join(profile.get("tags", []))[:80]
            ctk.CTkLabel(info, text=f"Tags : {tags_preview or '—'}",
                         text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", pady=(2, 0))
            desc_preview = (profile.get("description", "")[:80] or "—").replace("\n", " ")
            ctk.CTkLabel(info, text=f"Description : {desc_preview}",
                         text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w")

            btns = ctk.CTkFrame(inner, fg_color="transparent")
            btns.pack(side="right")
            _btn(btns, "✎ Modifier", lambda n=name: self._youtube_edit_profile(n),
                 small=True, width=100, height=28).pack(side="left", padx=(0, 6))
            _btn(btns, "✕ Supprimer", lambda n=name: self._youtube_delete_profile(n),
                 small=True, width=100, height=28, danger=True).pack(side="left")

    def _youtube_delete_profile(self, name: str):
        if messagebox.askyesno("Profil", f"Supprimer le profil « {name} » ?"):
            self.youtube_profiles.pop(name, None)
            if self._youtube_active_profile == name:
                self._youtube_active_profile = next(iter(self.youtube_profiles), "")
            self._persist_now()
            self.show_youtube_profiles()

    def _youtube_edit_profile(self, name: str | None):
        import customtkinter as ctk
        import tkinter as tk
        from app.ui.app import BG, SURF3, BORDER, TEXT, MUTED, FONT_H2, FONT_SM, FONT_MU, _btn

        existing = self.youtube_profiles.get(name, {}) if name else {}

        win = ctk.CTkToplevel(self)
        win.title("Profil YouTube" if name else "Nouveau profil")
        win.configure(fg_color=BG)
        win.geometry("480x480")
        win.grab_set()

        ctk.CTkLabel(win, text="Nom du profil", text_color=MUTED, font=FONT_MU, anchor="w").pack(
            anchor="w", padx=16, pady=(16, 2))
        name_var = tk.StringVar(value=name or "")
        name_entry = ctk.CTkEntry(win, textvariable=name_var, fg_color=SURF3,
                                   border_color=BORDER, text_color=TEXT, font=FONT_SM)
        name_entry.pack(fill="x", padx=16, pady=(0, 10))
        if name:
            name_entry.configure(state="disabled")

        ctk.CTkLabel(win, text="Tags par défaut (séparés par des virgules)",
                     text_color=MUTED, font=FONT_MU, anchor="w").pack(anchor="w", padx=16)
        tags_var = tk.StringVar(value=", ".join(existing.get("tags", [])))
        ctk.CTkEntry(win, textvariable=tags_var, fg_color=SURF3, border_color=BORDER,
                     text_color=TEXT, font=FONT_SM).pack(fill="x", padx=16, pady=(2, 10))

        ctk.CTkLabel(win, text="Description par défaut", text_color=MUTED,
                     font=FONT_MU, anchor="w").pack(anchor="w", padx=16)
        desc_box = ctk.CTkTextbox(win, fg_color=SURF3, border_color=BORDER, border_width=1,
                                  text_color=TEXT, font=FONT_SM, wrap="word")
        desc_box.pack(fill="both", expand=True, padx=16, pady=(2, 12))
        desc_box.insert("1.0", existing.get("description", ""))

        def _save():
            profile_name = name_var.get().strip()
            if not profile_name:
                messagebox.showerror("Profil", "Le nom du profil est obligatoire.")
                return
            self.youtube_profiles[profile_name] = {
                "tags": [t.strip() for t in tags_var.get().split(",") if t.strip()],
                "description": desc_box.get("1.0", "end-1c"),
            }
            if not self._youtube_active_profile:
                self._youtube_active_profile = profile_name
            self._persist_now()
            win.destroy()
            self.show_youtube_profiles()

        _btn(win, "Enregistrer", _save, accent=True, height=38).pack(
            fill="x", padx=16, pady=(0, 16))
