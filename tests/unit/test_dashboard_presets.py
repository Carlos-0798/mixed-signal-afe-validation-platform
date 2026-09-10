from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from analog_validation import MeasurementUnit, ReadOperation
from analog_validation_app import (
    DashboardApplication,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
)
from analog_validation_app.dashboard.presets import draft_from_configuration
from analog_validation_app.dashboard.project_widgets import ProjectPage
from analog_validation_app.dashboard.project_workspace import ProjectWorkspace
from analog_validation_app.dashboard.wizard import DashboardWizardDraft
from analog_validation_app.factories import SerialSourceConfig
from analog_validation_app.product_workflows import ProductWorkflowConfiguration
from analog_validation_app.projects import (
    ValidationPreset,
    ValidationProject,
    write_validation_project,
)
from tests.unit.test_dashboard_app import FakeVariable
from tests.unit.test_dashboard_application import advance_to_configuration
from tests.unit.test_dashboard_projects import Widget


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    (
        ("abc", "3300"),
        ("0", "abc"),
        ("nan", "3300"),
        ("0", "inf"),
        ("2", "1"),
        ("1", "1"),
    ),
)
def test_invalid_replay_bounds_do_not_block_switching_back_to_simulator(
    tmp_path: Path, minimum: str, maximum: str
) -> None:
    application = DashboardApplication()
    assert application.select_source(ProductSourceMode.CSV_REPLAY)
    draft = advance_to_configuration(application)
    invalid = replace(
        draft,
        replay_path=str(tmp_path / "not-opened.csv"),
        replay_minimum=minimum,
        replay_maximum=maximum,
    )
    # The selected Replay source continues to reject invalid or unordered bounds.
    with pytest.raises(ProductRequestError):
        invalid.to_product_configuration()
    assert not application.prepare_review(invalid)
    assert application.issue_field_id in {"replay_minimum", "replay_maximum"}
    assert application.back() and application.back()
    assert application.select_source(ProductSourceMode.SIMULATOR)
    assert application.next() and application.next()

    assert application.prepare_review(application.wizard_state.draft)

    configuration = application.wizard_state.draft.to_product_configuration()
    defaults = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    assert configuration.replay_minimum == defaults.replay_minimum
    assert configuration.replay_maximum == defaults.replay_maximum
    assert application.wizard_state.can_run
    assert application.wizard_state.issue is None
    assert application.dashboard_state.progress.worker_state is ProductWorkerState.IDLE
    assert not tuple(tmp_path.iterdir())
    assert application.request_close()


def test_direct_non_replay_draft_uses_defaults_for_invalid_hidden_bounds() -> None:
    draft = replace(DashboardWizardDraft(), replay_minimum="bad", replay_maximum="bad")
    configuration = draft.to_product_configuration()
    assert configuration == ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )


@pytest.mark.parametrize("job_type", tuple(ProductJobType))
@pytest.mark.parametrize(
    "source_mode", (ProductSourceMode.SIMULATOR, ProductSourceMode.CSV_REPLAY)
)
def test_saved_offline_configuration_round_trips_without_reading_input(
    tmp_path: Path, job_type: ProductJobType, source_mode: ProductSourceMode
) -> None:
    configuration = ProductWorkflowConfiguration(
        source_mode,
        job_type,
        primary_channel="board.input",
        secondary_channel="board.output",
        state_channel="board.state",
        sample_count=12,
        rising_count=8,
        falling_count=14,
        replay_path=tmp_path / "not-created.csv"
        if source_mode is ProductSourceMode.CSV_REPLAY
        else None,
        replay_minimum=-2.5,
        replay_maximum=4200.25,
        low_output_limit=20.5,
        high_output_limit=3200.5,
        target_gain=1.1234567890123457,
        gain_tolerance=0.0725,
        max_abs_offset=18.5,
        min_r_squared=0.99875,
        max_rmse=0.8,
        coefficient_id="saved-calibration",
        coefficient_version="2",
        max_calibration_rmse=0.85,
        max_calibration_mean_absolute_error=0.7,
        max_calibration_absolute_error=1.5,
        minimum_calibration_rmse_reduction=0.125,
        minimum_high_threshold=910.5,
        maximum_high_threshold=1110.5,
        minimum_low_threshold=810.5,
        maximum_low_threshold=1010.5,
        minimum_width=25.5,
        maximum_width=205.5,
        maximum_width_span=5.5,
        frequency_channel="board.frequency",
        frequency_point_count=13,
        frequency_minimum_hz=12.5,
        frequency_maximum_hz=12500.5,
        frequency_input_amplitude=800.5,
        simulated_cutoff_frequency_hz=900.5,
        target_cutoff_frequency_hz=1050.5,
        cutoff_relative_tolerance=0.125,
        cutoff_drop_db=3.1,
        monitor_sample_interval_seconds=0.125,
        monitor_time_window_seconds=3.5,
        monitor_max_buffer_points=127,
        monitor_include_secondary=False,
        monitor_include_state=False,
    )

    draft = draft_from_configuration(configuration)

    assert draft.to_product_configuration() == configuration
    assert draft.target_gain == "1.1234567890123457"
    assert draft.export_path == ""
    assert draft.serial_port == ""
    assert not draft.serial_confirm_read_only
    assert not tuple(tmp_path.iterdir())


