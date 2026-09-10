from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from analog_validation import EvidenceSource, MeasurementUnit
from analog_validation_app.dashboard import import_page as page_module
from analog_validation_app.dashboard.import_page import ImportPage
from analog_validation_app.import_packages import (
    load_voltage_mapping,
    write_voltage_mapping,
)
from analog_validation_app.models import ProductJobType
from analog_validation_app.tabular_import import VoltageImportMapping
from tests.unit.test_dashboard_app import FakeVariable, FakeWidget, fake_toolkit


class Variable(FakeVariable):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.callbacks: list[Any] = []
        self.set_count = 0

    def trace_add(self, mode: str, callback: Any) -> None:
        assert mode == "write"
        self.callbacks.append(callback)

    def set(self, value: str) -> None:
        super().set(value)
        self.set_count += 1
        for callback in self.callbacks:
            callback("variable", "", "write")


class Widget(FakeWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.configure_count = 0
        self.tabs: list[tuple[object, str]] = []

    def add(self, tab: object, *, text: str) -> None:
        self.tabs.append((tab, text))

    def configure(self, **kwargs: Any) -> None:
        super().configure(**kwargs)
        self.configure_count += 1

    def xview(self, *_args: object) -> None:
        pass

    def set(self, *_args: object) -> None:
        pass


def build_page(
    *, traces: bool = True, scrollbars: bool = False
) -> tuple[ImportPage, Any]:
    root, tk, _ttk = fake_toolkit()
    if traces:
        tk.StringVar = Variable
    toolkit = SimpleNamespace(
        Frame=Widget,
        LabelFrame=Widget,
        Label=Widget,
        Button=Widget,
        Entry=Widget,
        Combobox=Widget,
        Treeview=Widget,
    )
    if scrollbars:
        toolkit.Scrollbar = Widget
    notebook = Widget()
    state = SimpleNamespace(busy=False, paths={}, calls=[], loaded=[], accepted=True)

    def choose(mode: str) -> str:
        state.calls.append(mode)
        return state.paths.get(mode, "")

    def load(configuration: object) -> bool:
        state.loaded.append(configuration)
        return state.accepted

    page = ImportPage(
        root,
        tk,
        toolkit,
        notebook,
        on_load_setup=load,
        is_busy=lambda: state.busy,
        choose_path=choose,
    )
    assert notebook.tabs == [(page.tab, "Import data")]
    return page, state


def voltage_csv(path: Path, *, separator: str = ",", elapsed: bool = False) -> bytes:
    rows = [separator.join(("Time", "Input", "Output"))]
    for index in range(6):
        time = str(index) if elapsed else f"2026-09-09T12:00:0{index}Z"
        rows.append(
            separator.join((time, str(0.2 + index / 10), str(400 + index * 200)))
        )
    content = ("\n".join(rows) + "\n").encode("utf-8")
    path.write_bytes(content)
    return content


def assign(page: ImportPage, **values: str) -> None:
    for key, value in values.items():
        page.variables[key].set(value)
    page.render()


def select_and_check(
    page: ImportPage, state: Any, path: Path, *, paired: bool = True
) -> None:
    state.paths["source"] = str(path)
    page.select_source()
    values = {"time_column": "Time", "input_column": "Input", "input_unit": "V"}
    if paired:
        values.update(output_column="Output", output_unit="mV")
    assign(page, **values)
    page.preview_mapping()
    assert page.preview is not None, page.status.get()


def test_first_use_blocks_unreviewed_actions_and_preserves_cancelled_selection() -> (
    None
):
    page, state = build_page(traces=False)
    assert not page.has_unsaved_work
    assert page.origin_entry.config["state"] == "disabled"
    for name in ("preview", "save_mapping", "publish", "load_setup", "output_unit"):
        assert page.controls[name].config["state"] == "disabled"
    page.preview_mapping()
    assert "Choose a readable CSV" in page.status.get()
    page.save_mapping()
    assert "Check the current mapping" in page.status.get()
    page.publish()
    page.load_setup()
    assert "Publish a checked package" in page.status.get()
    assert not state.calls
    page.select_source()
    page.load_mapping()
    assert state.calls == ["source", "load_mapping"]
    assert page.source is None


def test_paired_import_snapshot_preview_publish_and_guarded_load(
    tmp_path: Path,
) -> None:
    page, state = build_page(scrollbars=True)
    path = tmp_path / "external.csv"
    original = voltage_csv(path)
    select_and_check(page, state, path)
    assert len(page.raw_table.rows) == 5
    assert next(iter(page.raw_table.rows.values()))[0] == 2
    assert page.preview is not None
    assert page.preview.row_count == 6
    assert page.source is not None
    assert page.source.source_sha256 in page.snapshot.get()
    assert "captured snapshot" in page.snapshot.get()
    assert "CSV_REPLAY" in page.review.get()
    assert "Input: Input (V) -> mV; first values: 200, 300, 400." in page.review.get()
    assert (
        "Output: Output (mV) -> mV; first values: 400, 600, 800." in page.review.get()
    )
    assert page.has_unsaved_work
    path.write_text("edited after inspection", encoding="utf-8")
    state.paths["save_mapping"] = str(tmp_path / "mapping.json")
    page.save_mapping()
    assert page.has_unsaved_work
    assert (
        load_voltage_mapping(tmp_path / "mapping.json").output_unit
        is MeasurementUnit.MILLIVOLT
    )
    state.paths["output"] = str(tmp_path / "package")
    page.publish()
    assert page.publication is not None, page.status.get()
    assert not page.has_unsaved_work
    assert any(
        item.read_bytes() == original
        for item in page.publication.output_directory.rglob("*.csv")
    )
    assert page.publication.configuration.job_type is ProductJobType.DC_ANALYSIS
    assert not state.loaded
    state.accepted = False
    page.load_setup()
    assert "cancelled" in page.status.get()
    assert page.publication.project_path.exists()
    state.accepted = True
    page.load_setup()
    assert state.loaded[-1] == page.publication.configuration
    assert "no run was started" in page.status.get()
    old_directory = page.publication.output_directory
    assign(page, minimum_mv="-10")
    assert page.preview is None
    assert page.publication is None
    assert old_directory.exists()
    assert page.load_button.config["state"] == "disabled"


def test_mapping_templates_restore_before_source_and_elapsed_time(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "relative.csv"
    original = voltage_csv(path, separator=";", elapsed=True)
    state.paths["source"] = str(path)
    page.select_source()
    assert page.source is not None
    assert len(page.source.columns) == 1
    path.write_text("unrelated later edit", encoding="utf-8")
    assign(
        page,
        delimiter="Semicolon (;)",
        time_mode="elapsed_seconds",
        start_time_utc="2026-09-09T08:00:00-04:00",
        time_column="Time",
        input_column="Input",
        output_column="Output",
        output_unit="mV",
    )
    assert page.origin_entry.config["state"] == "normal"
    assert page.source is not None and page.source.raw_bytes == original
    page.preview_mapping()
    assert page.preview is not None, page.status.get()
    state.paths["save_mapping"] = str(tmp_path / "elapsed-mapping.json")
    page.save_mapping()
    mapping = load_voltage_mapping(tmp_path / "elapsed-mapping.json")
    assert mapping.delimiter == ";"
    assert mapping.start_time_utc is not None
    assert mapping.start_time_utc == "2026-09-09T08:00:00-04:00"
    restored, second_state = build_page()
    second_state.paths["load_mapping"] = str(tmp_path / "elapsed-mapping.json")
    restored.load_mapping()
    assert "actual recording start for this file" in restored.status.get()
    assert restored.source is None
    assert restored.variables["output_unit"].get() == "mV"
    assert restored.variables["delimiter"].get() == "Semicolon (;)"
    assert restored.variables["time_mode"].get() == "elapsed_seconds"
    assert restored.preview is None
    other = tmp_path / "same-columns.csv"
    other.write_bytes(original)
    second_state.paths["source"] = str(other)
    restored.select_source()
    restored.preview_mapping()
    assert restored.preview is not None, restored.status.get()
    assert restored.preview.mapping == mapping


def test_single_column_read_mapping_and_repeat_template_load_require_review(
    tmp_path: Path,
) -> None:
    page, state = build_page(traces=False)
    path = tmp_path / "external.csv"
    voltage_csv(path)
    select_and_check(page, state, path, paired=False)
    assert page.preview is not None
    assert page.preview.mapping.output_unit is None
    assert "Input: Input (V) -> mV; first values: 200" in page.review.get()
    assert "Output:" not in page.review.get()
    state.paths["save_mapping"] = str(tmp_path / "mapping.json")
    page.save_mapping()
    state.paths["output"] = str(tmp_path / "read-package")
    page.publish()
    assert page.publication is not None
    assert page.publication.configuration.job_type is ProductJobType.READ
    state.paths["load_mapping"] = str(tmp_path / "mapping.json")
    page.load_mapping()
    assert page.preview is None
    assert page.publication is None
    assert page.variables["start_time_utc"].get() == ""
    assert page.variables["output_unit"].get() == "V"
    page.preview_mapping()
    assert page.preview is not None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("minimum_mv", "words", "numeric values in mV"),
        ("maximum_mv", "nan", "finite"),
        ("time_column", "absent", "absent"),
        ("input_column", "", "column"),
    ],
)
def test_invalid_mapping_cannot_publish_and_retains_unpublished_work(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    page, state = build_page()
    path = tmp_path / "input.csv"
    voltage_csv(path)
    select_and_check(page, state, path)
    assign(page, **{field: value})
    assert page.has_unsaved_work
    page.preview_mapping()
    assert page.preview is None
    assert message.lower() in page.status.get().lower()
    assert page.publish_button.config["state"] == "disabled"


@pytest.mark.parametrize("origin", ["", "yesterday", "2026-09-09T08:00:00"])
def test_elapsed_start_must_be_explicit_and_timezone_aware(
    tmp_path: Path, origin: str
) -> None:
    page, state = build_page()
    path = tmp_path / "relative.csv"
    voltage_csv(path, elapsed=True)
    state.paths["source"] = str(path)
    page.select_source()
    assign(
        page,
        time_mode="elapsed_seconds",
        time_column="Time",
        input_column="Input",
        start_time_utc=origin,
    )
    page.preview_mapping()
    assert page.preview is None
    assert (
        "timezone" in page.status.get().lower()
        or "time zone" in page.status.get().lower()
    )
    assert not page.has_unsaved_work


def test_row_and_column_error_is_visible_without_imputation(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "bad-cell.csv"
    path.write_text(
        "Time,Input\n2026-09-09T12:00:00Z,1.2\n2026-09-09T12:00:01Z,broken\n",
        encoding="utf-8",
    )
    state.paths["source"] = str(path)
    page.select_source()
    assign(page, time_column="Time", input_column="Input")
    page.preview_mapping()
    assert page.preview is None
    assert "3" in page.status.get()
    assert "Input" in page.status.get()
    assert "broken" in str(tuple(page.raw_table.rows.values()))


def test_busy_blocks_all_import_actions_and_resumes_without_polling_or_refocus(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path)
    select_and_check(page, state, path)
    prior_calls = tuple(state.calls)
    state.busy = True
    page.render()
    assert all(
        widget.config["state"] == "disabled" for widget in page.controls.values()
    )
    for action in (
        page.select_source,
        page.preview_mapping,
        page.save_mapping,
        page.load_mapping,
        page.publish,
        page.load_setup,
    ):
        action()
    assert tuple(state.calls) == prior_calls
    assert "paused" in page.status.get()
    assign(page, name="Changed while worker busy")
    state.busy = False
    page.render()
    assert page.preview is None
    assert page.has_unsaved_work
    assert page.controls["input_column"].config["state"] == "readonly"
    configured = tuple(widget.configure_count for widget in page.controls.values())
    table_count = page.raw_table.configure_count
    status_sets = page.status.set_count
    page.render()
    assert (
        tuple(widget.configure_count for widget in page.controls.values()) == configured
    )
    assert page.raw_table.configure_count == table_count
    assert page.status.set_count == status_sets


def test_busy_transition_during_dialog_prevents_source_read(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path)

    def choose(_mode: str) -> str:
        state.busy = True
        return str(path)

    page.choose_path = choose
    page.select_source()
    assert page.source is None
    assert not page.has_unsaved_work
    state.busy = False
    page.render()
    assert "Wait for the active job" in page.status.get()


def test_cancelled_saves_and_publish_do_not_mutate_review(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path)
    select_and_check(page, state, path)
    preview = page.preview
    state.paths["source"] = ""
    page.save_mapping()
    page.publish()
    page.select_source()
    page.load_mapping()
    assert page.preview is preview
    assert page.publication is None
    assert page.has_unsaved_work
    assert list(tmp_path.iterdir()) == [path]


def test_create_new_mapping_and_package_refuse_replacement(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path)
    select_and_check(page, state, path)
    target = tmp_path / "mapping.json"
    target.write_text("keep original", encoding="utf-8")
    state.paths["save_mapping"] = str(target)
    page.save_mapping()
    assert target.read_text(encoding="utf-8") == "keep original"
    assert "exist" in page.status.get().lower()
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "retained.txt"
    sentinel.write_text("keep original", encoding="utf-8")
    state.paths["output"] = str(existing)
    page.publish()
    assert page.publication is None
    assert sentinel.read_text(encoding="utf-8") == "keep original"
    assert page.has_unsaved_work
    assert "exist" in page.status.get().lower()


def test_failed_source_and_bad_mapping_are_reported_without_using_old_data(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path)
    select_and_check(page, state, path)
    source = page.source
    invalid_mapping = tmp_path / "bad.json"
    invalid_mapping.write_text("not json", encoding="utf-8")
    state.paths["load_mapping"] = str(invalid_mapping)
    page.load_mapping()
    assert page.source is source
    assert page.preview is not None
    state.paths["source"] = str(tmp_path / "missing.csv")
    page.select_source()
    assert page.source is None
    assert page.preview is None
    assert not page.raw_table.rows
    assert "No readable table" in page.snapshot.get()
    assert page.has_unsaved_work


def test_loaded_mapping_reparses_existing_captured_bytes_with_its_delimiter(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "external.csv"
    voltage_csv(path, separator="\t")
    state.paths["source"] = str(path)
    page.select_source()
    mapping = VoltageImportMapping(
        name="Tab voltage",
        time_column="Time",
        input_column="Input",
        input_unit=MeasurementUnit.VOLT,
        delimiter="\t",
    )
    target = tmp_path / "tab.json"
    write_voltage_mapping(target, mapping)
    state.paths["load_mapping"] = str(target)
    page.load_mapping()
    assert page.variables["delimiter"].get() == "Tab"
    assert page.source is not None and page.source.columns == (
        "Time",
        "Input",
        "Output",
    )
    page.preview_mapping()
    assert page.preview is not None
    assert all(
        record.declared_source is EvidenceSource.CSV_REPLAY
        for record in page.preview.dataset.records
    )


def test_delimiter_parse_error_preserves_bytes_for_correction(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "commas.csv"
    path.write_text('Time,Input\n2026-09-09T12:00:00Z,"1;2"\n', encoding="utf-8")
    state.paths["source"] = str(path)
    page.select_source()
    assert page.source is not None
    raw = page.source.raw_bytes
    assign(page, delimiter="Semicolon (;)")
    assert page.source is None
    assert page._raw_bytes == raw
    assert "SHA-256:" in page.snapshot.get()
    assert page.preview is None
    assign(page, delimiter="Comma (,)")
    assert page.source is not None and page.source.raw_bytes == raw


def test_loaded_template_preserves_separator_error_until_user_corrects_it(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "commas.csv"
    path.write_text('Time,Input\n2026-09-09T12:00:00Z,"1;2"\n', encoding="utf-8")
    state.paths["source"] = str(path)
    page.select_source()
    mapping = VoltageImportMapping(
        name="Other separator",
        time_column="Time",
        input_column="Input",
        input_unit=MeasurementUnit.VOLT,
        delimiter=";",
    )
    target = tmp_path / "other.json"
    write_voltage_mapping(target, mapping)
    state.paths["load_mapping"] = str(target)
    page.load_mapping()
    assert page.source is None
    assert "Mapping loaded" in page.status.get()
    assert "row 2" in page.status.get()
    assert page.publish_button.config["state"] == "disabled"


def test_initial_wrong_separator_requires_selecting_file_again(tmp_path: Path) -> None:
    page, state = build_page()
    path = tmp_path / "semicolon.csv"
    path.write_text(
        "Time;Input;Note\n"
        "2026-09-09T12:00:00Z;1.2;reference,check\n"
        "2026-09-09T12:00:01Z;1.3;reference\n",
        encoding="utf-8",
    )
    state.paths["source"] = str(path)
    page.select_source()
    assert page.source is None and page._raw_bytes is None
    assert (
        "Select the correct separator, then choose the file again." in page.status.get()
    )
    assign(page, delimiter="Semicolon (;)")
    assert page.source is None
    assert (
        "Select the correct separator, then choose the file again." in page.status.get()
    )
    page.select_source()
    assert page.source is not None
    assert page.source.columns == ("Time", "Input", "Note")
    assign(page, time_column="Time", input_column="Input")
    page.preview_mapping()
    assert page.preview is not None, page.status.get()


def test_two_paired_rows_publish_read_setup_with_both_columns_retained(
    tmp_path: Path,
) -> None:
    page, state = build_page()
    path = tmp_path / "two-pairs.csv"
    content = voltage_csv(path)
    path.write_bytes(b"\n".join(content.splitlines()[:3]) + b"\n")
    select_and_check(page, state, path)
    assert page.preview is not None and page.preview.row_count == 2
    assert len(page.preview.dataset.records) == 4
    state.paths["output"] = str(tmp_path / "short-paired-package")
    page.publish()
    assert page.publication is not None, page.status.get()
    assert page.publication.configuration.job_type is ProductJobType.READ
    from analog_validation import load_csv_replay

    replay = load_csv_replay(page.publication.replay_path)
    assert {record.channel for record in replay.records} == {
        "afe.ch0.input",
        "afe.ch0.output",
    }
    assert len(replay.records) == 4


def test_invalid_dialog_contract_and_expected_io_error_show_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, _state = build_page()
    page.choose_path = lambda _mode: None  # type: ignore[assignment,return-value]
    page.select_source()
    assert "path string" in page.status.get()
    page.choose_path = lambda _mode: str(tmp_path / "unreadable.csv")

    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("Source could not be read")

    monkeypatch.setattr(page_module, "load_voltage_table", denied)
    page.select_source()
    assert "could not be read" in page.status.get()
