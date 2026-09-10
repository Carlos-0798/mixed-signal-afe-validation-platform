"""Guided local voltage imports using immutable, explicitly mapped snapshots."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from analog_validation import MeasurementUnit

from ..errors import ProductRequestError
from ..import_packages import (
    VoltageImportPublication,
    load_voltage_mapping,
    load_voltage_table,
    publish_voltage_import,
    write_voltage_mapping,
)
from ..product_workflows import ProductWorkflowConfiguration
from ..tabular_import import (
    TabularImportSource,
    VoltageImportMapping,
    VoltageImportPreview,
    parse_voltage_table,
    preview_voltage_import,
)
from .widgets import _bind_mouse_wheel, _create_scrollable_page

_DELIMITERS = {"Comma (,)": ",", "Semicolon (;)": ";", "Tab": "\t"}
_RESELECT_GUIDANCE = "Select the correct separator, then choose the file again."
_DEFAULTS = {
    "name": "Imported voltage",
    "delimiter": "Comma (,)",
    "time_mode": "timestamp",
    "time_column": "",
    "input_column": "",
    "input_unit": "V",
    "output_column": "",
    "output_unit": "V",
    "start_time_utc": "",
    "minimum_mv": "0",
    "maximum_mv": "3300",
}


class ImportPage:
    """One UI-thread page; importing, publishing, and loading never run a test."""

    def __init__(
        self,
        root: Any,
        tk: Any,
        ttk: Any,
        notebook: Any,
        *,
        on_load_setup: Callable[[ProductWorkflowConfiguration], bool],
        is_busy: Callable[[], bool],
        choose_path: Callable[[str], str],
    ) -> None:
        self.on_load_setup = on_load_setup
        self.is_busy = is_busy
        self.choose_path = choose_path
        self.source: TabularImportSource | None = None
        self.preview: VoltageImportPreview | None = None
        self.publication: VoltageImportPublication | None = None
        self.source_path = ""
        self._raw_bytes: bytes | None = None
        self._source_delimiter = ","
        self._suspend_changes = False
        self._message = "Choose a CSV file, then assign its time and voltage columns."
        self._render_state: object = None
        self._unpublished_work = False
        self.variables = {
            key: tk.StringVar(master=root, value=value)
            for key, value in _DEFAULTS.items()
        }
        self.status = tk.StringVar(master=root, value="")
        self.snapshot = tk.StringVar(master=root, value="No source snapshot selected.")
        self.review = tk.StringVar(master=root, value="Mapping has not been checked.")
        self._last_values = self._values()
        self.controls: dict[str, Any] = {}
        self._comboboxes: set[str] = set()
        self.tab = ttk.Frame(notebook, style="App.TFrame")
        notebook.add(self.tab, text="Import data")
        page, canvas = _create_scrollable_page(
            self.tab,
            tk,
            ttk,
            high_contrast=bool(getattr(root, "_avs_high_contrast", False)),
        )
        self.page = page
        self.canvas = canvas
        _bind_mouse_wheel(root, (canvas,))
        page.columnconfigure(0, weight=1)

        def card(title: str, row: int) -> Any:
            frame = ttk.LabelFrame(
                page, text=title, padding=12, style="Card.TLabelframe"
            )
            frame.grid(row=row, column=0, sticky="ew", padx=18, pady=8)
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(3, weight=1)
            return frame

        def label(frame: Any, text: str, row: int) -> None:
            ttk.Label(
                frame, text=text, wraplength=870, justify="left", style="Muted.TLabel"
            ).grid(row=row, column=0, columnspan=4, sticky="w", pady=4)

        def field(
            frame: Any,
            key: str,
            text: str,
            row: int,
            column: int = 0,
            choices: tuple[str, ...] | None = None,
        ) -> Any:
            ttk.Label(frame, text=text, style="Body.TLabel").grid(
                row=row, column=column, sticky="w", padx=4, pady=3
            )
            options = {"textvariable": self.variables[key], "takefocus": True}
            if choices is None:
                widget = ttk.Entry(frame, **options)
            else:
                widget = ttk.Combobox(frame, values=choices, width=19, **options)
                self._comboboxes.add(key)
            widget.grid(row=row, column=column + 1, sticky="ew", padx=4, pady=3)
            self.controls[key] = widget
            widget.bind("<KeyRelease>", self._changed)
            widget.bind("<<ComboboxSelected>>", self._changed)
            return widget

        def button(
            frame: Any, key: str, text: str, action: Callable[[], None], column: int
        ) -> Any:
            widget = ttk.Button(
                frame,
                text=text,
                command=action,
                takefocus=True,
                style="Secondary.TButton",
            )
            widget.grid(row=0, column=column, sticky="w", padx=4, pady=5)
            self.controls[key] = widget
            return widget

        intro = card("Import external voltage data", 0)
        label(
            intro,
            "Map an existing CSV into replay data. Start with V or mV readings; "
            "time must include a timezone, or use elapsed seconds with an explicit "
            "recording start. Files without a time column are not supported yet. "
            "Evidence stays CSV_REPLAY; importing does not verify a physical device.",
            0,
        )
        source = card("1. Choose a file and inspect the captured rows", 1)
        actions = ttk.Frame(source, style="Card.TFrame")
        actions.grid(row=0, column=0, columnspan=4, sticky="ew")
        button(actions, "select_source", "Choose CSV…", self.select_source, 0)
        button(actions, "load_mapping", "Load mapping…", self.load_mapping, 1)
        field(source, "delimiter", "Separator", 1, choices=tuple(_DELIMITERS))
        ttk.Label(
            source,
            textvariable=self.snapshot,
            wraplength=870,
            justify="left",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=5)
        self.raw_table = ttk.Treeview(
            source,
            columns=("row",),
            show="headings",
            height=5,
            takefocus=True,
            style="Modern.Treeview",
        )
        self.raw_table.heading("row", text="Source row")
        self.raw_table.grid(row=3, column=0, columnspan=4, sticky="ew", pady=4)
        scrollbar_factory = getattr(ttk, "Scrollbar", None)
        if callable(scrollbar_factory):
            scrollbar = scrollbar_factory(
                source, orient="horizontal", command=self.raw_table.xview
            )
            scrollbar.grid(row=4, column=0, columnspan=4, sticky="ew")
            self.raw_table.configure(xscrollcommand=scrollbar.set)
        label(source, "First 5 data rows. Select the separator used by your file.", 5)

        mapping = card("2. Assign columns and units", 2)
        field(mapping, "name", "Mapping name", 0)
        field(
            mapping, "time_mode", "Time format", 0, 2, ("timestamp", "elapsed_seconds")
        )
        field(mapping, "time_column", "Time column", 1, choices=("",))
        self.origin_entry = field(mapping, "start_time_utc", "Recording start", 1, 2)
        label(
            mapping,
            "timestamp: each cell needs ISO time with Z or an offset. "
            "elapsed_seconds: enter the real start, for example "
            "2026-09-09T14:00:00-04:00. No time or start is invented.",
            2,
        )
        field(mapping, "input_column", "Input / reading column", 3, choices=("",))
        field(mapping, "input_unit", "Input unit", 3, 2, ("V", "mV"))
        field(mapping, "output_column", "Output column (optional)", 4, choices=("",))
        field(mapping, "output_unit", "Output unit", 4, 2, ("V", "mV"))
        field(mapping, "minimum_mv", "Minimum (mV)", 5)
        field(mapping, "maximum_mv", "Maximum (mV)", 5, 2)
        label(
            mapping,
            "One voltage column prepares a read setup. An input/output pair with "
            "at least 3 rows prepares DC analysis; 1 or 2 rows prepare a read setup. "
            "Both columns use the declared mV range; units "
            "are converted explicitly. Missing or invalid cells must be corrected "
            "in the source and selected again.",
            6,
        )
        finish = card("3. Check, save, and load into Setup", 3)
        action_bar = ttk.Frame(finish, style="Card.TFrame")
        action_bar.grid(row=0, column=0, columnspan=4, sticky="ew")
        self.preview_button = button(
            action_bar, "preview", "Check mapping", self.preview_mapping, 0
        )
        self.save_button = button(
            action_bar, "save_mapping", "Save mapping…", self.save_mapping, 1
        )
        self.publish_button = button(
            action_bar, "publish", "Publish package…", self.publish, 2
        )
        self.load_button = button(
            action_bar, "load_setup", "Load imported setup", self.load_setup, 3
        )
        for row, variable in ((1, self.review), (2, self.status)):
            ttk.Label(
                finish,
                textvariable=variable,
                wraplength=870,
                justify="left",
                style="Status.TLabel",
            ).grid(row=row, column=0, columnspan=4, sticky="w", pady=5)
        label(
            finish,
            "Save mapping creates a new JSON template. Publish creates a new "
            "folder with the captured source, mapping, replay, project, and hashes. "
            "Load imported setup prepares Setup for your review; it never starts a run.",
            3,
        )
        for variable in self.variables.values():
            trace = getattr(variable, "trace_add", None)
            if callable(trace):
                trace("write", self._changed)
        self.render()

    def _values(self) -> tuple[str, ...]:
        return tuple(str(variable.get()) for variable in self.variables.values())

    @property
    def has_unsaved_work(self) -> bool:
        """Keep reviewed data dirty across edits until a package is published."""
        return self._unpublished_work

    def _changed(self, *_args: object) -> None:
        if not self._suspend_changes:
            self.render()

    def _invalidate(self) -> None:
        self.preview = None
        self.publication = None
        self.review.set("Mapping changed. Check it again before saving or publishing.")

    def _sync_fields(self) -> None:
        values = self._values()
        if values == self._last_values:
            return
        self._last_values = values
        self._invalidate()
        self._message = "Check the updated mapping. Existing saved files are retained."
        if self._raw_bytes is None and self.source_path:
            self._message = _RESELECT_GUIDANCE
        delimiter = _DELIMITERS[str(self.variables["delimiter"].get())]
        if self._raw_bytes is not None and delimiter != self._source_delimiter:
            self._source_delimiter = delimiter
            self.source = None
            try:
                self.source = parse_voltage_table(self._raw_bytes, delimiter=delimiter)
            except ProductRequestError as error:
                self._message = str(error)
            self._show_source()

    def _show_source(self) -> None:
        for item in self.raw_table.get_children():
            self.raw_table.delete(item)
        columns = () if self.source is None else self.source.columns
        identifiers = ("row",) + tuple(
            f"column-{index}" for index in range(len(columns))
        )
        self.raw_table.configure(columns=identifiers)
        for identifier, heading in zip(identifiers, ("Source row",) + columns):
            self.raw_table.heading(identifier, text=heading)
            self.raw_table.column(identifier, width=140, minwidth=90, stretch=False)
        for key in ("time_column", "input_column", "output_column"):
            self.controls[key].configure(values=("",) + columns)
        if self.source is None:
            snapshot = f"No readable table. {_RESELECT_GUIDANCE}"
            if self._raw_bytes is not None:
                snapshot += (
                    f"\nCaptured: {self.source_path}\n"
                    f"SHA-256: {hashlib.sha256(self._raw_bytes).hexdigest()}\n"
                    "Separator changes still use this captured snapshot."
                )
            self.snapshot.set(snapshot)
            return
        self.snapshot.set(
            f"Captured: {self.source_path}\nSHA-256: {self.source.source_sha256}\n"
            "Preview and publication use this captured snapshot. Select the file "
            "again to include later edits."
        )
        for number, row in zip(self.source.row_numbers[:5], self.source.rows[:5]):
            self.raw_table.insert("", "end", values=(number,) + row)

    def _require_idle(self) -> None:
        if self.is_busy():
            raise ProductRequestError("Wait for the active job or batch to finish.")

    def _choose(self, mode: str) -> str:
        path = self.choose_path(mode)
        self._require_idle()
        if not isinstance(path, str):
            raise ProductRequestError("The file dialog must return a path string.")
        return path

    def _act(self, action: Callable[[], None]) -> None:
        try:
            self._require_idle()
            self._sync_fields()
            action()
        except (ProductRequestError, OSError, ValueError) as error:
            self._message = str(error)
            if self.source is None and self._raw_bytes is None and self.source_path:
                self._message += f" {_RESELECT_GUIDANCE}"
        self.render()

    def select_source(self) -> None:
        self._act(self._select_source)

    def _select_source(self) -> None:
        path = self._choose("source")
        if not path:
            return
        self._invalidate()
        self.source = None
        self._raw_bytes = None
        self.source_path = str(Path(path).resolve())
        self._source_delimiter = _DELIMITERS[str(self.variables["delimiter"].get())]
        try:
            self.source = load_voltage_table(path, delimiter=self._source_delimiter)
            self._raw_bytes = self.source.raw_bytes
        finally:
            self._show_source()
        self._message = (
            "Snapshot captured. Assign the time and voltage columns, then check."
        )

    def _mapping(self) -> VoltageImportMapping:
        values = {
            key: str(variable.get()).strip() for key, variable in self.variables.items()
        }
        origin = (
            values["start_time_utc"]
            if values["time_mode"] == "elapsed_seconds"
            else None
        )
        try:
            minimum = float(values["minimum_mv"])
            maximum = float(values["maximum_mv"])
        except ValueError as error:
            raise ProductRequestError(
                "Minimum and maximum must be numeric values in mV."
            ) from error
        return VoltageImportMapping(
            name=values["name"],
            time_column=values["time_column"],
            input_column=values["input_column"],
            input_unit=MeasurementUnit(values["input_unit"]),
            output_column=values["output_column"] or None,
            output_unit=(
                MeasurementUnit(values["output_unit"])
                if values["output_column"]
                else None
            ),
            time_mode=values["time_mode"],
            start_time_utc=origin,
            delimiter=_DELIMITERS[values["delimiter"]],
            minimum_mv=minimum,
            maximum_mv=maximum,
        )

    def preview_mapping(self) -> None:
        self._act(self._preview_mapping)

    def _preview_mapping(self) -> None:
        self._invalidate()
        if self.source is None:
            raise ProductRequestError("Choose a readable CSV source first.")
        self.preview = preview_voltage_import(self.source, self._mapping())
        self._unpublished_work = True
        mapping = self.preview.mapping
        channels = [
            ("Input", mapping.input_column, mapping.input_unit, "afe.ch0.input")
        ]
        if mapping.output_column is not None and mapping.output_unit is not None:
            channels.append(
                ("Output", mapping.output_column, mapping.output_unit, "afe.ch0.output")
            )
        converted = []
        for role, column, unit, channel in channels:
            values = [
                f"{record.value:g}"
                for record in self.preview.dataset.records
                if record.channel == channel
            ][:3]
            converted.append(
                f"{role}: {column} ({unit.value}) -> mV; first values: "
                f"{', '.join(values)}."
            )
        self.review.set(
            f"Checked {self.preview.row_count} source rows.\n"
            + "\n".join(converted)
            + "\n"
            "Evidence: CSV_REPLAY. Save this mapping or publish a new package."
        )
        self._message = "Mapping is valid. No files have been written by this check."

    def _require_preview(self) -> VoltageImportPreview:
        if self.preview is None:
            raise ProductRequestError(
                "Check the current mapping before saving or publishing."
            )
        return self.preview

    def save_mapping(self) -> None:
        self._act(self._save_mapping)

    def _save_mapping(self) -> None:
        preview = self._require_preview()
        path = self._choose("save_mapping")
        if path:
            saved = write_voltage_mapping(path, preview.mapping)
            self._message = (
                f"Mapping saved: {saved}. Load it with another matching CSV."
            )

    def load_mapping(self) -> None:
        self._act(self._load_mapping)

    def _load_mapping(self) -> None:
        path = self._choose("load_mapping")
        if not path:
            return
        mapping = load_voltage_mapping(path)
        values = {
            "name": mapping.name,
            "time_column": mapping.time_column,
            "input_column": mapping.input_column,
            "input_unit": mapping.input_unit.value,
            "output_column": mapping.output_column or "",
            "output_unit": "V"
            if mapping.output_unit is None
            else mapping.output_unit.value,
            "delimiter": next(
                name
                for name, delimiter in _DELIMITERS.items()
                if delimiter == mapping.delimiter
            ),
            "time_mode": mapping.time_mode,
            "start_time_utc": mapping.start_time_utc or "",
            "minimum_mv": str(mapping.minimum_mv),
            "maximum_mv": str(mapping.maximum_mv),
        }
        self._suspend_changes = True
        try:
            for key, value in values.items():
                self.variables[key].set(value)
        finally:
            self._suspend_changes = False
        self._sync_fields()
        self._invalidate()
        self._message = (
            f"Mapping loaded. {self._message}"
            if self.source is None and self._raw_bytes is not None
            else "Mapping loaded. Choose a matching CSV and check the assigned columns."
        )
        if mapping.time_mode == "elapsed_seconds":
            self._message += (
                " Confirm or update the actual recording start for this file."
            )

    def publish(self) -> None:
        self._act(self._publish)

    def _publish(self) -> None:
        preview = self._require_preview()
        path = self._choose("output")
        if path:
            self.publication = publish_voltage_import(
                path, preview, source_name=Path(self.source_path).name
            )
            self._unpublished_work = False
            self._message = (
                f"Package saved: {self.publication.output_directory}. "
                "Load imported setup, then review it in Setup before running."
            )

    def load_setup(self) -> None:
        self._act(self._load_setup)

    def _load_setup(self) -> None:
        if self.publication is None:
            raise ProductRequestError("Publish a checked package before loading Setup.")
        if self.on_load_setup(self.publication.configuration):
            self._message = (
                "Imported setup loaded. Review it in Setup; no run was started."
            )
        else:
            self._message = (
                "Setup loading was cancelled. The published package is retained."
            )

    def render(self) -> None:
        """Refresh changed controls only; never schedule work or move keyboard focus."""
        busy = self.is_busy()
        if not busy:
            self._sync_fields()
        state = (
            busy,
            self._values(),
            self.source is not None,
            self.preview is not None,
            self.publication is not None,
            self._message,
        )
        if state == self._render_state:
            return
        self._render_state = state
        for key, widget in self.controls.items():
            enabled = not busy
            if key == "start_time_utc":
                enabled = (
                    enabled and self.variables["time_mode"].get() == "elapsed_seconds"
                )
            elif key == "output_unit":
                enabled = enabled and bool(self.variables["output_column"].get())
            elif key == "preview":
                enabled = enabled and self.source is not None
            elif key in {"save_mapping", "publish"}:
                enabled = enabled and self.preview is not None
            elif key == "load_setup":
                enabled = enabled and self.publication is not None
            widget.configure(
                state=("readonly" if key in self._comboboxes else "normal")
                if enabled
                else "disabled"
            )
        self.status.set(
            "Import controls are paused while a job or project batch is active."
            if busy
            else self._message
        )


__all__ = ["ImportPage"]
