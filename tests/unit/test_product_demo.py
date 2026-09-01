"""Deterministic, private-by-default portfolio demo contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from os import PathLike
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import analog_validation_app.demo as demo_module
from analog_validation import EvidenceSource, parse_csv_replay
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import (
    load_result_export_csv,
    load_result_export_json,
    result_export_to_dict,
)
from analog_validation_app import (
    DemoArtifact,
    PortfolioDemoPublication,
    ProductDemoExistsError,
    ProductDemoFormatError,
    ProductDemoPathError,
    publish_portfolio_demo,
)

EXPECTED_ARTIFACTS = {
    "README.md",
    "demo-config.json",
    "examples/replay-dc.csv",
    "examples/replay-faults.csv",
    "manifest.json",
    "report/chart.svg",
    "report/manifest.json",
    "report/report.html",
    "report/report.md",
    "report/report.txt",
    "result.csv",
    "result.json",
}


def _hashes(publication: PortfolioDemoPublication) -> dict[str, str]:
    return {
        artifact.relative_path: artifact.sha256 for artifact in publication.artifacts
    }


def test_demo_runs_the_formal_chain_and_is_byte_identical_in_unicode_paths(
    tmp_path: Path,
) -> None:
    first = publish_portfolio_demo(tmp_path / "first-demo")
    second = publish_portfolio_demo(tmp_path / "演示-β")

    assert first.outcome is RunOutcome.PASS
    assert first.evidence_source is EvidenceSource.SYNTHETIC
    assert first.canonical_result_sha256 == first.artifact("result.json").sha256
    assert _hashes(first) == _hashes(second)
    assert set(_hashes(first)) == EXPECTED_ARTIFACTS
    assert result_export_to_dict(
        load_result_export_json(first.output_directory / "result.json")
    ) == result_export_to_dict(
        load_result_export_csv(first.output_directory / "result.csv")
    )

    manifest = json.loads(
        (first.output_directory / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "portfolio-demo.v1"
    assert manifest["result"] == {
        "canonical_result_sha256": first.canonical_result_sha256,
        "evidence_source": "SYNTHETIC",
        "outcome": "PASS",
    }
    assert manifest["safety_and_privacy"] == {
        "absolute_paths_embedded": False,
        "application_bytes_written": 0,
        "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
        "network_access": "NONE",
        "raw_serial_bytes_embedded": False,
        "serial_ports_opened": 0,
    }
    assert manifest["artifact_count"] == len(EXPECTED_ARTIFACTS) - 1
    assert "manifest.json" not in {
        artifact["relative_path"] for artifact in manifest["artifacts"]
    }


def test_demo_replay_and_fault_examples_are_strict_synthetic_datasets(
    tmp_path: Path,
) -> None:
    publication = publish_portfolio_demo(tmp_path / "demo")
    clean = parse_csv_replay(
        (publication.output_directory / "examples/replay-dc.csv").read_bytes()
    )
    faults = parse_csv_replay(
        (publication.output_directory / "examples/replay-faults.csv").read_bytes()
    )

    assert len(clean.records) == 48
    assert {record.declared_source for record in clean.records} == {
        EvidenceSource.SYNTHETIC
    }
    assert len(faults.records) == 4
    assert {record.declared_source for record in faults.records} == {
        EvidenceSource.SYNTHETIC
    }
    assert {
        flag.value for record in faults.records for flag in record.quality_flags
    } == {
        "COMMUNICATION_ERROR",
        "MISSING",
        "NON_FINITE",
        "SATURATED",
    }


def test_demo_artifacts_do_not_embed_output_path_or_serial_payload(
    tmp_path: Path,
) -> None:
    publication = publish_portfolio_demo(tmp_path / "private-user-path")
    forbidden = (
        str(tmp_path).encode(),
        str(tmp_path).replace("\\", "/").encode(),
        b"TEL,1,",
        b"COM4",
    )

    for artifact in publication.artifacts:
        payload = (
            publication.output_directory / Path(artifact.relative_path)
        ).read_bytes()
        assert all(value not in payload for value in forbidden)
    html = (publication.output_directory / "report/report.html").read_text(
        encoding="utf-8"
    )
    assert "<script" not in html.lower()
    assert "src=" not in html.lower()
    assert 'name="viewport"' in html
    assert "Outcome: PASS" in html
    assert "Evidence source:</strong> SYNTHETIC" in html


def test_demo_is_create_new_and_requires_an_existing_parent(tmp_path: Path) -> None:
    destination = tmp_path / "demo"
    publish_portfolio_demo(destination)

    with pytest.raises(ProductDemoExistsError, match="already exists"):
        publish_portfolio_demo(destination)
    with pytest.raises(ProductDemoPathError, match="parent"):
        publish_portfolio_demo(tmp_path / "missing" / "demo")
    with pytest.raises(ProductDemoPathError, match="identify"):
        publish_portfolio_demo(Path("."))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"relative_path": ""}, "path cannot be empty"),
        ({"relative_path": "../escape"}, "normalized relative"),
        ({"media_type": ""}, "media_type"),
        ({"size_bytes": cast(Any, True)}, "size_bytes"),
        ({"size_bytes": -1}, "size_bytes"),
        ({"sha256": "bad"}, "64 lowercase"),
        ({"sha256": "g" * 64}, "64 lowercase"),
    ],
)
def test_demo_artifact_rejects_invalid_contracts(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "relative_path": "result.json",
        "media_type": "application/json",
        "size_bytes": 1,
        "sha256": "a" * 64,
    }
    values.update(changes)
    with pytest.raises(ProductDemoFormatError, match=message):
        DemoArtifact(**cast(Any, values))


def test_demo_publication_rejects_invalid_contracts(tmp_path: Path) -> None:
    artifact = DemoArtifact("result.json", "application/json", 1, "a" * 64)
    valid = PortfolioDemoPublication(
        tmp_path,
        RunOutcome.PASS,
        EvidenceSource.SYNTHETIC,
        "b" * 64,
        (artifact,),
    )
    assert valid.artifact("result.json") is artifact
    with pytest.raises(ProductDemoFormatError, match="absent"):
        valid.artifact("missing.json")

    base: dict[str, object] = {
        "output_directory": tmp_path,
        "outcome": RunOutcome.PASS,
        "evidence_source": EvidenceSource.SYNTHETIC,
        "canonical_result_sha256": "b" * 64,
        "artifacts": (artifact,),
    }
    invalid_values = (
        ({"output_directory": "path"}, "output_directory"),
        ({"outcome": "PASS"}, "outcome"),
        ({"evidence_source": "SYNTHETIC"}, "evidence_source"),
        ({"canonical_result_sha256": "bad"}, "canonical_result"),
        ({"canonical_result_sha256": "z" * 64}, "canonical_result"),
        ({"artifacts": ()}, "artifacts cannot be empty"),
        ({"artifacts": (object(),)}, "invalid value"),
        ({"artifacts": (artifact, artifact)}, "cannot repeat"),
        ({"schema_version": "future"}, "unsupported"),
    )
    for changes, message in invalid_values:
        values = {**base, **changes}
        with pytest.raises(ProductDemoFormatError, match=message):
            PortfolioDemoPublication(**cast(Any, values))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (True, "1"),
        (False, "0"),
        (7, "7"),
        (1.25, "1.25"),
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
    ],
)
def test_demo_replay_number_format_is_explicit(value: object, expected: str) -> None:
    assert demo_module._number(value) == expected


def test_demo_private_helpers_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ProductDemoFormatError, match="unsupported type"):
        demo_module._number(object())
    with pytest.raises(ProductDemoFormatError, match="media type"):
        demo_module._media_type(Path("unknown.bin"))
    with pytest.raises(ProductDemoPathError, match="string or path-like"):
        demo_module._output_path(cast(Any, 42))

    class BadPath(PathLike[str]):
        def __fspath__(self) -> str:
            raise ValueError("bad path")

    with pytest.raises(ProductDemoPathError, match="path is invalid"):
        demo_module._output_path(BadPath())

    monkeypatch.setattr(
        demo_module,
        "parse_csv_replay",
        lambda _payload: cast(
            Any, type("Wrong", (), {"dataset_id": "other", "records": ()})()
        ),
    )
    with pytest.raises(ProductDemoFormatError, match="round-trip"):
        demo_module._render_replay("expected", ())


def test_demo_staging_helpers_create_new_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "staging"
    path = staging / "nested" / "value.txt"
    demo_module._write_file(path, b"value")
    with pytest.raises(ProductDemoExistsError, match="staging file"):
        demo_module._write_file(path, b"replacement")
    demo_module._cleanup_staging(staging)
    assert not staging.exists()
    demo_module._cleanup_staging(staging)

    monkeypatch.setattr(
        Path,
        "mkdir",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("denied")),
    )
    with pytest.raises(ProductDemoPathError, match="could not be written"):
        demo_module._write_file(tmp_path / "denied/value.txt", b"value")


def test_demo_cleanup_suppresses_only_cleanup_os_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    original = Path.rglob

    def fail_for_staging(path: Path, pattern: str) -> object:
        if path == staging:
            raise OSError("cleanup denied")
        return original(path, pattern)

    monkeypatch.setattr(Path, "rglob", fail_for_staging)
    demo_module._cleanup_staging(staging)
    assert staging.exists()


def test_demo_maps_preflight_and_fixed_workflow_contract_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_exists = Path.exists

    def fail_parent(path: Path) -> bool:
        if path == tmp_path:
            raise OSError("preflight denied")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fail_parent)
    with pytest.raises(ProductDemoPathError, match="cannot be prepared"):
        publish_portfolio_demo(tmp_path / "preflight")
    monkeypatch.undo()

    monkeypatch.setattr(
        demo_module,
        "execute_product_job",
        lambda *_args, **_kwargs: SimpleNamespace(
            worker_state=demo_module.ProductWorkerState.FAILED,
            result=None,
            output=None,
        ),
    )
    with pytest.raises(ProductDemoFormatError, match="reviewed PASS"):
        publish_portfolio_demo(tmp_path / "failed-workflow")


def test_demo_refuses_evidence_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = demo_module.build_human_report_view

    def wrong_evidence(bundle: object) -> object:
        return replace(
            original(cast(Any, bundle)),
            evidence_source=EvidenceSource.HOST_TEST,
        )

    monkeypatch.setattr(demo_module, "build_human_report_view", wrong_evidence)
    with pytest.raises(ProductDemoFormatError, match="must remain SYNTHETIC"):
        publish_portfolio_demo(tmp_path / "wrong-evidence")


def test_demo_propagates_guarded_staging_failure_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_write(_path: Path, _payload: bytes) -> None:
        raise ProductDemoPathError("guarded staging failure")

    monkeypatch.setattr(demo_module, "_write_file", fail_write)
    destination = tmp_path / "guarded-failure"
    with pytest.raises(ProductDemoPathError, match="guarded staging failure"):
        publish_portfolio_demo(destination)

    assert not destination.exists()
    assert not tuple(tmp_path.glob(".guarded-failure.*.tmp"))


@pytest.mark.parametrize(
    ("error", "expected_type", "message"),
    [
        (FileExistsError("race"), ProductDemoExistsError, "already exists"),
        (OSError("rename denied"), ProductDemoPathError, "could not be published"),
    ],
)
def test_demo_maps_atomic_rename_failures_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
    expected_type: type[Exception],
    message: str,
) -> None:
    original_publish = demo_module.publish_human_report

    def publish_then_arm_rename(output_directory: Any, view: Any) -> Any:
        publication = original_publish(output_directory, view)
        monkeypatch.setattr(
            demo_module.os,
            "rename",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )
        return publication

    monkeypatch.setattr(demo_module, "publish_human_report", publish_then_arm_rename)
    destination = tmp_path / "rename-race"
    with pytest.raises(expected_type, match=message):
        publish_portfolio_demo(destination)

    assert not destination.exists()
    assert not tuple(tmp_path.glob(".rename-race.*.tmp"))
