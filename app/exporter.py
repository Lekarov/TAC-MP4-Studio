"""Export vidéo — rendu frame par frame + encodage FFmpeg.

Correction critique vs version originale :
- start_offset était systématiquement passé à 0.0 pour les exports non-preview
  même quand calculé correctement pour SHORT → BUG CORRIGÉ.

Encodage en une seule passe :
- Les frames sont pipées directement vers FFmpeg (rawvideo sur stdin), qui les
  encode et les mixe avec l'audio en un seul appel. Auparavant, les frames étaient
  écrites via cv2.VideoWriter (codec mp4v, avec pertes) dans un fichier temporaire,
  puis ce fichier était intégralement ré-encodé par FFmpeg pour ajouter l'audio :
  deux passes d'encodage, donc une perte de qualité superflue et un export plus long.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import numpy as np

from app.audio import compute_audio_features
from app.errors import ExportError, FFmpegError
from app.logger import get_logger
from app.models import RenderSettings
from app.presets import FPS, WIDTH, HEIGHT
from app.renderer import load_cover_image, render_frame

_log = get_logger("exporter")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegError(
            "FFmpeg est introuvable. Installez-le et ajoutez-le au PATH.",
            detail="shutil.which('ffmpeg') returned None",
        )


def ffmpeg_has_nvenc() -> bool:
    """Détecte si FFmpeg supporte l'encodage GPU NVIDIA."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return "h264_nvenc" in (result.stdout + result.stderr)
    except Exception as exc:
        _log.debug("Détection NVENC échouée, bascule sur CPU: %s", exc)
        return False


def _read_ffmpeg_log(path: Path) -> str:
    """Lit la fin du log stderr de FFmpeg pour le détail d'une erreur."""
    try:
        return "Erreur FFmpeg :\n" + path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        return "Erreur FFmpeg (log indisponible)."


def open_file(path: str) -> None:
    """Ouvre un fichier ou dossier dans l'explorateur Windows (no-op sur les autres OS)."""
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError:
        # Linux/macOS — ouvrir avec xdg-open si disponible
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            _log.debug("xdg-open a échoué pour %r: %s", path, exc)
    except Exception as exc:
        _log.debug("Impossible d'ouvrir %r: %s", path, exc)


def _start_ffmpeg_pipe(
    audio_path: str,
    output_path: str,
    width: int,
    height: int,
    fps: int,
    start_offset: float,
    video_duration: float,
    stderr_log_path: Path,
) -> tuple[subprocess.Popen, Any]:
    """Démarre FFmpeg en attente de frames brutes (BGR) sur stdin.

    FFmpeg encode et mixe avec l'audio au fil de l'eau, en une seule passe.
    Le codec (NVENC ou CPU) est choisi une fois avant de commencer à envoyer des
    frames : un éventuel fallback en cours de flux impliquerait de relancer tout
    le rendu, ce qui coûterait plus cher que le bénéfice du GPU.

    Le -ss est placé AVANT l'input audio pour un seek précis (fast seek).
    """
    seek = max(0.0, float(start_offset or 0.0))

    base_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-ss", f"{seek:.3f}",
        "-i", audio_path,
        "-t", f"{video_duration:.3f}",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-shortest",
    ]

    if ffmpeg_has_nvenc():
        cmd = base_cmd + [
            "-c:v", "h264_nvenc",
            "-preset", "p6",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "16",
            "-b:v", "0",
            output_path,
        ]
    else:
        cmd = base_cmd + [
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "16",
            output_path,
        ]

    stderr_log = open(stderr_log_path, "w+b")
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr_log,
        )
    except FileNotFoundError as exc:
        stderr_log.close()
        raise FFmpegError(
            "FFmpeg est introuvable. Installez-le et ajoutez-le au PATH.",
            detail=str(exc),
        ) from exc
    return proc, stderr_log


