"""Widgets Tkinter réutilisables."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollFrame(ttk.Frame):
    """Frame avec scrollbar verticale, compatible mousewheel."""

    def __init__(self, parent: tk.Widget, width: int = 340, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        self.canvas = tk.Canvas(self, bg="#111111", highlightthickness=0, width=width)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Panel.TFrame")

        self.inner.bind(
            "<Configure>",
            lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Mousewheel sur canvas et inner
        for widget in (self.canvas, self.inner):
            widget.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
