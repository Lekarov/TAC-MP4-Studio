"""Entités visuelles animées : particules, fumée, voiles, plasma, lueur ambiante."""
from __future__ import annotations

import math
import random

import cv2
import numpy as np

from app.presets import WIDTH, REGGAE_PALETTE, SMOKE_COLORS

# ── Cache lueur ambiante ──────────────────────────────────────────────────────
_ambient_mask_cache: dict[tuple[int, int], np.ndarray] = {}


# ── Particules flottantes ─────────────────────────────────────────────────────

class FloatingParticle:
    """Particule lumineuse réactive — cycle de vie, drift organique, fade in/out."""

    __slots__ = (
        "width", "height", "preset_name",
        "x", "y", "base_size", "speed", "angle", "alpha",
        "age", "max_age", "drift",
    )

    def __init__(self, width: int, height: int, preset_name: str) -> None:
        self.width = width
        self.height = height
        self.preset_name = preset_name
        self.reset()

    def reset(self) -> None:
        self.x = random.uniform(0, self.width)
        self.y = random.uniform(0, self.height)
        self.base_size = random.uniform(1.0, 3.8)
        self.speed = random.uniform(0.25, 1.35)
        if self.preset_name == "Pluie lumineuse":
            self.angle = random.uniform(math.pi * 0.42, math.pi * 0.58)
        else:
            self.angle = random.uniform(-math.pi * 0.92, -math.pi * 0.08)
        self.alpha = random.uniform(35, 145)
        self.age = 0.0
        self.max_age = random.uniform(70, 180)
        self.drift = random.uniform(-0.022, 0.022)

    def update(self, high: float, kick: float, preset: dict) -> None:
        boost = 1.0 + high * preset["speed"] * 7.5 + kick * 4.5
        self.x += math.cos(self.angle) * self.speed * boost
        self.y += math.sin(self.angle) * self.speed * boost
        self.angle += self.drift
        self.age += 1.0 + kick * 2.5
        out = (self.x < -40 or self.x > self.width + 40
               or self.y < -40 or self.y > self.height + 40)
        if out or self.age >= self.max_age:
            self.reset()
            self.y = -20 if self.preset_name == "Pluie lumineuse" else self.height + 20

    def draw(self, layer: np.ndarray, high: float, kick: float,
             preset: dict, scale: float) -> None:
        fade = (min(1.0, self.age / 15.0)
                * min(1.0, (self.max_age - self.age) / 20.0))
        fade = max(0.0, fade)
        energy = min(1.0, high * 0.8 + kick * 0.5)
        size = int(self.base_size * preset["size"] * scale * (1.0 + energy * 3.2))
        alpha = int(min(235, (self.alpha + energy * 125) * preset["alpha"] * fade))
        if alpha < 4 or size < 1:
            return
        cv2.circle(layer, (int(self.x), int(self.y)), max(1, size),
                   (alpha, alpha, alpha), -1, lineType=cv2.LINE_AA)


# ── Fumée classique ───────────────────────────────────────────────────────────

