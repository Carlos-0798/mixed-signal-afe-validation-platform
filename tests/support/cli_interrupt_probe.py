"""Subprocess probe for the installed CLI cooperative-interrupt boundary."""

from __future__ import annotations

import sys
from _thread import interrupt_main
from pathlib import Path
from threading import Event, Thread

import analog_validation_app.cli as cli_module
from analog_validation import EvidenceSource
from analog_validation_app import (
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductResultStatus,
    ProductServiceOutputSlot,
    ProductSourceMode,
    execute_product_job,
)
from analog_validation_app.worker import ProductProgressReporter

READY = Event()


class _BlockingService:
    def __init__(self, marker: Path) -> None:
        self._marker = marker

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        report_progress("Interrupt probe is waiting for cancellation.", 0, 1)
        self._marker.write_text("RUNNING\n", encoding="utf-8")
        READY.set()
        while not cancellation.wait(0.01):
            pass
        cancellation.raise_if_cancelled()
        return ProductJobResult(
            request,
            ProductResultStatus.COMPLETED,
            EvidenceSource.SYNTHETIC,
            ("Unreachable interrupt-probe result; no hardware was accessed.",),
        )

    def cleanup(self) -> None:
        self._marker.with_suffix(".cleaned").write_text("CLEANED\n", encoding="utf-8")


def main() -> int:
    marker = Path(sys.argv[1])
    request = ProductJobRequest(
        "subprocess-interrupt-probe",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )

    def execute(
        _arguments: object, _dependencies: object
    ) -> cli_module.ProductJobExecution:
        slot = ProductServiceOutputSlot()
        return execute_product_job(
            request,
            lambda _request: _BlockingService(marker),
            slot,
        )

    def interrupt_when_running() -> None:
        if READY.wait(5.0):
            interrupt_main()

    Thread(target=interrupt_when_running, daemon=True).start()
    cli_module._execute_workflow = execute  # type: ignore[assignment]
    return cli_module.main(["simulate", "read", "--json"])


if __name__ == "__main__":
    raise SystemExit(main())
