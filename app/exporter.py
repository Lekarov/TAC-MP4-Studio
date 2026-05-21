"""Export vidéo — rendu frame par frame + encodage FFmpeg.

Correction critique vs version originale :
- start_offset était systématiquement passé à 0.0 pour les exports non-preview
  même quand calculé correctement pour SHORT → BUG CORRIGÉ.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from app.audio import compute_audio_features
from app.errors import ExportError, FFmpegError
from app.models import RenderSettings
from app.presets import FPS, WIDTH, HEIGHT
from app.renderer import load_cover_image, render_frame


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
    except Exception:
        return False


def run_ffmpeg(cmd: list[str]) -> None:
    """Lance une commande FFmpeg et lève une exception en cas d'erreur."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise FFmpegError(
            "FFmpeg est introuvable. Installez-le et ajoutez-le au PATH.",
            detail=str(exc),
        ) from exc
    if result.returncode != 0:
        raise FFmpegError(
            "FFmpeg a rencontré une erreur lors de l'encodage.",
            detail="Erreur FFmpeg :\n" + result.stderr[-3000:],
        )


def open_file(path: str) -> None:
    """Ouvre un fichier ou dossier dans l'explorateur Windows (no-op sur les autres OS)."""
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError:
        # Linux/macOS — ouvrir avec xdg-open si disponible
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
    except Exception:
        pass


def _add_audio_to_video(
    temp_video: str,
    audio_path: str,
    output_path: str,
    duration: float,
    start_offset: float,
) -> None:
    """Combine la vidéo muette avec l'audio en découpant depuis start_offset.

    Le -ss est placé AVANT l'input audio pour un seek précis (fast seek).
    """
    seek = max(0.0, float(start_offset or 0.0))

    base_cmd = [
        "ffmpeg", "-y",
        "-ss", f"{seek:.3f}",
        "-i", audio_path,
        "-i", temp_video,
        "-t", f"{duration:.3f}",
        "-map", "1:v:0",
        "-map", "0:a:0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-shortest",
    ]

    if ffmpeg_has_nvenc():
        nvenc_cmd = base_cmd + [
            "-c:v", "h264_nvenc",
            "-preset", "p6",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "16",
            "-b:v", "0",
            output_path,
        ]
        try:
            run_ffmpeg(nvenc_cmd)
            return
        except (FFmpegError, RuntimeError):
            pass  # Fallback sur libx264

    cpu_cmd = base_cmd + [
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "16",
        output_path,
    ]
    run_ffmpeg(cpu_cmd)


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

    temp_video = str(out_dir / "_temp_tac_no_audio.mp4")

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

    writer = cv2.VideoWriter(
        temp_video,
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (out_w, out_h),
    )
    if not writer.isOpened():
        raise ExportError(
            "Export interrompu.",
            detail="Impossible d'ouvrir le moteur vidéo OpenCV (cv2.VideoWriter).",
        )

    try:
        total = len(features["rms"])

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

            writer.write(frame)

            if progress_callback and i % FPS == 0:
                pct = i / max(1, total - 1) * 100
                progress_callback(f"Rendu : {pct:.1f}%")

    finally:
        writer.release()

    if progress_callback:
        progress_callback("Encodage MP4 qualité max avec musique...")

    # BUG FIX : start_offset correctement transmis (était 0.0 en dur dans l'original)
    _add_audio_to_video(
        temp_video,
        settings.audio_path,
        settings.output_path,
        features["duration"],
        settings.start_offset,  # ← CORRIGÉ : était 0.0 systématiquement
    )

    try:
        os.remove(temp_video)
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
    except Exception:
        pass