def test_digital_read_preserves_operation_and_boolean_unit() -> None:
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        primary_channel="afe.ch0.threshold",
        operation=ReadOperation.DIGITAL,
        unit=MeasurementUnit.BOOLEAN,
    )
    assert (
        draft_from_configuration(configuration).to_product_configuration()
        == configuration
    )


def test_preset_conversion_rejects_invalid_type_serial_and_lossy_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ProductRequestError, match="ProductWorkflowConfiguration"):
        draft_from_configuration(cast(Any, {}))
    serial = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.READ,
        serial_config=SerialSourceConfig(port_id="NOT-OPENED"),
        confirm_read_only=True,
    )
    with pytest.raises(ProductRequestError, match="Only Simulator and CSV Replay"):
        draft_from_configuration(serial)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    monkeypatch.setattr(
        DashboardWizardDraft,
        "to_product_configuration",
        lambda self: replace(configuration, sample_count=6),
    )
    with pytest.raises(ProductRequestError, match="represented exactly"):
        draft_from_configuration(configuration)


def test_workspace_resolves_replay_at_project_without_changing_saved_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_directory = tmp_path / "project"
    project_directory.mkdir()
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.DC_ANALYSIS,
        replay_path=Path("inputs/not-created.csv"),
    )
    project = ValidationProject(
        "saved-project",
        "Saved project",
        "",
        (ValidationPreset("dc", "DC", configuration),),
    )
    project_path = write_validation_project(project_directory / "project.json", project)
    original = project_path.read_bytes()
    model = ProjectWorkspace(lambda: False)
    model.open(str(project_path))
    loaded_project = model.project
    monkeypatch.chdir(tmp_path)

    copied = model.configuration_for_setup("dc")

    assert copied.replay_path == project_directory / "inputs/not-created.csv"
    assert copied.replay_path is not None and not copied.replay_path.exists()
    assert model.project == loaded_project
    assert not model.dirty
    assert project_path.read_bytes() == original
    assert model.project is not None
    model.project = project
    assert model.configuration_for_setup("dc") == copied
    model.project = replace(project, presets=(ValidationPreset("dc", "DC", copied),))
    assert model.configuration_for_setup("dc") == copied


def test_workspace_load_requires_known_preset_and_idle_project(tmp_path: Path) -> None:
    model = ProjectWorkspace(lambda: False)
    with pytest.raises(ProductRequestError, match="Open or create"):
        model.configuration_for_setup("dc")
    model.create(str(tmp_path / "project.json"), "project", "Project")
    with pytest.raises(ProductRequestError, match="existing preset"):
        model.configuration_for_setup("missing")
    assert model.project is not None
    assert (
        model.configuration_for_setup("dc-default")
        == model.project.presets[1].configuration
    )
    model.other_busy = lambda: True
    with pytest.raises(ProductRequestError, match="active test"):
        model.configuration_for_setup("dc-default")


def test_project_load_action_requires_single_selection_and_preserves_original(
    tmp_path: Path,
) -> None:
    model = ProjectWorkspace(lambda: False)
    selected: list[ProductWorkflowConfiguration] = []
    accepted = False

    def load(configuration: ProductWorkflowConfiguration) -> bool:
        selected.append(configuration)
        return accepted

    ttk = SimpleNamespace(
        **{
            name: Widget
            for name in (
                "Frame",
                "LabelFrame",
                "Label",
                "Entry",
                "Button",
                "Treeview",
                "Scrollbar",
                "Progressbar",
            )
        }
    )
    page = ProjectPage(
        Widget(),
        SimpleNamespace(StringVar=FakeVariable),
        ttk,
        Widget(),
        model,
        lambda _: "",
        DashboardWizardDraft,
        load,
    )
    assert page.load_setup_button.config["state"] == "disabled"
    model.create(str(tmp_path / "project.json"), "project", "Project")
    original = model.project
    page.render()
    with pytest.raises(ProductRequestError, match="exactly one"):
        page.load_setup()
    page.presets.selection_set(("dc-default", "read-default"))
    page.render()
    assert page.load_setup_button.config["state"] == "disabled"
    with pytest.raises(ProductRequestError, match="exactly one"):
        page.load_setup()
    page.presets.selection_set(("dc-default",))
    page.render()
    assert page.load_setup_button.config["state"] == "normal"
    status_before = model.status
    page.load_setup()
    assert model.status == status_before
    assert len(selected) == 1
    accepted = True
    page.load_setup_button.kwargs["command"]()
    assert "Loaded dc-default into Setup" in model.status
    assert "unchanged" in model.status
    assert selected[0] == selected[1]
    assert model.project == original
    assert not model.dirty
    model.other_busy = lambda: True
    page.render()
    assert page.load_setup_button.config["state"] == "disabled"
    with pytest.raises(ProductRequestError, match="active test"):
        page.load_setup()
    assert len(selected) == 2
    model.other_busy = lambda: False
    page.on_load_setup = None
    page.render()
    assert page.load_setup_button.config["state"] == "disabled"
    with pytest.raises(ProductRequestError, match="unavailable"):
        page.load_setup()
