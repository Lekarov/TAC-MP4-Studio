"""Analyse audio — extraction des features réactives.

Update 8 (patch) :
- raw_frames vectorisé numpy (suppression boucle Python ~5400 iter)
- imports déplacés en tête de fichier

Optimisation perf :
- compute_audio_features mis en cache LRU sur (audio_path, fps, duration_limit, start_offset)
  pour éviter les re-analyses coûteuses lors des refreshs de preview.
"""
from __future__ import annotations

import functools
import warnings
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf

from app.errors import AudioImportError


# ── Cache LRU pour compute_audio_features ─────────────────────────────────────
# Clé : (audio_path, fps, duration_limit, start_offset)
# Taille max = 4 entrées (couvre preview + export sans accumuler indéfiniment)
@functools.lru_cache(maxsize=4)
def _cached_compute_audio_features(
    audio_path: str,
    fps: int,
    duration_limit: float | None,
    start_offset: float,
) -> dict:
    """Version cachée de compute_audio_features — ne pas appeler directement."""
    return _compute_audio_features_impl(audio_path, fps, duration_limit, start_offset)


def _load_audio(
    audio_path: str,
    sr: int = 44100,
    offset: float = 0.0,
    duration: float | None = None,
) -> tuple[np.ndarray, int]:
    """Load audio using soundfile (fast, WAV/FLAC/OGG); fall back to librosa for other formats."""
    import scipy.signal

    if not Path(audio_path).exists():
        raise AudioImportError(
            "Fichier audio introuvable.",
            detail=f"Path: {audio_path!r}",
        )

    ext = Path(audio_path).suffix.lower()
    _SUPPORTED = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".aiff"}
    if ext and ext not in _SUPPORTED:
        raise AudioImportError(
            "Format audio non supporté.",
            detail=f"Extension: {ext!r}, path: {audio_path!r}",
        )

    # Clamp offset so it never starts past the end of the file.
    # If offset > file duration, fall back to the last `duration` seconds.
    clamped_offset = offset
    try:
        info = sf.info(audio_path)
        file_dur = info.frames / info.samplerate
        if clamped_offset >= file_dur:
            clamped_offset = max(0.0, file_dur - (duration if duration is not None else file_dur))
    except Exception:
        pass

    # Fast path — soundfile handles WAV/FLAC/OGG natively without deprecated audioread
    try:
        info = sf.info(audio_path)
        sr_native = info.samplerate
        start_frame = int(clamped_offset * sr_native)
        stop_frame = (min(int((clamped_offset + duration) * sr_native), info.frames)
                      if duration is not None else None)
        data, _ = sf.read(audio_path, start=start_frame, stop=stop_frame,
                          dtype="float32", always_2d=True)
        if len(data) > 0:
            y = data.mean(axis=1) if data.shape[1] > 1 else data[:, 0]
            if sr_native != sr:
                n = int(round(len(y) * sr / sr_native))
                y = scipy.signal.resample(y, n).astype(np.float32)
            return y, sr
    except AudioImportError:
        raise
    except Exception:
        pass

    # Fallback — handles MP3, M4A, ADPCM WAV, and anything soundfile can't read
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="PySoundFile failed")
            warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")
            return librosa.load(audio_path, sr=sr, mono=True,
                                offset=clamped_offset, duration=duration)
    except AudioImportError:
        raise
    except Exception as exc:
        raise AudioImportError(
            "Impossible de lire le fichier audio.",
            detail=str(exc),
        ) from exc


def _resize_1d(arr: np.ndarray, target_len: int) -> np.ndarray:
    if len(arr) == target_len:
        return arr
    x_old = np.linspace(0.0, 1.0, len(arr))
    x_new = np.linspace(0.0, 1.0, target_len)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def _resize_2d_time(spec: np.ndarray, target_frames: int) -> np.ndarray:
    if spec.shape[1] == target_frames:
        return spec
    old_frames = spec.shape[1]
    indices = np.linspace(0.0, old_frames - 1, target_frames)
    left  = np.floor(indices).astype(np.int32)
    right = np.minimum(left + 1, old_frames - 1)
    frac  = (indices - left).astype(np.float32)
    return (spec[:, left] * (1.0 - frac) + spec[:, right] * frac).astype(np.float32)


