from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Thread
from typing import Any, cast

import pytest

import analog_validation_app.dashboard.wizard as wizard_module
from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    DASHBOARD_WIZARD_SCHEMA_VERSION,
    MAX_DASHBOARD_WIZARD_PORTS,
    MAX_DASHBOARD_WIZARD_REVIEW_LINES,
    MAX_DASHBOARD_WIZARD_TEXT_CHARS,
    DashboardWizardDraft,
    DashboardWizardGuidance,
    DashboardWizardPresenter,
    DashboardWizardState,
    DashboardWizardStep,
    ProductAppError,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"


def issue() -> UserIssue:
    return UserIssue(
        UserIssueCode.INVALID_REQUEST,
        UserIssueSeverity.ERROR,
        "The form is invalid.",
        "A required value is missing.",
        "Correct the value and retry.",
        "ProductRequestError",
    )


def configuration_presenter() -> DashboardWizardPresenter:
    presenter = DashboardWizardPresenter()
    presenter.next()
    presenter.next()
    return presenter


def reviewed_presenter() -> DashboardWizardPresenter:
    presenter = configuration_presenter()
    presenter.present_review(presenter.state.draft, ("Reviewed safely.",))
    return presenter


@pytest.mark.parametrize(
    "value",
    [
        DashboardWizardGuidance(1, "Title", "What", "Why", "Confirm"),
        DashboardWizardGuidance(6, "Title", "What", "Why", "Confirm"),
    ],
)
def test_guidance_accepts_fixed_six_step_bounds(
    value: DashboardWizardGuidance,
) -> None:
    assert 1 <= value.number <= 6


@pytest.mark.parametrize(
    "arguments",
    [
        (0, "Title", "What", "Why", "Confirm"),
        (True, "Title", "What", "Why", "Confirm"),
        (1, "", "What", "Why", "Confirm"),
        (1, "x" * (MAX_DASHBOARD_WIZARD_TEXT_CHARS + 1), "What", "Why", "Confirm"),
        (1, "Bad\nTitle", "What", "Why", "Confirm"),
    ],
)
def test_guidance_rejects_invalid_number_and_text(
    arguments: tuple[object, ...],
) -> None:
    with pytest.raises(ProductRequestError):
        DashboardWizardGuidance(*cast(Any, arguments))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_mode": "SIMULATOR"}, "source_mode"),
        ({"job_type": "READ"}, "job_type"),
        ({"operation": "ANALOG"}, "operation"),
        ({"unit": "mV"}, "unit"),
        ({"export_format": "json"}, "export_format"),
        ({"profile_name": ""}, "profile_name"),
        ({"sample_count": " bad"}, "stripped"),
        ({"sample_count": "bad\nvalue"}, "printable"),
        ({"serial_confirm_read_only": "yes"}, "boolean"),
        (
            {
                "source_mode": ProductSourceMode.SERIAL_READ_ONLY,
                "job_type": ProductJobType.DC_ANALYSIS,
            },
            "does not support",
        ),
        (
            {
                "source_mode": ProductSourceMode.SIMULATOR,
                "profile_name": "msp430-equipment-health",
            },
            "does not support",
        ),
    ],
)
def test_draft_rejects_invalid_types_text_and_catalog_combinations(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductAppError, match=message):
        DashboardWizardDraft(**cast(Any, changes))


def test_draft_converts_simulator_replay_and_serial_without_opening_resources() -> None:
    simulator = DashboardWizardDraft().to_product_configuration()
    replay = DashboardWizardDraft(
        source_mode=ProductSourceMode.CSV_REPLAY,
        replay_path=str(GOLDEN_REPLAY),
        replay_minimum="0",
        replay_maximum="3300",
    ).to_product_configuration()
    serial = DashboardWizardDraft(
        source_mode=ProductSourceMode.SERIAL_READ_ONLY,
        serial_port="MEMORY:1",
        serial_confirm_read_only=True,
        sample_count="20",
    ).to_product_configuration()

    assert simulator.source_mode is ProductSourceMode.SIMULATOR
    assert replay.replay_path == GOLDEN_REPLAY
    assert serial.serial_config is not None
    assert serial.serial_config.max_buffered_measurements == 160
    assert serial.confirm_read_only is True


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sample_count": "many"}, "integer"),
        ({"target_gain": "much"}, "numeric"),
        ({"target_gain": "nan"}, "finite"),
        (
            {
                "source_mode": ProductSourceMode.CSV_REPLAY,
                "replay_path": "",
            },
            "replay_path",
        ),
        (
            {
                "source_mode": ProductSourceMode.SERIAL_READ_ONLY,
                "serial_port": "",
                "serial_confirm_read_only": True,
            },
            "serial_port",
        ),
        (
            {
                "source_mode": ProductSourceMode.SERIAL_READ_ONLY,
                "serial_port": "MEMORY:1",
                "serial_baud_rate": "fast",
                "serial_confirm_read_only": True,
            },
            "serial_baud_rate",
        ),
    ],
)
def test_draft_conversion_rejects_unparseable_values(
    changes: dict[str, object], message: str
) -> None:
    draft = DashboardWizardDraft(**cast(Any, changes))
    with pytest.raises(ProductRequestError, match=message):
        draft.to_product_configuration()


