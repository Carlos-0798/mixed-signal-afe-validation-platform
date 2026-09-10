"""Small report action panel, kept separate from the workflow form renderer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..reporting import HumanReportPublication


class ReportActions:
    def __init__(
        self,
        parent: Any,
        tk: Any,
        ttk: Any,
        *,
        on_save: Callable[[], object],
        on_open: Callable[[], object],
    ) -> None:
        self.path = tk.StringVar(master=parent, value="")
        self._state: tuple[bool, str | None] | None = None
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.save_button = ttk.Button(
            frame,
            text="Save report package…",
            command=on_save,
            style="Primary.TButton",
            takefocus=True,
        )
        self.save_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.open_button = ttk.Button(
            frame,
            text="Open saved report",
            command=on_open,
            style="Secondary.TButton",
            takefocus=True,
        )
        self.open_button.grid(row=0, column=1, sticky="ew")
        ttk.Label(
            frame,
            textvariable=self.path,
            wraplength=880,
            justify="left",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def render(
        self, can_save: bool, publication: HumanReportPublication | None
    ) -> None:
        path = None if publication is None else str(publication.output_directory)
        state = (can_save, path)
        if state == self._state:
            return
        self._state = state
        self.save_button.configure(state="normal" if can_save else "disabled")
        self.open_button.configure(state="normal" if path is not None else "disabled")
        self.path.set(
            f"Saved report folder: {path}"
            if path is not None
            else "Save HTML, chart, Markdown, text and the complete result JSON together in a new folder."
            if can_save
            else "Report packages become available after a finalized analysis."
        )