def _band_energy(spec: np.ndarray, freqs: np.ndarray,
                 low: float, high: float) -> np.ndarray:
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return np.zeros(spec.shape[1], dtype=np.float32)
    vals = np.mean(spec[mask, :], axis=0)
    return (vals / (np.max(vals) + 1e-9)).astype(np.float32)


def compute_audio_features(
    audio_path: str,
    fps: int,
    duration_limit: float | None = None,
    start_offset: float = 0.0,
) -> dict:
    """Extrait toutes les features audio nécessaires au rendu frame par frame.

    Les résultats sont mis en cache par (audio_path, fps, duration_limit, start_offset).
    Le cache LRU (maxsize=4) évite les re-analyses lors des rafraîchissements de preview.
    """
    return _cached_compute_audio_features(audio_path, fps, duration_limit, start_offset)


def _compute_audio_features_impl(
    audio_path: str,
    fps: int,
    duration_limit: float | None,
    start_offset: float,
) -> dict:
    """Implémentation réelle — appelée via le cache LRU."""
    try:
        y, sr = _load_audio(audio_path, sr=44100, offset=start_offset, duration=duration_limit)
    except AudioImportError:
        raise
    except Exception as exc:
        raise AudioImportError(
            "Impossible de lire le fichier audio.",
            detail=str(exc),
        ) from exc
    duration = len(y) / sr
    if duration <= 0:
        raise AudioImportError(
            "Impossible de lire le fichier audio.",
            detail=(
                f"Audio vide ou illisible (0 s chargées). "
                f"Fichier : {audio_path!r}, offset={start_offset}, durée limite={duration_limit}"
            ),
        )

    hop    = max(1, int(sr / fps))
    frames = max(1, int(duration * fps))

    rms   = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    rms   = (rms / (np.max(rms) + 1e-9)).astype(np.float32)

    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onset = (onset / (np.max(onset) + 1e-9)).astype(np.float32)

    stft_amp = np.abs(librosa.stft(y, n_fft=4096, hop_length=hop))
    freqs    = librosa.fft_frequencies(sr=sr, n_fft=4096)
    bass     = _band_energy(stft_amp, freqs, 20,   180)
    mid      = _band_energy(stft_amp, freqs, 180,  2500)
    high     = _band_energy(stft_amp, freqs, 2500, 12000)

    spec_db = librosa.amplitude_to_db(stft_amp, ref=np.max)
    spec    = np.clip((spec_db + 80.0) / 80.0, 0.0, 1.0).astype(np.float32)

    # ── Oscilloscope : raw_frames vectorisé (Update 8 — fix PERF 1) ──────────
    # Construit la matrice (frames × osc_len) sans boucle Python
    osc_len    = 512
    half       = osc_len // 2
    frame_idxs = np.arange(frames, dtype=np.int32) * hop        # centre de chaque frame
    starts     = np.clip(frame_idxs - half, 0, max(0, len(y) - osc_len))
    # Vectorisé : index matrix shape (frames, osc_len)
    col_idxs   = starts[:, np.newaxis] + np.arange(osc_len, dtype=np.int32)
    col_idxs   = np.clip(col_idxs, 0, len(y) - 1)
    raw_frames  = y[col_idxs].astype(np.float32)                # (frames, osc_len)

    return {
        "rms":      _resize_1d(rms,    frames),
        "kick":     _resize_1d(onset,  frames),
        "bass":     _resize_1d(bass,   frames),
        "mid":      _resize_1d(mid,    frames),
        "high":     _resize_1d(high,   frames),
        "spec":     _resize_2d_time(spec, frames),
        "raw":      raw_frames,
        "duration": duration,
    }
