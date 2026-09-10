"""Import file chooser and app navigation/unsaved-work boundaries."""

from __future__ import annotations

from typing import Any

import pytest

from analog_validation_app import ProductRequestError
from analog_validation_app.dashboard import app as app_module
from tests.unit.test_dashboard_product_actions import _launch_callbacks


@pytest.mark.parametrize("mode", ["source", "load_mapping", "save_mapping", "output"])
def test_import_chooser_is_explicit_and_can_cancel(mode: str) -> None:
    calls: list[dict[str, Any]] = []

    def choose(**options: Any) -> str:
        calls.append(options)
        return "new-path"

    assert app_module._choose_import_path(object(), mode, dialog=choose) == "new-path"
    options = calls[0]
    if mode in {"save_mapping", "output"}:
        assert options["confirmoverwrite"] is False
        assert options["defaultextension"] == (".json" if mode == "save_mapping" else "")
    else:
        assert "filetypes" in options
    assert app_module._choose_import_path(object(), mode, dialog=lambda **_: "") == ""


def test_import_chooser_rejects_unknown_mode_and_nonstring_response() -> None:
    with pytest.raises(ProductRequestError, match="Unknown import"):
        app_module._choose_import_path(object(), "invalid")
    with pytest.raises(ProductRequestError, match="path string"):
        app_module._choose_import_path(object(), "source", dialog=lambda **_: None)  # type: ignore[arg-type,return-value]


@pytest.mark.parametrize("answer", [True, False])
def test_import_discard_confirmation_defaults_to_preserve_work(answer: bool) -> None:
    calls: list[dict[str, Any]] = []

    def confirm(**options: Any) -> bool:
        calls.append(options)
        return answer

    assert app_module._confirm_discard_import(object(), dialog=confirm) is answer
    assert calls[0]["default"] == "no"
    assert "original input file stays unchanged" in calls[0]["detail"]


def test_import_discard_requires_boolean() -> None:
    with pytest.raises(ProductRequestError, match="return a bool"):
        app_module._confirm_discard_import(object(), dialog=lambda **_: "yes")  # type: ignore[arg-type,return-value]


def test_import_app_wires_picker_busy_guard_and_close_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choices: list[str] = []
    answers = iter((False, True))
    monkeypatch.setattr(app_module, "_confirm_discard_import", lambda _: next(answers))

    def choose(_root: Any, mode: str) -> str:
        choices.append(mode)
        return "chosen-file"

    monkeypatch.setattr(app_module, "_choose_import_path", choose)

    def exercise(captured: Any) -> None:
        callbacks = captured.import_callbacks
        assert callbacks["on_load_setup"] is captured.load_setup
        assert callbacks["choose_path"]("source") == "chosen-file"
        assert choices == ["source"]
        assert not callbacks["is_busy"]()
        captured.workspace._thread = object()
        assert callbacks["is_busy"]()
        captured.workspace._thread = None
        captured.import_page.has_unsaved_work = True
        captured.root.protocols["WM_DELETE_WINDOW"]()
        assert not captured.root.destroyed
        captured.root.protocols["WM_DELETE_WINDOW"]()
        assert captured.root.destroyed

    _launch_callbacks(monkeypatch, exercise)
