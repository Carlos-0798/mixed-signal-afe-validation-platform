"""Directional, provenance-aware Schmitt hysteresis analysis."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from statistics import fmean
from typing import cast

from analog_validation.domain import (
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import ValidationError

from .common import (
    DEFAULT_ANALYSIS_QUALITY_POLICY,
    AnalysisQualityPolicy,
    AnalysisRecordReference,
    MeasurementBatch,
    MeasurementDecision,
    PointDisposition,
    assess_voltage_measurement,
)

HYSTERESIS_ANALYSIS_SCHEMA_VERSION = "hysteresis-analysis.v1"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class SweepDirection(str, Enum):
    """Expected order and transition for one threshold sweep."""

    RISING = "RISING"
    FALLING = "FALLING"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _require_nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer")
    return value


def _require_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class HysteresisAnalysisConfig:
    """Channels, unit, and quality policy for directional analysis."""

    input_channel: str
    state_channel: str
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("input_channel", self.input_channel)
        _require_identifier("state_channel", self.state_channel)
        if self.input_channel == self.state_channel:
            raise ValidationError("input and state channels must be distinct")
        if self.normalized_unit not in _VOLTAGE_UNITS:
            raise ValidationError("normalized_unit must be V or mV")
        if not isinstance(self.quality_policy, AnalysisQualityPolicy):
            raise ValidationError("quality_policy must be an AnalysisQualityPolicy")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class HysteresisCycleInput:
    """One rising/falling acquisition pair kept as immutable source batches."""

    cycle_index: int
    rising: MeasurementBatch
    falling: MeasurementBatch
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonnegative_integer("cycle_index", self.cycle_index)
        if not isinstance(self.rising, MeasurementBatch):
            raise ValidationError("rising must be a MeasurementBatch")
        if not isinstance(self.falling, MeasurementBatch):
            raise ValidationError("falling must be a MeasurementBatch")
        if self.rising.evidence_source is not self.falling.evidence_source:
            raise ValidationError("rising and falling batches must use one source")
        ids = self.rising.record_ids + self.falling.record_ids
        if len(ids) != len(set(ids)):
            raise ValidationError("cycle record IDs must be unique")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )

    @property
    def evidence_source(self) -> EvidenceSource:
        return self.rising.evidence_source


@dataclass(frozen=True, slots=True)
class HysteresisPointResult:
    """One analog input and digital-state observation with exact lineage."""

    sequence: int
    direction: SweepDirection
    input_decision: MeasurementDecision
    state_reference: AnalysisRecordReference
    state_value: int | None
    state_status: MeasurementStatus
    state_quality_flags: frozenset[QualityFlag]
    included: bool
    exclusion_reasons: tuple[str, ...] = ()
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonnegative_integer("sequence", self.sequence)
        if not isinstance(self.direction, SweepDirection):
            raise ValidationError("direction must be a SweepDirection")
        if not isinstance(self.input_decision, MeasurementDecision):
            raise ValidationError("input_decision must be a MeasurementDecision")
        if not isinstance(self.state_reference, AnalysisRecordReference):
            raise ValidationError("state_reference must be an AnalysisRecordReference")
        if self.state_value is not None and self.state_value not in {0, 1}:
            raise ValidationError("state_value must be zero, one, or missing")
        if not isinstance(self.state_status, MeasurementStatus):
            raise ValidationError("state_status must be a MeasurementStatus")
        flags = frozenset(self.state_quality_flags)
        if not all(isinstance(flag, QualityFlag) for flag in flags):
            raise ValidationError("state_quality_flags contains an unknown flag")
        object.__setattr__(self, "state_quality_flags", flags)
        if not isinstance(self.included, bool):
            raise ValidationError("included must be a bool")
        reasons = tuple(self.exclusion_reasons)
        if not all(isinstance(value, str) and value for value in reasons):
            raise ValidationError("exclusion_reasons must contain strings")
        if len(reasons) != len(set(reasons)):
            raise ValidationError("exclusion_reasons cannot contain duplicates")
        object.__setattr__(self, "exclusion_reasons", reasons)
        expected = (
            self.input_decision.disposition is PointDisposition.INCLUDED
            and self.state_status is MeasurementStatus.VALID
            and not flags
            and self.state_value is not None
        )
        if self.included is not expected:
            raise ValidationError("included must agree with input and state quality")
        if self.included == bool(reasons):
            raise ValidationError(
                "excluded points require reasons; included points forbid them"
            )
        if self.input_decision.reference.source is not self.state_reference.source:
            raise ValidationError("point records must use one evidence source")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class HysteresisTransition:
    """One adjacent state change estimated at the input-interval midpoint."""

    direction: SweepDirection
    before_input_reference: AnalysisRecordReference
    before_state_reference: AnalysisRecordReference
    after_input_reference: AnalysisRecordReference
    after_state_reference: AnalysisRecordReference
    before_state: int
    after_state: int
    interval_start: float
    interval_end: float
    threshold: float
    unit: MeasurementUnit
    method: str = "adjacent-input-interval-midpoint"
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.direction, SweepDirection):
            raise ValidationError("direction must be a SweepDirection")
        references = (
            self.before_input_reference,
            self.before_state_reference,
            self.after_input_reference,
            self.after_state_reference,
        )
        if not all(isinstance(value, AnalysisRecordReference) for value in references):
            raise ValidationError("transition references must be record references")
        if len({value.source for value in references}) != 1:
            raise ValidationError("transition records must use one evidence source")
        expected_states = (0, 1) if self.direction is SweepDirection.RISING else (1, 0)
        if (self.before_state, self.after_state) != expected_states:
            raise ValidationError("transition states do not match direction")
        start = _require_finite("interval_start", self.interval_start)
        end = _require_finite("interval_end", self.interval_end)
        threshold = _require_finite("threshold", self.threshold)
        expected_threshold = (start + end) / 2.0
        if threshold != expected_threshold:
            raise ValidationError("threshold must equal the interval midpoint")
        if self.direction is SweepDirection.RISING and start > end:
            raise ValidationError("rising transition interval must not decrease")
        if self.direction is SweepDirection.FALLING and start < end:
            raise ValidationError("falling transition interval must not increase")
        if self.unit not in _VOLTAGE_UNITS:
            raise ValidationError("transition unit must be V or mV")
        if self.method != "adjacent-input-interval-midpoint":
            raise ValidationError("unsupported transition estimation method")
        object.__setattr__(self, "interval_start", start)
        object.__setattr__(self, "interval_end", end)
        object.__setattr__(self, "threshold", threshold)
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class HysteresisCycleResult:
    """Directional points, transition evidence, and thresholds for one cycle."""

    cycle_index: int
    rising_points: tuple[HysteresisPointResult, ...]
    falling_points: tuple[HysteresisPointResult, ...]
    rising_transition: HysteresisTransition | None = None
    falling_transition: HysteresisTransition | None = None
    high_threshold: float | None = None
    low_threshold: float | None = None
    width: float | None = None
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonnegative_integer("cycle_index", self.cycle_index)
        for name in ("rising_points", "falling_points"):
            values = tuple(getattr(self, name))
            if not values or not all(
                isinstance(value, HysteresisPointResult) for value in values
            ):
                raise ValidationError(f"{name} must contain hysteresis points")
            object.__setattr__(self, name, values)
        if any(
            point.direction is not SweepDirection.RISING for point in self.rising_points
        ):
            raise ValidationError("rising_points must use RISING direction")
        if any(
            point.direction is not SweepDirection.FALLING
            for point in self.falling_points
        ):
            raise ValidationError("falling_points must use FALLING direction")
        missing = tuple(self.missing_requirements)
        if len(missing) != len(set(missing)) or not all(
            isinstance(value, str) and value for value in missing
        ):
            raise ValidationError("missing_requirements must contain unique strings")
        object.__setattr__(self, "missing_requirements", missing)
        if self.unit not in _VOLTAGE_UNITS:
            raise ValidationError("cycle unit must be V or mV")
        values = (self.high_threshold, self.low_threshold, self.width)
        complete_values = all(value is not None for value in values)
        if complete_values != (not missing):
            raise ValidationError("cycle values and missing requirements must agree")
        if complete_values:
            if not isinstance(
                self.rising_transition, HysteresisTransition
            ) or not isinstance(self.falling_transition, HysteresisTransition):
                raise ValidationError("complete cycle requires both transitions")
            high, low, width = cast(tuple[float, float, float], values)
            high = _require_finite("high_threshold", high)
            low = _require_finite("low_threshold", low)
            width = _require_finite("width", width)
            if high < low:
                raise ValidationError("high threshold is below low threshold")
            if width != high - low:
                raise ValidationError(
                    "width must equal high threshold minus low threshold"
                )
            if (
                self.rising_transition.threshold != high
                or self.falling_transition.threshold != low
            ):
                raise ValidationError("cycle values must match transition thresholds")
        elif (
            any(value is not None for value in values)
            or self.rising_transition is not None
            or self.falling_transition is not None
        ):
            raise ValidationError("incomplete cycle cannot publish partial thresholds")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )

    @property
    def is_complete(self) -> bool:
        return not self.missing_requirements


@dataclass(frozen=True, slots=True)
class HysteresisSummary:
    """Across-cycle threshold and width statistics."""

    cycle_count: int
    mean_high_threshold: float
    mean_low_threshold: float
    mean_width: float
    minimum_width: float
    maximum_width: float
    unit: MeasurementUnit
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle_count, bool)
            or not isinstance(self.cycle_count, int)
            or self.cycle_count < 1
        ):
            raise ValidationError("cycle_count must be a positive integer")
        for name in (
            "mean_high_threshold",
            "mean_low_threshold",
            "mean_width",
            "minimum_width",
            "maximum_width",
        ):
            object.__setattr__(self, name, _require_finite(name, getattr(self, name)))
        if self.mean_high_threshold < self.mean_low_threshold:
            raise ValidationError("mean high threshold is below mean low threshold")
        if self.minimum_width < 0 or self.minimum_width > self.maximum_width:
            raise ValidationError("summary width bounds are invalid")
        if not self.minimum_width <= self.mean_width <= self.maximum_width:
            raise ValidationError("mean width must be inside width bounds")
        if self.unit not in _VOLTAGE_UNITS:
            raise ValidationError("summary unit must be V or mV")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )

    @property
    def width_span(self) -> float:
        return self.maximum_width - self.minimum_width


@dataclass(frozen=True, slots=True)
class HysteresisAnalysisResult:
    """Every directional decision plus an optional complete summary."""

    config: HysteresisAnalysisConfig
    evidence_source: EvidenceSource
    cycles: tuple[HysteresisCycleResult, ...]
    summary: HysteresisSummary | None = None
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = HYSTERESIS_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.config, HysteresisAnalysisConfig):
            raise ValidationError("config must be a HysteresisAnalysisConfig")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        cycles = tuple(self.cycles)
        if not cycles or not all(
            isinstance(value, HysteresisCycleResult) for value in cycles
        ):
            raise ValidationError("cycles must contain HysteresisCycleResult values")
        if tuple(value.cycle_index for value in cycles) != tuple(range(len(cycles))):
            raise ValidationError("cycle indexes must be contiguous from zero")
        object.__setattr__(self, "cycles", cycles)
        if any(
            point.input_decision.reference.source is not self.evidence_source
            for cycle in cycles
            for point in cycle.rising_points + cycle.falling_points
        ):
            raise ValidationError("all cycle records must match evidence_source")
        missing = tuple(self.missing_requirements)
        if len(missing) != len(set(missing)) or not all(
            isinstance(value, str) and value for value in missing
        ):
            raise ValidationError("missing_requirements must contain unique strings")
        object.__setattr__(self, "missing_requirements", missing)
        if self.summary is None:
            if not missing:
                raise ValidationError(
                    "analysis without a summary must identify missing requirements"
                )
        else:
            if not isinstance(self.summary, HysteresisSummary):
                raise ValidationError("summary must be a HysteresisSummary")
            if missing or any(not cycle.is_complete for cycle in cycles):
                raise ValidationError("complete summary cannot have missing cycles")
            if (
                self.summary.cycle_count != len(cycles)
                or self.summary.unit is not self.config.normalized_unit
            ):
                raise ValidationError("summary must match analysis cycles and unit")
        if self.schema_version != HYSTERESIS_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis analysis schema: {self.schema_version}"
            )

    @property
    def is_complete(self) -> bool:
        return self.summary is not None


def _state_value(
    measurement: object, config: HysteresisAnalysisConfig
) -> tuple[int | None, tuple[str, ...]]:
    from analog_validation.domain import Measurement

    if not isinstance(measurement, Measurement):
        raise ValidationError("state record must be a Measurement")
    if measurement.channel != config.state_channel:
        raise ValidationError("state record channel does not match analysis config")
    if measurement.unit is not MeasurementUnit.BOOLEAN:
        raise ValidationError("state record unit must be bool")
    if (
        measurement.value is not None
        and math.isfinite(measurement.value)
        and measurement.value not in {0.0, 1.0}
    ):
        raise ValidationError("digital state must be zero or one")
    if measurement.status is not MeasurementStatus.VALID:
        return None, (f"state-status:{measurement.status.value}",)
    return int(cast(float, measurement.value)), ()


def _points(
    batch: MeasurementBatch, direction: SweepDirection, config: HysteresisAnalysisConfig
) -> tuple[HysteresisPointResult, ...]:
    if len(batch.measurements) % 2:
        raise ValidationError("direction batch must contain input/state pairs")
    points: list[HysteresisPointResult] = []
    for sequence in range(len(batch.measurements) // 2):
        input_measurement = batch.measurements[sequence * 2]
        state_measurement = batch.measurements[sequence * 2 + 1]
        if input_measurement.channel != config.input_channel:
            raise ValidationError("input record channel does not match analysis config")
        input_decision = assess_voltage_measurement(
            input_measurement,
            config.quality_policy,
            target_unit=config.normalized_unit,
        )
        state, state_reasons = _state_value(state_measurement, config)
        reasons = []
        if input_decision.disposition is not PointDisposition.INCLUDED:
            reasons.append("input-not-included")
        reasons.extend(state_reasons)
        points.append(
            HysteresisPointResult(
                sequence=sequence,
                direction=direction,
                input_decision=input_decision,
                state_reference=AnalysisRecordReference.from_measurement(
                    state_measurement
                ),
                state_value=state,
                state_status=state_measurement.status,
                state_quality_flags=state_measurement.quality_flags,
                included=not reasons,
                exclusion_reasons=tuple(reasons),
            )
        )
    if len(points) < 2:
        raise ValidationError("each direction requires at least two points")
    return tuple(points)


def _transition(
    points: tuple[HysteresisPointResult, ...], direction: SweepDirection
) -> tuple[HysteresisTransition | None, tuple[str, ...]]:
    if any(not point.included for point in points):
        return None, (f"{direction.value.lower()}-usable-points",)
    values = cast(
        tuple[float, ...],
        tuple(point.input_decision.normalized_value for point in points),
    )
    pairs = pairwise(values)
    if direction is SweepDirection.RISING and any(
        left > right for left, right in pairs
    ):
        raise ValidationError("rising input must be monotonically nondecreasing")
    if direction is SweepDirection.FALLING and any(
        left < right for left, right in pairs
    ):
        raise ValidationError("falling input must be monotonically nonincreasing")
    changes = [
        index
        for index in range(1, len(points))
        if points[index - 1].state_value != points[index].state_value
    ]
    if not changes:
        return None, (f"{direction.value.lower()}-transition",)
    if len(changes) != 1:
        raise ValidationError(
            f"{direction.value.lower()} sweep contains chatter or multiple transitions"
        )
    index = changes[0]
    before = points[index - 1]
    after = points[index]
    expected = (0, 1) if direction is SweepDirection.RISING else (1, 0)
    if (before.state_value, after.state_value) != expected:
        raise ValidationError(f"{direction.value.lower()} transition is reversed")
    start = cast(float, before.input_decision.normalized_value)
    end = cast(float, after.input_decision.normalized_value)
    return (
        HysteresisTransition(
            direction=direction,
            before_input_reference=before.input_decision.reference,
            before_state_reference=before.state_reference,
            after_input_reference=after.input_decision.reference,
            after_state_reference=after.state_reference,
            before_state=cast(int, before.state_value),
            after_state=cast(int, after.state_value),
            interval_start=start,
            interval_end=end,
            threshold=(start + end) / 2.0,
            unit=before.input_decision.normalized_unit,
        ),
        (),
    )


def _analyze_cycle(
    cycle: HysteresisCycleInput, config: HysteresisAnalysisConfig
) -> HysteresisCycleResult:
    rising_points = _points(cycle.rising, SweepDirection.RISING, config)
    falling_points = _points(cycle.falling, SweepDirection.FALLING, config)
    rising_transition, rising_missing = _transition(
        rising_points, SweepDirection.RISING
    )
    falling_transition, falling_missing = _transition(
        falling_points, SweepDirection.FALLING
    )
    missing = rising_missing + falling_missing
    if missing:
        return HysteresisCycleResult(
            cycle_index=cycle.cycle_index,
            rising_points=rising_points,
            falling_points=falling_points,
            unit=config.normalized_unit,
            missing_requirements=missing,
        )
    high = cast(HysteresisTransition, rising_transition).threshold
    low = cast(HysteresisTransition, falling_transition).threshold
    if high < low:
        raise ValidationError("high threshold is below low threshold")
    return HysteresisCycleResult(
        cycle_index=cycle.cycle_index,
        rising_points=rising_points,
        falling_points=falling_points,
        rising_transition=rising_transition,
        falling_transition=falling_transition,
        high_threshold=high,
        low_threshold=low,
        width=high - low,
        unit=config.normalized_unit,
    )


def analyze_hysteresis(
    cycles: Iterable[HysteresisCycleInput], config: HysteresisAnalysisConfig
) -> HysteresisAnalysisResult:
    """Analyze ordered cycles without silently producing partial thresholds."""

    if isinstance(cycles, (str, bytes)) or not isinstance(cycles, Iterable):
        raise ValidationError("cycles must be an iterable")
    cycle_inputs = tuple(cycles)
    if not cycle_inputs or not all(
        isinstance(value, HysteresisCycleInput) for value in cycle_inputs
    ):
        raise ValidationError("cycles must contain HysteresisCycleInput values")
    if not isinstance(config, HysteresisAnalysisConfig):
        raise ValidationError("config must be a HysteresisAnalysisConfig")
    if tuple(value.cycle_index for value in cycle_inputs) != tuple(
        range(len(cycle_inputs))
    ):
        raise ValidationError("cycle indexes must be contiguous from zero")
    source = cycle_inputs[0].evidence_source
    if any(value.evidence_source is not source for value in cycle_inputs):
        raise ValidationError("all cycles must use one evidence source")
    all_ids = tuple(
        record_id
        for cycle in cycle_inputs
        for record_id in cycle.rising.record_ids + cycle.falling.record_ids
    )
    if len(all_ids) != len(set(all_ids)):
        raise ValidationError("analysis record IDs must be unique across cycles")
    results = tuple(_analyze_cycle(cycle, config) for cycle in cycle_inputs)
    missing = tuple(
        f"cycle-{cycle.cycle_index}:{requirement}"
        for cycle in results
        for requirement in cycle.missing_requirements
    )
    if missing:
        return HysteresisAnalysisResult(
            config, source, results, missing_requirements=missing
        )
    highs = cast(tuple[float, ...], tuple(cycle.high_threshold for cycle in results))
    lows = cast(tuple[float, ...], tuple(cycle.low_threshold for cycle in results))
    widths = cast(tuple[float, ...], tuple(cycle.width for cycle in results))
    summary = HysteresisSummary(
        cycle_count=len(results),
        mean_high_threshold=fmean(highs),
        mean_low_threshold=fmean(lows),
        mean_width=fmean(widths),
        minimum_width=min(widths),
        maximum_width=max(widths),
        unit=config.normalized_unit,
    )
    return HysteresisAnalysisResult(config, source, results, summary=summary)


__all__ = [
    "HYSTERESIS_ANALYSIS_SCHEMA_VERSION",
    "HysteresisAnalysisConfig",
    "HysteresisAnalysisResult",
    "HysteresisCycleInput",
    "HysteresisCycleResult",
    "HysteresisPointResult",
    "HysteresisSummary",
    "HysteresisTransition",
    "SweepDirection",
    "analyze_hysteresis",
]