def test_wizard_state_exposes_fixed_choices_guidance_and_permissions() -> None:
    initial = DashboardWizardState(
        0, DashboardWizardStep.SOURCE, DashboardWizardDraft()
    )
    assert initial.guidance.number == 1
    assert initial.source_modes == tuple(ProductSourceMode)
    assert initial.job_types == (
        ProductJobType.READ,
        ProductJobType.DC_ANALYSIS,
        ProductJobType.HYSTERESIS_ANALYSIS,
    )
    assert initial.profile_identities == ("afe/1",)
    assert initial.can_back is False
    assert initial.can_next is True
    assert initial.can_prepare_review is False
    assert initial.can_run is False
    assert initial.can_cancel is False
    assert initial.can_export is False
    assert DASHBOARD_WIZARD_SCHEMA_VERSION == "dashboard-wizard.v1"


@pytest.mark.parametrize(
    "changes",
    [
        {"revision": -1},
        {"revision": True},
        {"step": "SOURCE"},
        {"draft": object()},
        {"review_lines": []},
        {"review_lines": ("ok",) * (MAX_DASHBOARD_WIZARD_REVIEW_LINES + 1)},
        {"review_lines": ("bad\nline",)},
        {"discovered_ports": []},
        {
            "discovered_ports": (SerialPortInfo("MEMORY:1"),)
            * (MAX_DASHBOARD_WIZARD_PORTS + 1)
        },
        {"discovered_ports": (object(),)},
        {"issue": object()},
        {"export_available": "yes"},
        {"export_message": ""},
        {"schema_version": "dashboard-wizard.v2"},
    ],
)
def test_wizard_state_rejects_invalid_contract_fields(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "revision": 0,
        "step": DashboardWizardStep.SOURCE,
        "draft": DashboardWizardDraft(),
    }
    values.update(changes)
    with pytest.raises(ProductRequestError):
        DashboardWizardState(**cast(Any, values))


def test_profile_identity_reports_catalog_empty_defensively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = DashboardWizardState(0, DashboardWizardStep.SOURCE, DashboardWizardDraft())
    monkeypatch.setattr(wizard_module, "list_product_profiles", lambda: ())
    with pytest.raises(ProductAppError, match="no profile"):
        _ = state.profile_identities


def test_presenter_runs_the_six_steps_and_preserves_review_permissions() -> None:
    presenter = DashboardWizardPresenter()
    assert presenter.state.step is DashboardWizardStep.SOURCE
    presenter.select_source(ProductSourceMode.CSV_REPLAY)
    first_revision = presenter.state.revision
    presenter.select_profile("afe", "1")
    assert presenter.state.revision == first_revision
    presenter.next()
    presenter.select_job(ProductJobType.DC_ANALYSIS)
    presenter.next()
    draft = replace(
        presenter.state.draft,
        replay_path=str(GOLDEN_REPLAY),
        sample_count="2",
    )
    presenter.submit_configuration(draft)
    presenter.present_review(draft, ("CSV validated.", "Hardware not claimed."))
    assert presenter.state.can_run is True
    presenter.begin_run()
    assert presenter.state.can_cancel is True
    presenter.finish_run(export_available=True)
    assert presenter.state.can_export is True
    presenter.present_export("result.json")
    assert presenter.state.export_message == "Exported safely: result.json"
    presenter.back()
    assert presenter.state.step is DashboardWizardStep.CONFIGURATION