class SmokeBlob:
    """Blob de fumée avec forme elliptique, fade in progressif et mouvement organique."""

    __slots__ = (
        "width", "height",
        "x", "y", "radius", "rx", "ry",
        "speed", "drift", "phase", "alpha", "color_index",
        "travel", "fade_in_dist",
    )

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.reset(first=True)

    def reset(self, first: bool = False) -> None:
        self.x = random.uniform(-0.15 * self.width, 1.15 * self.width)
        self.y = (
            random.uniform(0.48 * self.height, 1.15 * self.height)
            if first
            else self.height + random.uniform(20, 180)
        )
        self.radius = random.uniform(90, 250) * (self.width / WIDTH)
        aspect = random.uniform(0.62, 1.42)
        self.rx = max(8, int(self.radius * aspect))
        self.ry = max(8, int(self.radius / max(0.3, aspect)))
        self.speed = random.uniform(0.15, 0.8)
        self.drift = random.uniform(-0.45, 0.45)
        self.phase = random.uniform(0, math.tau)
        self.alpha = random.uniform(28, 85)
        self.color_index = random.randint(0, 2)
        self.travel = 0.0
        self.fade_in_dist = random.uniform(50, 160)

    def update(self, bass: float, kick: float, preset: dict) -> None:
        dy = self.speed * (1.0 + bass * 3.5 + kick * 2.0) * preset["speed"]
        self.y -= dy
        self.travel += dy
        self.x += self.drift * (1.0 + bass * 1.6)
        self.phase += 0.025 + bass * 0.06
        if self.y < -max(self.rx, self.ry) * 2:
            self.reset()

    def draw(self, layer: np.ndarray, color_bgr: tuple[int, int, int],
             bass: float, kick: float, preset: dict) -> None:
        if preset["density"] <= 0:
            return
        fade_in = min(1.0, self.travel / max(1.0, self.fade_in_dist))
        wobble = 0.08 * math.sin(self.phase)
        rx = max(5, int(self.rx * (1.0 + bass * 0.45 + kick * 0.25 + wobble)))
        ry = max(5, int(self.ry * (1.0 + bass * 0.65 + kick * 0.35 + wobble)))
        alpha = int(min(155, self.alpha * preset["density"] * fade_in
                        * (1.0 + bass * 1.1 + kick * 0.5)))
        if alpha < 3:
            return
        color = tuple(int(v * alpha / 255) for v in color_bgr)
        cv2.ellipse(layer, (int(self.x), int(self.y)), (rx, ry),
                    0, 0, 360, color, -1, cv2.LINE_AA)


# ── Voiles ────────────────────────────────────────────────────────────────────

class VeilBlob:
    """Grande ellipse translucide et lente — effet de voile ou brume lumineuse."""

    __slots__ = ("width", "height", "x", "y", "rx", "ry",
                 "speed", "phase", "alpha", "color_index")

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.reset(first=True)

    def reset(self, first: bool = False) -> None:
        self.x = random.uniform(0.10 * self.width, 0.90 * self.width)
        self.rx = int(random.uniform(0.28, 0.58) * self.width)
        self.ry = int(random.uniform(0.10, 0.25) * self.height)
        self.y = (
            random.uniform(0.55 * self.height, 0.95 * self.height)
            if first
            else self.height + self.ry + random.uniform(0, 120)
        )
        self.speed = random.uniform(0.04, 0.16)
        self.phase = random.uniform(0, math.tau)
        self.alpha = random.uniform(14, 36)
        self.color_index = random.randint(0, 2)

    def update(self, bass: float, kick: float, preset: dict) -> None:
        self.y -= self.speed * (1.0 + bass * 1.8) * preset["speed"]
        self.phase += 0.007 + bass * 0.014
        if self.y < -self.ry * 3:
            self.reset()

    def draw(self, layer: np.ndarray, color_bgr: tuple[int, int, int],
             bass: float, kick: float, preset: dict) -> None:
        wobble = math.sin(self.phase)
        rx = max(20, int(self.rx * (1.0 + bass * 0.10 + wobble * 0.05)))
        ry = max(10, int(self.ry * (1.0 + bass * 0.18 + wobble * 0.04)))
        alpha = int(min(85, self.alpha * preset["density"] * (1.0 + bass * 0.65)))
        if alpha < 3:
            return
        color = tuple(int(v * alpha / 255) for v in color_bgr)
        cx = int(self.x + self.rx * 0.06 * wobble)
        cv2.ellipse(layer, (cx, int(self.y)), (rx, ry),
                    0, 0, 360, color, -1, cv2.LINE_AA)


# ── Traces plasma ─────────────────────────────────────────────────────────────

