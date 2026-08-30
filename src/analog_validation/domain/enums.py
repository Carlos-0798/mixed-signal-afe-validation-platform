"""Stable enum values used by measurement schemas and reports."""

from __future__ import annotations

from enum import Enum


class EvidenceSource(str, Enum):
    """Origin and evidence class of a record."""

    THEORY = "THEORY"
    SYNTHETIC = "SYNTHETIC"
    CSV_REPLAY = "CSV_REPLAY"
    SPICE_IDEAL = "SPICE_IDEAL"
    SPICE_MODEL = "SPICE_MODEL"
    HOST_TEST = "HOST_TEST"
    BENCH_DMM = "BENCH_DMM"
    BENCH_CONTROLLER = "BENCH_CONTROLLER"
    BENCH_SCOPE = "BENCH_SCOPE"

    @property
    def is_bench_evidence(self) -> bool:
        """Return whether this source can represent physical bench evidence."""

        return self.value.startswith("BENCH_")


class QualityFlag(str, Enum):
    """A specific condition affecting measurement usability."""

    MISSING = "MISSING"
    NON_FINITE = "NON_FINITE"
    SATURATED = "SATURATED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    TIME_ANOMALY = "TIME_ANOMALY"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"


class MeasurementStatus(str, Enum):
    """Overall usability state of a measurement."""

    VALID = "VALID"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"


class MeasurementUnit(str, Enum):
    """Supported public units with stable serialization values."""

    VOLT = "V"
    MILLIVOLT = "mV"
    AMPERE = "A"
    MILLIAMPERE = "mA"
    OHM = "ohm"
    HERTZ = "Hz"
    CELSIUS = "degC"
    ADC_COUNT = "count"
    RATIO = "ratio"
    DECIBEL = "dB"
    BOOLEAN = "bool"
    UNITLESS = "unitless"


__all__ = [
    "EvidenceSource",
    "MeasurementStatus",
    "MeasurementUnit",
    "QualityFlag",
]