def test_source_and_profile_selection_follow_compatibility_without_guessing() -> None:
    presenter = DashboardWizardPresenter()
    state = presenter.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    assert state.draft.job_type is ProductJobType.READ
    assert state.profile_identities == (
        "afe/1",
        "msp430-equipment-health/1",
    )
    state = presenter.select_profile("msp430-equipment-health", "1")
    assert state.draft.profile_name == "msp430-equipment-health"


def test_back_transitions_are_explicit_for_test_configuration_and_review() -> None:
    test_step = DashboardWizardPresenter()
    test_step.next()
    assert test_step.back().step is DashboardWizardStep.SOURCE

    configuration = configuration_presenter()
    assert configuration.back().step is DashboardWizardStep.TEST

    review = reviewed_presenter()
    assert review.back().step is DashboardWizardStep.CONFIGURATION


def test_presenter_ports_issue_and_export_are_typed() -> None:
    serial = DashboardWizardPresenter()
    serial.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    ports = (SerialPortInfo("MEMORY:1", "Memory port"),)
    assert serial.present_ports(ports).discovered_ports == ports
    selected_issue = issue()
    assert serial.present_issue(selected_issue).issue is selected_issue
    with pytest.raises(ProductRequestError, match="tuple"):
        serial.present_ports(cast(Any, []))
    with pytest.raises(ProductRequestError, match="UserIssue"):
        serial.present_issue(cast(Any, object()))

    simulator = DashboardWizardPresenter()
    with pytest.raises(ProductRequestError, match="Serial source"):
        simulator.present_ports(())
    with pytest.raises(ProductRequestError, match="export"):
        simulator.present_export("result.json")


def test_presenter_rejects_actions_in_wrong_steps_and_payloads() -> None:
    with pytest.raises(ProductRequestError, match="state"):
        DashboardWizardPresenter(cast(Any, object()))

    source = DashboardWizardPresenter()
    with pytest.raises(ProductAppError, match="does not support"):
        source.select_profile("msp430-equipment-health", "1")
    with pytest.raises(ProductRequestError, match="Back"):
        source.back()
    with pytest.raises(ProductRequestError, match="configuration"):
        source.submit_configuration(source.state.draft)
    with pytest.raises(ProductRequestError, match="review"):
        source.present_review(source.state.draft, ("ok",))
    with pytest.raises(ProductRequestError, match="Run"):
        source.begin_run()
    with pytest.raises(ProductRequestError, match="running"):
        source.finish_run(export_available=False)

    test_step = DashboardWizardPresenter()
    test_step.next()
    with pytest.raises(ProductRequestError, match="source"):
        test_step.select_source(ProductSourceMode.CSV_REPLAY)
    with pytest.raises(ProductRequestError, match="profile"):
        test_step.select_profile("afe", "1")

    serial_test = DashboardWizardPresenter()
    serial_test.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    serial_test.next()
    with pytest.raises(ProductAppError, match="does not support"):
        serial_test.select_job(ProductJobType.DC_ANALYSIS)

    configuration = configuration_presenter()
    with pytest.raises(ProductRequestError, match="test"):
        configuration.select_job(ProductJobType.READ)
    with pytest.raises(ProductRequestError, match="draft"):
        configuration.submit_configuration(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="silently"):
        configuration.submit_configuration(
            replace(configuration.state.draft, job_type=ProductJobType.DC_ANALYSIS)
        )
    with pytest.raises(ProductRequestError, match="Next"):
        configuration.next()
    with pytest.raises(ProductRequestError, match="draft"):
        configuration.present_review(cast(Any, object()), ("ok",))
    with pytest.raises(ProductRequestError, match="review_lines"):
        configuration.present_review(configuration.state.draft, ())

    running = reviewed_presenter()
    running.begin_run()
    with pytest.raises(ProductRequestError, match="Back"):
        running.back()
    with pytest.raises(ProductRequestError, match="boolean"):
        running.finish_run(export_available=cast(Any, "yes"))


def test_presenter_rejects_cross_thread_updates() -> None:
    presenter = DashboardWizardPresenter()
    errors: list[BaseException] = []

    def update() -> None:
        try:
            presenter.next()
        except BaseException as error:  # noqa: BLE001 - test captures exact boundary
            errors.append(error)

    thread = Thread(target=update)
    thread.start()
    thread.join(2.0)
    assert len(errors) == 1
    assert isinstance(errors[0], ProductRequestError)
    assert "creating UI thread" in str(errors[0])
