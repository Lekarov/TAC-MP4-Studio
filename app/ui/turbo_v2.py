"""TurboV2Mixin — mode Turbo V2 : import d'un dossier de paires musique/pochette.

Réutilise le moteur de rendu par lot de TurboMixin (app/ui/turbo.py) : les
items ajoutés à ``self._turbo_queue`` ont exactement la même forme, donc
``_turbo_start`` / ``_turbo_build_settings`` fonctionnent sans modification
(seul le mode "v2" y change le dossier/nom de sortie, voir turbo.py).

Sécurités spécifiques à Turbo V2 :
- Détection de doublons de nom (deux audios ou deux images de même nom à la
  casse près) → exclus de l'appariement plutôt que silencieusement écrasés.
- Vérification d'écriture dans le dossier choisi avant tout rendu.
- Historique persistant (``self.turbo_v2_history``, sauvegardé dans
  config.json) basé sur une empreinte (taille + date de modification) de
  l'audio et de l'image : une paire déjà rendue et inchangée est marquée
  "✅ Déjà fait" et n'est pas ré-exportée.
"""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


def _fingerprint(path: Path) -> int | None:
    """Empreinte légère (taille) pour détecter un fichier changé.

    Volontairement basée sur la seule taille, pas la date de modification :
    un déplacement, une copie ou une resynchro (NAS/cloud) changent souvent le
    mtime sans changer le contenu, ce qui faisait perdre le statut "déjà fait"
    à des paires pourtant inchangées."""
    try:
        return path.stat().st_size
    except OSError:
        return None