class PlasmaTrail:
    """Traînée lumineuse qui monte en ondulant — effet énergie / plasma."""

    __slots__ = ("width", "height", "x", "y", "speed", "phase", "phase_speed",
                 "amplitude", "alpha", "length", "color_index")

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.reset()

    def reset(self) -> None:
        self.x = random.uniform(0.05 * self.width, 0.95 * self.width)
        self.y = self.height + random.uniform(0, self.height * 0.6)
        self.speed = random.uniform(1.2, 3.8)
        self.phase = random.uniform(0, math.tau)
        self.phase_speed = random.uniform(0.05, 0.13)
        self.amplitude = random.uniform(8, 32) * (self.width / WIDTH)
        self.alpha = random.uniform(190, 255)
        self.length = int(random.uniform(0.10, 0.26) * self.height)
        self.color_index = random.randint(0, 2)

    def update(self, bass: float, kick: float, preset: dict) -> None:
        self.y -= self.speed * (1.0 + bass * 1.5 + kick * 3.5) * preset["speed"]
        self.phase += self.phase_speed + bass * 0.04
        if self.y < -self.length:
            self.reset()

    def draw(self, layer: np.ndarray, color_bgr: tuple[int, int, int],
             bass: float, kick: float, preset: dict) -> None:
        n_pts = 14
        pts = []
        for i in range(n_pts):
            t = i / max(1, n_pts - 1)
            y_pt = int(self.y + self.length * (1.0 - t))
            x_pt = int(self.x + self.amplitude * math.sin(self.phase + t * math.pi * 2.2))
            pts.append((x_pt, y_pt, t))

        for i in range(len(pts) - 1):
            x1, y1, t1 = pts[i]
            x2, y2, _ = pts[i + 1]
            a = int(self.alpha * t1 * preset["density"] * (1.0 + bass * 0.5 + kick * 0.8))
            if a < 8:
                continue
            a = min(255, a)
            c = tuple(int(v * a / 255) for v in color_bgr)
            # Ligne principale + halo plus épais
            lw_main = max(1, int((1.5 + (1.0 - t1) * 2.0) * self.width / WIDTH))
            lw_glow = lw_main + 4
            c_glow = tuple(min(255, int(v * 1.4)) for v in c)
            cv2.line(layer, (x1, y1), (x2, y2), c_glow, lw_glow, cv2.LINE_AA)
            cv2.line(layer, (x1, y1), (x2, y2), c,      lw_main, cv2.LINE_AA)


# ── Lueur ambiante (fonction standalone) ─────────────────────────────────────

def draw_ambient_glow(frame: np.ndarray, bass: float, kick: float,
                      preset: dict, color_bgr: tuple[int, int, int]) -> None:
    """Lueur colorée rayonnant depuis le bas et les bords — pur numpy, sans particules."""
    height, width = frame.shape[:2]
    key = (width, height)
    if key not in _ambient_mask_cache:
        y_lin = np.linspace(1.0, 0.0, height, dtype=np.float32)[:, np.newaxis]
        x_lin = np.linspace(0.0, 1.0, width,  dtype=np.float32)[np.newaxis, :]
        bottom = np.power(y_lin, 2.2)
        center = np.power(1.0 - np.abs(x_lin * 2.0 - 1.0), 1.5)
        _ambient_mask_cache[key] = (bottom * center).astype(np.float32)

    mask = _ambient_mask_cache[key]
    intensity = preset["density"] * (0.30 + bass * 0.50 + kick * 0.28)

    b, g, r = color_bgr
    glow = np.empty((height, width, 3), dtype=np.float32)
    glow[:, :, 0] = b * mask * intensity
    glow[:, :, 1] = g * mask * intensity
    glow[:, :, 2] = r * mask * intensity

    blur_k = min(91, max(41, int(height * 0.10))) | 1
    glow_u8 = np.clip(glow, 0, 255).astype(np.uint8)
    cv2.addWeighted(cv2.GaussianBlur(glow_u8, (blur_k, blur_k), 0),
                    0.95, frame, 1.0, 0, frame)