def render_video(
    settings: RenderSettings,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Rendu complet : analyse audio → frames → encodage FFmpeg.

    progress_callback reçoit des chaînes de progression type "Rendu : 42.3%".
    """
    require_ffmpeg()

    out_dir = Path(settings.output_path).parent
    if not out_dir.exists():
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise ExportError(
                "Permission refusée : impossible d'écrire dans ce dossier.",
                detail=str(exc),
            ) from exc
        except OSError as exc:
            raise ExportError(
                "Le dossier de destination n'existe pas.",
                detail=str(exc),
            ) from exc

    try:
        _test = out_dir / ".tac_write_test"
        _test.touch()
        _test.unlink()
    except PermissionError as exc:
        raise ExportError(
            "Permission refusée : impossible d'écrire dans ce dossier.",
            detail=str(exc),
        ) from exc
    except OSError:
        pass

    out_name = Path(settings.output_path).name
    _INVALID_CHARS = set('<>:"/\\|?*')
    if any(c in _INVALID_CHARS for c in out_name):
        raise ExportError(
            "Nom de fichier invalide.",
            detail=f"Nom: {out_name!r}",
        )

    stderr_log_path = out_dir / "_tac_ffmpeg_export.log"

    if progress_callback:
        progress_callback("Analyse audio bass/kick/aigus...")

    features = compute_audio_features(
        settings.audio_path,
        FPS,
        settings.duration_limit,
        settings.start_offset,
    )

    out_w = settings.output_width
    out_h = settings.output_height

    bg, cover = load_cover_image(
        settings.image_path,
        settings.background_blur,
        settings.image_zoom,
        out_w,
        out_h,
        bg_mode=settings.bg_mode,
        gradient_top=settings.gradient_top,
        gradient_bottom=settings.gradient_bottom,
        background_brightness=settings.background_brightness,
        bg_image_path=settings.bg_image_path,
    )

    particles: list = []
    smoke_blobs: list = []
    smoothed = np.zeros(84, dtype=np.float32)
    smooth_kick = 0.0
    vinyl_angle = 0.0

    total = len(features["rms"])
    video_duration = total / FPS

    # BUG FIX (conservé) : start_offset correctement transmis à l'audio
    # (était 0.0 en dur dans l'original).
    proc, stderr_log = _start_ffmpeg_pipe(
        settings.audio_path,
        settings.output_path,
        out_w, out_h, FPS,
        settings.start_offset,
        video_duration,
        stderr_log_path,
    )

    try:
        for i in range(total):
            smooth_kick = smooth_kick * 0.68 + float(features["kick"][i]) * 0.32

            metrics = {
                "rms":  float(features["rms"][i]),
                "kick": smooth_kick,
                "bass": float(features["bass"][i]),
                "mid":  float(features["mid"][i]),
                "high": float(features["high"][i]),
            }

            raw_f = features["raw"][i] if "raw" in features else None
            try:
                frame, particles, smoke_blobs, smoothed, vinyl_angle = render_frame(
                    bg,
                    cover,
                    particles,
                    smoke_blobs,
                    features["spec"][:, i],
                    metrics,
                    smoothed,
                    settings,
                    vinyl_angle,
                    frame_idx=i,
                    raw_frame=raw_f,
                )
            except Exception as exc:
                raise ExportError(
                    "Export interrompu.",
                    detail=f"Erreur au rendu de la frame {i}: {exc}",
                ) from exc

            try:
                proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError) as exc:
                raise FFmpegError(
                    "FFmpeg s'est arrêté prématurément pendant le rendu.",
                    detail=_read_ffmpeg_log(stderr_log_path),
                ) from exc

            if progress_callback and i % FPS == 0:
                pct = i / max(1, total - 1) * 100
                progress_callback(f"Rendu : {pct:.1f}%")

        proc.stdin.close()
    except BaseException:
        # Erreur pendant le rendu ou l'écriture : on arrête FFmpeg proprement plutôt
        # que de le laisser attendre indéfiniment plus de frames sur stdin.
        proc.kill()
        proc.wait()
        stderr_log.close()
        raise

    if progress_callback:
        progress_callback("Finalisation de l'encodage...")

    returncode = proc.wait()
    stderr_log.close()
    if returncode != 0:
        raise FFmpegError(
            "FFmpeg a rencontré une erreur lors de l'encodage.",
            detail=_read_ffmpeg_log(stderr_log_path),
        )

    try:
        stderr_log_path.unlink()
    except OSError:
        pass

    # Miniature pour l'historique (Update 3)
    _extract_thumbnail(settings.output_path)

    if progress_callback:
        progress_callback(f"Terminé : {settings.output_path}")


def _extract_thumbnail(video_path: str) -> None:
    """Extrait une frame à t=1s comme miniature JPG à côté de la vidéo."""
    try:
        thumb = str(video_path).replace(".mp4", "_thumb.jpg")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "quiet",
            "-ss", "00:00:01", "-i", video_path,
            "-vframes", "1", "-vf", "scale=320:-2",
            thumb,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        _log.debug("Extraction de la miniature échouée pour %r: %s", video_path, exc)