class TurboV2Mixin:

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO V2 — appariement audio / pochette par nom de fichier
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_v2_scan_folder(self, folder: str) -> dict:
        """Apparie chaque audio avec l'image de même nom dans `folder`.

        Retourne un dict :
          pairs        -> items prêts pour self._turbo_queue
          no_image     -> nb d'audios ignorés (pas de pochette correspondante)
          ambiguous    -> nb de fichiers ignorés (nom en double, ex. Song.mp3 + Song.wav)
          already_done -> nb de paires marquées comme déjà rendues (historique)
        """
        from app.ui.app import AUDIO_EXTS, IMAGE_EXTS

        folder_path = Path(folder)
        audio_files: dict[str, Path] = {}
        image_files: dict[str, Path] = {}
        audio_dupes: set[str] = set()
        image_dupes: set[str] = set()

        try:
            entries = list(folder_path.iterdir())
        except OSError as exc:
            messagebox.showerror("Turbo V2", f"Impossible de lire ce dossier :\n{exc}")
            return {"pairs": [], "no_image": 0, "ambiguous": 0, "already_done": 0}

        for p in entries:
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            stem_key = p.stem.casefold()
            if ext in AUDIO_EXTS:
                if stem_key in audio_files:
                    audio_dupes.add(stem_key)
                else:
                    audio_files[stem_key] = p
            elif ext in IMAGE_EXTS:
                if stem_key in image_files:
                    image_dupes.add(stem_key)
                else:
                    image_files[stem_key] = p

        pairs = []
        no_image = 0
        ambiguous = 0
        already_done = 0

        for stem_key, audio_path in sorted(audio_files.items(), key=lambda kv: kv[1].name.lower()):
            if stem_key in audio_dupes:
                ambiguous += 1
                continue
            image_path = image_files.get(stem_key)
            if image_path is None:
                no_image += 1
                continue
            if stem_key in image_dupes:
                ambiguous += 1
                continue

            stem = audio_path.stem
            if " - " in stem:
                left, right = stem.split(" - ", 1)
                artist_val, title_val = left.strip(), right.strip()
            else:
                artist_val, title_val = "", stem.strip()

            item = {
                "audio":      str(audio_path),
                "image":      str(image_path),
                "artist_var": tk.StringVar(value=artist_val),
                "title_var":  tk.StringVar(value=title_val),
                "status":     "⏳ En attente",
                "_status_lbl": None,
                "_img_btn":    None,
            }

            done_output = self._turbo_v2_already_done(audio_path, image_path)
            if done_output:
                item["status"] = "✅ Déjà fait"
                item["_v2_output"] = done_output
                already_done += 1

            pairs.append(item)

        return {
            "pairs": pairs,
            "no_image": no_image,
            "ambiguous": ambiguous,
            "already_done": already_done,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO V2 — historique persistant (déjà fait = pas refait)
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_v2_history_key(self, audio_path: Path) -> str:
        try:
            return str(audio_path.resolve()).casefold()
        except OSError:
            return str(audio_path).casefold()

    @staticmethod
    def _turbo_v2_normalize_fp(stored_fp) -> int | None:
        """Compatibilité avec les anciennes empreintes [taille, mtime] enregistrées
        avant l'abandon du mtime — n'en garde que la taille."""
        if isinstance(stored_fp, (list, tuple)):
            return stored_fp[0] if stored_fp else None
        return stored_fp

    def _turbo_v2_already_done(self, audio_path: Path, image_path: Path) -> str | None:
        """Retourne le chemin de sortie déjà rendu si la paire n'a pas changé, sinon None."""
        key = self._turbo_v2_history_key(audio_path)
        entry = self.turbo_v2_history.get(key)
        if not entry:
            return None

        output = entry.get("output", "")
        if not output or not Path(output).exists():
            return None

        audio_fp = _fingerprint(audio_path)
        image_fp = _fingerprint(image_path)
        if audio_fp is None or audio_fp != self._turbo_v2_normalize_fp(entry.get("audio_fp")):
            return None
        if image_fp is None or image_fp != self._turbo_v2_normalize_fp(entry.get("image_fp")):
            return None

        return output

    def _turbo_v2_mark_done(self, audio_path: str, image_path: str, output_path: str):
        import datetime
        key = self._turbo_v2_history_key(Path(audio_path))
        self.turbo_v2_history[key] = {
            "output":     output_path,
            "audio_fp":   _fingerprint(Path(audio_path)),
            "image_fp":   _fingerprint(Path(image_path)),
            "rendered_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        # Sauvegarde immédiate (pas de debounce) : si l'app crashe juste après,
        # on ne doit pas re-rendre un fichier déjà terminé au prochain lancement.
        try:
            self._persist_now()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO V2 — sélection du dossier
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_v2_check_folder_writable(self, folder: str) -> bool:
        probe = Path(folder) / ".tac_turbo_v2_write_test"
        try:
            probe.touch()
            probe.unlink()
            return True
        except OSError as exc:
            messagebox.showerror(
                "Turbo V2",
                f"Impossible d'écrire dans ce dossier (les vidéos y sont exportées) :\n{exc}")
            return False

    def _turbo_v2_pick_folder(self):
        if self._turbo_queue:
            if not messagebox.askyesno(
                "Turbo V2",
                "La file actuelle sera remplacée par le contenu du dossier choisi. Continuer ?"):
                return

        folder = filedialog.askdirectory(title="Dossier de musiques + pochettes (Turbo V2)")
        if not folder:
            return

        self._turbo_v2_load_folder(folder)

    def _turbo_v2_autoload_if_empty(self):
        """Recharge silencieusement le dernier dossier utilisé (persisté) si la
        file est vide — permet de retrouver l'état après un redémarrage de
        l'appli sans revalider de dialogue."""
        if self._turbo_queue:
            return
        folder = getattr(self, "_turbo_v2_last_folder", "")
        if not folder or not Path(folder).is_dir():
            return
        try:
            result = self._turbo_v2_scan_folder(folder)
        except Exception:
            return
        if result["pairs"]:
            self._turbo_queue = result["pairs"]

    def _turbo_v2_rescan_folder(self):
        """Ré-analyse le dernier dossier choisi (nouveaux fichiers, suppressions…)."""
        folder = getattr(self, "_turbo_v2_last_folder", "")
        if not folder:
            messagebox.showwarning("Turbo V2", "Aucun dossier sélectionné.")
            return
        if not Path(folder).is_dir():
            messagebox.showerror("Turbo V2", "Ce dossier n'existe plus ou n'est plus accessible.")
            return
        self._turbo_v2_load_folder(folder)

    def _turbo_v2_load_folder(self, folder: str):
        if not self._turbo_v2_check_folder_writable(folder):
            return

        result = self._turbo_v2_scan_folder(folder)
        pairs = result["pairs"]
        if not pairs:
            messagebox.showwarning(
                "Turbo V2",
                "Aucune paire musique + pochette (même nom de fichier) trouvée dans ce dossier.")
            return

        self._turbo_queue = pairs
        self._turbo_v2_last_folder = folder
        try:
            self._persist_now()
        except Exception:
            pass

        if getattr(self, "_turbo_v2_view_active", False):
            self.show_turbo_v2()

        todo = len(pairs) - result["already_done"]
        msg = f"⚡ Turbo V2 — {len(pairs)} paire(s), {todo} à faire"
        if result["already_done"]:
            msg += f", {result['already_done']} déjà faite(s)"
        self._set_status(msg)

        details = []
        if result["already_done"]:
            details.append(f"{result['already_done']} déjà rendue(s) précédemment (ignorée(s)).")
        if result["no_image"]:
            details.append(f"{result['no_image']} fichier(s) audio ignoré(s) (aucune pochette de même nom).")
        if result["ambiguous"]:
            details.append(
                f"{result['ambiguous']} fichier(s) ignoré(s) : nom en double "
                f"(ex. Titre.mp3 ET Titre.wav, ou deux pochettes Titre.*).")
        if details:
            messagebox.showinfo(
                "Turbo V2",
                f"{len(pairs)} paire(s) importée(s), {todo} à produire.\n\n" + "\n".join(details))

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO V2 — sécurités de rendu (chemin, collisions, espace disque)
    # ══════════════════════════════════════════════════════════════════════════

    # Marge de sécurité Windows (MAX_PATH ≈ 260) pour le chemin de sortie complet.
    WINDOWS_MAX_PATH = 259
    # Estimation prudente de l'espace nécessaire par vidéo (1080p, quelques minutes).
    EST_BYTES_PER_VIDEO = 150 * 1024 * 1024

    def _turbo_v2_unique_output_path(self, target_dir: Path, stem: str) -> Path:
        """Renvoie un chemin `<stem>.mp4` libre, en suffixant (1), (2)… si occupé
        par un fichier qui n'est pas un rendu Turbo V2 déjà connu."""
        candidate = target_dir / f"{stem}.mp4"
        if not candidate.exists():
            return candidate
        n = 1
        while True:
            candidate = target_dir / f"{stem} ({n}).mp4"
            if not candidate.exists():
                return candidate
            n += 1

    def _turbo_v2_check_disk_space(self, folder: str, pending_count: int) -> bool:
        import shutil as _shutil
        try:
            free = _shutil.disk_usage(folder).free
        except OSError:
            return True  # impossible à vérifier, on ne bloque pas pour autant

        needed = self.EST_BYTES_PER_VIDEO * max(1, pending_count)
        if free >= needed:
            return True

        free_mb = free // (1024 * 1024)
        needed_mb = needed // (1024 * 1024)
        return messagebox.askyesno(
            "Turbo V2 — espace disque",
            f"Espace disque libre estimé insuffisant sur ce disque "
            f"({free_mb} Mo libres, ~{needed_mb} Mo estimés nécessaires pour "
            f"{pending_count} vidéo(s)).\n\nContinuer quand même ?")

    # ══════════════════════════════════════════════════════════════════════════
    # TURBO V2 — aperçu aléatoire
    # ══════════════════════════════════════════════════════════════════════════

    def _turbo_preview_random(self):
        candidates = [it for it in self._turbo_queue if not it["status"].startswith("✅")]
        if not candidates:
            candidates = list(self._turbo_queue)
        if not candidates:
            messagebox.showwarning("Aperçu", "Importez d'abord un dossier de musiques.")
            return

        # Évite de retomber sur le même fichier que le tirage précédent tant
        # qu'il reste d'autres candidats (sinon un tirage uniforme peut, par
        # pur hasard, redonner le même choix plusieurs fois de suite).
        last_audio = getattr(self, "_turbo_preview_last_audio", None)
        pool = [it for it in candidates if it["audio"] != last_audio]
        if not pool:
            pool = candidates

        pick = random.choice(pool)
        self._turbo_preview_last_audio = pick["audio"]
        self._turbo_preview(pick)
