"""Independent read-only interoperability model for MSP430 UART Protocol v1.

The byte contract is derived from the peer project's published ``docs/protocol.md``
at commit ``151fdcfa60661bce1ba04af13c1d3509706f7d4a``.  This module contains no
peer-project runtime code and deliberately provides no command encoder.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntFlag
from typing import TypeAlias

from analog_validation.domain import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    SafeRange,
)
from analog_validation.errors import FrameTooLong, FramingError, ProtocolError

from .envelope import decode_crc_envelope, encode_crc_envelope

MSP430_HEALTH_PROFILE_NAME = "msp430-equipment-health"
MSP430_HEALTH_PROFILE_VERSION = "1"
MSP430_HEALTH_MAX_RECORD_BYTES = 128
MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C = -0x8000
MSP430_HEALTH_INTERFACE_COMMIT = "151fdcfa60661bce1ba04af13c1d3509706f7d4a"

MSP430_HEALTH_CHANNEL_TEMPERATURE_DS = "msp430.health.temperature_ds"
MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC = "msp430.health.temperature_ntc"
MSP430_HEALTH_CHANNEL_BUS_VOLTAGE = "msp430.health.bus_voltage"
MSP430_HEALTH_CHANNEL_CURRENT = "msp430.health.current"
MSP430_HEALTH_CHANNEL_FAN_PWM = "msp430.health.fan_pwm"

_UPPER_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")
_HEX_DIGITS = frozenset(string.hexdigits)


class Msp430DeviceState(str, Enum):
    """Named controller state carried by TEL and STS records."""

    BOOT = "BOOT"
    INIT = "INIT"
    NORMAL = "NORMAL"
    COOLING_LOW = "COOLING_LOW"
    COOLING_HIGH = "COOLING_HIGH"
    WARNING = "WARNING"
    FAULT = "FAULT"


class Msp430ControlMode(str, Enum):
    """Control mode reported by a read-only STS response."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class Msp430Fault(IntFlag):
    """Published Protocol v1 fault bits; unknown bits remain preserved as ints."""

    DS18B20_MISSING = 0x0001
    DS18B20_CRC = 0x0002
    NTC_RANGE = 0x0004
    SENSOR_DISAGREE = 0x0008
    INA219_COMM = 0x0010
    FAN_NO_CURRENT = 0x0020
    FAN_OVERCURRENT = 0x0040
    OVERTEMP_WARNING = 0x0080
    OVERTEMP_CRITICAL = 0x0100
    CONFIG_CRC = 0x0200
    WATCHDOG_RESET = 0x0400
    UART_PROTOCOL = 0x0800


MSP430_HEALTH_KNOWN_FAULT_MASK = sum(fault.value for fault in Msp430Fault)


def _require_int(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ProtocolError(f"{name} is outside [{minimum}, {maximum}]")
    return value


def _require_enum(name: str, value: object, enum_type: type[Enum]) -> None:
    if not isinstance(value, enum_type):
        raise ProtocolError(f"{name} must be a {enum_type.__name__}")


def _require_token(name: str, value: object) -> str:
    if not isinstance(value, str) or _UPPER_TOKEN.fullmatch(value) is None:
        raise ProtocolError(f"{name} must be 1..16 uppercase token characters")
    return value


@dataclass(frozen=True, slots=True)
class Msp430Telemetry:
    """One exact TEL payload, including raw sentinels and fault bits."""

    sequence: int
    uptime_ms: int
    temperature_ds_deci_c: int
    temperature_ntc_deci_c: int
    bus_mv: int
    current_ma: int
    power_mw: int
    pwm_permille: int
    state: Msp430DeviceState
    fault_flags: int

    def __post_init__(self) -> None:
        _require_int("sequence", self.sequence, 0, 0xFFFFFFFF)
        _require_int("uptime_ms", self.uptime_ms, 0, 0xFFFFFFFF)
        _require_int("temperature_ds_deci_c", self.temperature_ds_deci_c, -0x8000, 0x7FFF)
        _require_int("temperature_ntc_deci_c", self.temperature_ntc_deci_c, -0x8000, 0x7FFF)
        _require_int("bus_mv", self.bus_mv, 0, 0xFFFF)
        _require_int("current_ma", self.current_ma, -0x8000, 0x7FFF)
        _require_int("power_mw", self.power_mw, 0, 0xFFFFFFFF)
        _require_int("pwm_permille", self.pwm_permille, 0, 1000)
        _require_enum("state", self.state, Msp430DeviceState)
        _require_int("fault_flags", self.fault_flags, 0, 0xFFFF)

    @property
    def known_faults(self) -> Msp430Fault:
        """Return only currently published bits as an IntFlag value."""

        return Msp430Fault(self.fault_flags & MSP430_HEALTH_KNOWN_FAULT_MASK)

    @property
    def unknown_fault_bits(self) -> int:
        """Return unassigned bits without discarding them from ``fault_flags``."""

        return self.fault_flags & (~MSP430_HEALTH_KNOWN_FAULT_MASK & 0xFFFF)

    @property
    def temperature_ds_available(self) -> bool:
        """Return whether the DS18B20 value is usable under Protocol v1."""

        unavailable_faults = Msp430Fault.DS18B20_MISSING | Msp430Fault.DS18B20_CRC
        return (
            self.temperature_ds_deci_c != MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C
            and not bool(self.known_faults & unavailable_faults)
        )

    @property
    def temperature_ntc_available(self) -> bool:
        """Return whether the NTC value is usable under Protocol v1."""

        return (
            self.temperature_ntc_deci_c != MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C
            and not bool(self.known_faults & Msp430Fault.NTC_RANGE)
        )

    @property
    def ina219_available(self) -> bool:
        """Return whether voltage/current/power fields are available."""

        return not bool(self.known_faults & Msp430Fault.INA219_COMM)


@dataclass(frozen=True, slots=True)
class Msp430Ack:
    """Read-only model of one device acknowledgment."""

    sequence: int
    ok: bool
    error_code: str | None = None

    def __post_init__(self) -> None:
        _require_int("sequence", self.sequence, 0, 0xFFFFFFFF)
        if not isinstance(self.ok, bool):
            raise ProtocolError("ok must be boolean")
        if self.ok:
            if self.error_code is not None:
                raise ProtocolError("OK acknowledgment cannot include an error code")
        elif self.error_code is None:
            raise ProtocolError("ERR acknowledgment requires an error code")
        else:
            _require_token("error_code", self.error_code)


@dataclass(frozen=True, slots=True)
class Msp430Status:
    """Read-only STS response snapshot."""

    request_sequence: int
    uptime_ms: int
    mode: Msp430ControlMode
    manual_pwm_permille: int
    state: Msp430DeviceState
    fault_flags: int

    def __post_init__(self) -> None:
        _require_int("request_sequence", self.request_sequence, 0, 0xFFFFFFFF)
        _require_int("uptime_ms", self.uptime_ms, 0, 0xFFFFFFFF)
        _require_enum("mode", self.mode, Msp430ControlMode)
        _require_int("manual_pwm_permille", self.manual_pwm_permille, 0, 1000)
        _require_enum("state", self.state, Msp430DeviceState)
        _require_int("fault_flags", self.fault_flags, 0, 0xFFFF)


@dataclass(frozen=True, slots=True)
class Msp430Config:
    """Read-only CFG response; no setter or command encoder is provided."""

    request_sequence: int
    storage_sequence: int
    t_low_on_deci_c: int
    t_high_on_deci_c: int
    t_warning_deci_c: int
    t_critical_deci_c: int
    hysteresis_deci_c: int
    pwm_low_permille: int
    pwm_high_permille: int
    start_boost_ms: int
    manual_timeout_s: int
    fan_baseline_ma: int

    def __post_init__(self) -> None:
        _require_int("request_sequence", self.request_sequence, 0, 0xFFFFFFFF)
        _require_int("storage_sequence", self.storage_sequence, 0, 0xFFFFFFFF)
        _require_int("t_low_on_deci_c", self.t_low_on_deci_c, -550, 1250)
        _require_int("t_high_on_deci_c", self.t_high_on_deci_c, -550, 1250)
        _require_int("t_warning_deci_c", self.t_warning_deci_c, -550, 1250)
        _require_int("t_critical_deci_c", self.t_critical_deci_c, -550, 1250)
        _require_int("hysteresis_deci_c", self.hysteresis_deci_c, 1, 1000)
        _require_int("pwm_low_permille", self.pwm_low_permille, 1, 999)
        _require_int("pwm_high_permille", self.pwm_high_permille, 1, 999)
        _require_int("start_boost_ms", self.start_boost_ms, 1, 0xFFFF)
        _require_int("manual_timeout_s", self.manual_timeout_s, 1, 0xFFFF)
        _require_int("fan_baseline_ma", self.fan_baseline_ma, 0, 0x7FFF)


@dataclass(frozen=True, slots=True)
class Msp430LogRecord:
    """Read-only LOG response with its raw numeric state and flag fields."""

    request_sequence: int
    offset: int
    timestamp_s: int
    event_code: int
    state_code: int
    flags: int
    temperature_deci_c: int
    current_ma: int
    bus_mv: int

    def __post_init__(self) -> None:
        _require_int("request_sequence", self.request_sequence, 0, 0xFFFFFFFF)
        _require_int("offset", self.offset, 0, 0xFFFF)
        _require_int("timestamp_s", self.timestamp_s, 0, 0xFFFFFFFF)
        _require_int("event_code", self.event_code, 0, 0xFFFF)
        _require_int("state_code", self.state_code, 0, 0xFF)
        _require_int("flags", self.flags, 0, 0xFF)
        _require_int("temperature_deci_c", self.temperature_deci_c, -0x8000, 0x7FFF)
        _require_int("current_ma", self.current_ma, -0x8000, 0x7FFF)
        _require_int("bus_mv", self.bus_mv, 0, 0xFFFF)


Msp430Message: TypeAlias = (
    Msp430Telemetry | Msp430Ack | Msp430Status | Msp430Config | Msp430LogRecord
)


def _decimal(name: str, token: str, minimum: int, maximum: int) -> int:
    try:
        value = int(token, 10)
    except ValueError as error:
        raise ProtocolError(f"{name} is not a decimal integer") from error
    return _require_int(name, value, minimum, maximum)


def _hex(name: str, token: str, digits: int) -> int:
    if len(token) != digits or any(character not in _HEX_DIGITS for character in token):
        raise ProtocolError(f"{name} must contain exactly {digits} hexadecimal digits")
    return int(token, 16)


def _decode_fields(record: str | bytes) -> tuple[str, ...]:
    if isinstance(record, str):
        try:
            raw = record.encode("ascii")
        except UnicodeEncodeError as error:
            raise FramingError("record must contain ASCII only") from error
    elif isinstance(record, bytes):
        raw = record
    else:
        raise FramingError("record must be str or bytes")

    if len(raw) > MSP430_HEALTH_MAX_RECORD_BYTES:
        raise FrameTooLong(
            f"record exceeds {MSP430_HEALTH_MAX_RECORD_BYTES} bytes"
        )
    if not raw.endswith(b"\n"):
        raise FramingError("MSP430 record must be LF-terminated")

    body = raw[:-1]
    if body.endswith(b"\r"):
        body = body[:-1]
    payload, separator, checksum = body.rpartition(b",")
    if not separator:
        raise FramingError("record has no CRC field")
    try:
        checksum_text = checksum.decode("ascii")
    except UnicodeDecodeError as error:
        raise FramingError("CRC must contain four hexadecimal digits") from error
    if len(checksum_text) != 4 or any(
        character not in _HEX_DIGITS for character in checksum_text
    ):
        raise FramingError("CRC must contain four hexadecimal digits")

    normalized = payload + b"," + checksum.upper() + b"\n"
    return decode_crc_envelope(
        normalized,
        max_record_bytes=MSP430_HEALTH_MAX_RECORD_BYTES,
    ).fields


def _require_kind(fields: tuple[str, ...], kind: str, count: int) -> None:
    if not fields or fields[0] != kind:
        actual = fields[0] if fields else ""
        raise ProtocolError(f"expected {kind} record, received {actual!r}")
    if len(fields) != count:
        raise ProtocolError(
            f"{kind} requires {count} payload fields, received {len(fields)}"
        )


def _device_state(token: str) -> Msp430DeviceState:
    try:
        return Msp430DeviceState(token)
    except ValueError as error:
        raise ProtocolError(f"unknown device state: {token!r}") from error


def _control_mode(token: str) -> Msp430ControlMode:
    try:
        return Msp430ControlMode(token)
    except ValueError as error:
        raise ProtocolError(f"unknown control mode: {token!r}") from error


def _parse_telemetry_fields(fields: tuple[str, ...]) -> Msp430Telemetry:
    _require_kind(fields, "TEL", 11)
    return Msp430Telemetry(
        sequence=_decimal("sequence", fields[1], 0, 0xFFFFFFFF),
        uptime_ms=_decimal("uptime_ms", fields[2], 0, 0xFFFFFFFF),
        temperature_ds_deci_c=_decimal(
            "temperature_ds_deci_c", fields[3], -0x8000, 0x7FFF
        ),
        temperature_ntc_deci_c=_decimal(
            "temperature_ntc_deci_c", fields[4], -0x8000, 0x7FFF
        ),
        bus_mv=_decimal("bus_mv", fields[5], 0, 0xFFFF),
        current_ma=_decimal("current_ma", fields[6], -0x8000, 0x7FFF),
        power_mw=_decimal("power_mw", fields[7], 0, 0xFFFFFFFF),
        pwm_permille=_decimal("pwm_permille", fields[8], 0, 1000),
        state=_device_state(fields[9]),
        fault_flags=_hex("fault_flags", fields[10], 4),
    )


def _parse_ack_fields(fields: tuple[str, ...]) -> Msp430Ack:
    if not fields or fields[0] != "ACK" or len(fields) not in (3, 4):
        raise ProtocolError("ACK has an invalid field count")
    sequence = _decimal("sequence", fields[1], 0, 0xFFFFFFFF)
    if fields[2] == "OK" and len(fields) == 3:
        return Msp430Ack(sequence, True)
    if fields[2] == "ERR" and len(fields) == 4:
        return Msp430Ack(sequence, False, _require_token("error_code", fields[3]))
    raise ProtocolError("ACK result is invalid")


def _parse_status_fields(fields: tuple[str, ...]) -> Msp430Status:
    _require_kind(fields, "STS", 7)
    return Msp430Status(
        request_sequence=_decimal("request_sequence", fields[1], 0, 0xFFFFFFFF),
        uptime_ms=_decimal("uptime_ms", fields[2], 0, 0xFFFFFFFF),
        mode=_control_mode(fields[3]),
        manual_pwm_permille=_decimal("manual_pwm_permille", fields[4], 0, 1000),
        state=_device_state(fields[5]),
        fault_flags=_hex("fault_flags", fields[6], 4),
    )


def _parse_config_fields(fields: tuple[str, ...]) -> Msp430Config:
    _require_kind(fields, "CFG", 13)
    return Msp430Config(
        request_sequence=_decimal("request_sequence", fields[1], 0, 0xFFFFFFFF),
        storage_sequence=_decimal("storage_sequence", fields[2], 0, 0xFFFFFFFF),
        t_low_on_deci_c=_decimal("t_low_on_deci_c", fields[3], -550, 1250),
        t_high_on_deci_c=_decimal("t_high_on_deci_c", fields[4], -550, 1250),
        t_warning_deci_c=_decimal("t_warning_deci_c", fields[5], -550, 1250),
        t_critical_deci_c=_decimal("t_critical_deci_c", fields[6], -550, 1250),
        hysteresis_deci_c=_decimal("hysteresis_deci_c", fields[7], 1, 1000),
        pwm_low_permille=_decimal("pwm_low_permille", fields[8], 1, 999),
        pwm_high_permille=_decimal("pwm_high_permille", fields[9], 1, 999),
        start_boost_ms=_decimal("start_boost_ms", fields[10], 1, 0xFFFF),
        manual_timeout_s=_decimal("manual_timeout_s", fields[11], 1, 0xFFFF),
        fan_baseline_ma=_decimal("fan_baseline_ma", fields[12], 0, 0x7FFF),
    )


def _parse_log_fields(fields: tuple[str, ...]) -> Msp430LogRecord:
    _require_kind(fields, "LOG", 10)
    return Msp430LogRecord(
        request_sequence=_decimal("request_sequence", fields[1], 0, 0xFFFFFFFF),
        offset=_decimal("offset", fields[2], 0, 0xFFFF),
        timestamp_s=_decimal("timestamp_s", fields[3], 0, 0xFFFFFFFF),
        event_code=_decimal("event_code", fields[4], 0, 0xFFFF),
        state_code=_decimal("state_code", fields[5], 0, 0xFF),
        flags=_hex("flags", fields[6], 2),
        temperature_deci_c=_decimal("temperature_deci_c", fields[7], -0x8000, 0x7FFF),
        current_ma=_decimal("current_ma", fields[8], -0x8000, 0x7FFF),
        bus_mv=_decimal("bus_mv", fields[9], 0, 0xFFFF),
    )


def parse_msp430_telemetry(record: str | bytes) -> Msp430Telemetry:
    """Validate one complete Protocol v1 TEL record."""

    return _parse_telemetry_fields(_decode_fields(record))


def parse_msp430_ack(record: str | bytes) -> Msp430Ack:
    """Validate one complete Protocol v1 ACK record."""

    return _parse_ack_fields(_decode_fields(record))


def parse_msp430_status(record: str | bytes) -> Msp430Status:
    """Validate one complete Protocol v1 STS record."""

    return _parse_status_fields(_decode_fields(record))


def parse_msp430_config(record: str | bytes) -> Msp430Config:
    """Validate one complete Protocol v1 CFG record."""

    return _parse_config_fields(_decode_fields(record))


def parse_msp430_log(record: str | bytes) -> Msp430LogRecord:
    """Validate one complete Protocol v1 LOG record."""

    return _parse_log_fields(_decode_fields(record))


def parse_msp430_message(record: str | bytes) -> Msp430Message:
    """Parse one device-emitted record; CMD is intentionally unsupported."""

    fields = _decode_fields(record)
    kind = fields[0] if fields else ""
    if kind == "TEL":
        return _parse_telemetry_fields(fields)
    if kind == "ACK":
        return _parse_ack_fields(fields)
    if kind == "STS":
        return _parse_status_fields(fields)
    if kind == "CFG":
        return _parse_config_fields(fields)
    if kind == "LOG":
        return _parse_log_fields(fields)
    raise ProtocolError(f"unsupported MSP430 device record type: {kind!r}")


def _message_fields(message: Msp430Message) -> tuple[object, ...]:
    if isinstance(message, Msp430Telemetry):
        return (
            "TEL", message.sequence, message.uptime_ms,
            message.temperature_ds_deci_c, message.temperature_ntc_deci_c,
            message.bus_mv, message.current_ma, message.power_mw,
            message.pwm_permille, message.state.value, f"{message.fault_flags:04X}",
        )
    if isinstance(message, Msp430Ack):
        if message.ok:
            return ("ACK", message.sequence, "OK")
        assert message.error_code is not None
        return ("ACK", message.sequence, "ERR", message.error_code)
    if isinstance(message, Msp430Status):
        return (
            "STS", message.request_sequence, message.uptime_ms, message.mode.value,
            message.manual_pwm_permille, message.state.value,
            f"{message.fault_flags:04X}",
        )
    if isinstance(message, Msp430Config):
        return (
            "CFG", message.request_sequence, message.storage_sequence,
            message.t_low_on_deci_c, message.t_high_on_deci_c,
            message.t_warning_deci_c, message.t_critical_deci_c,
            message.hysteresis_deci_c, message.pwm_low_permille,
            message.pwm_high_permille, message.start_boost_ms,
            message.manual_timeout_s, message.fan_baseline_ma,
        )
    if isinstance(message, Msp430LogRecord):
        return (
            "LOG", message.request_sequence, message.offset, message.timestamp_s,
            message.event_code, message.state_code, f"{message.flags:02X}",
            message.temperature_deci_c, message.current_ma, message.bus_mv,
        )
    raise ProtocolError("message must be a supported MSP430 device record")


def encode_msp430_message(message: Msp430Message) -> str:
    """Encode a typed device-output record; command transmission is absent."""

    return encode_crc_envelope(
        _message_fields(message),
        max_record_bytes=MSP430_HEALTH_MAX_RECORD_BYTES,
    )


def _measurement(
    *,
    raw_record_id: str,
    timestamp: datetime,
    channel: str,
    value: float | None,
    unit: MeasurementUnit,
    status: MeasurementStatus,
    source: EvidenceSource,
    flags: frozenset[QualityFlag] = frozenset(),
) -> Measurement:
    suffix = channel.rsplit(".", 1)[-1]
    return Measurement(
        record_id=f"{raw_record_id}-{suffix}",
        raw_record_id=raw_record_id,
        timestamp=timestamp,
        channel=channel,
        value=value,
        unit=unit,
        status=status,
        source=source,
        quality_flags=flags,
    )


def _temperature_measurement(
    *,
    raw_record_id: str,
    timestamp: datetime,
    channel: str,
    raw_deci_c: int,
    available: bool,
    source: EvidenceSource,
    unavailable_flags: frozenset[QualityFlag],
    disagreement: bool,
) -> Measurement:
    if not available:
        return _measurement(
            raw_record_id=raw_record_id,
            timestamp=timestamp,
            channel=channel,
            value=None,
            unit=MeasurementUnit.CELSIUS,
            status=MeasurementStatus.INVALID,
            source=source,
            flags=frozenset({QualityFlag.MISSING, *unavailable_flags}),
        )
    if disagreement:
        return _measurement(
            raw_record_id=raw_record_id,
            timestamp=timestamp,
            channel=channel,
            value=raw_deci_c / 10.0,
            unit=MeasurementUnit.CELSIUS,
            status=MeasurementStatus.SUSPECT,
            source=source,
            flags=frozenset({QualityFlag.DEVICE_FAULT}),
        )
    return _measurement(
        raw_record_id=raw_record_id,
        timestamp=timestamp,
        channel=channel,
        value=raw_deci_c / 10.0,
        unit=MeasurementUnit.CELSIUS,
        status=MeasurementStatus.VALID,
        source=source,
    )


def msp430_telemetry_to_measurements(
    telemetry: Msp430Telemetry,
    *,
    received_at: datetime,
    raw_record_id: str,
    source: EvidenceSource,
) -> tuple[Measurement, ...]:
    """Map usable TEL fields while retaining every raw field in ``telemetry``.

    ``power_mw`` remains available on the typed message but is not mislabeled as
    ``UNITLESS`` because Measurement v1 does not yet define a power unit.
    """

    if not isinstance(telemetry, Msp430Telemetry):
        raise ProtocolError("telemetry must be Msp430Telemetry")
    faults = telemetry.known_faults
    disagreement = bool(faults & Msp430Fault.SENSOR_DISAGREE)

    ds_flags: set[QualityFlag] = set()
    if faults & (Msp430Fault.DS18B20_MISSING | Msp430Fault.DS18B20_CRC):
        ds_flags.add(QualityFlag.DEVICE_FAULT)
    if faults & Msp430Fault.DS18B20_CRC:
        ds_flags.add(QualityFlag.COMMUNICATION_ERROR)

    ntc_flags: set[QualityFlag] = set()
    if faults & Msp430Fault.NTC_RANGE:
        ntc_flags.update({QualityFlag.DEVICE_FAULT, QualityFlag.OUT_OF_RANGE})

    measurements = [
        _temperature_measurement(
            raw_record_id=raw_record_id,
            timestamp=received_at,
            channel=MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
            raw_deci_c=telemetry.temperature_ds_deci_c,
            available=telemetry.temperature_ds_available,
            source=source,
            unavailable_flags=frozenset(ds_flags),
            disagreement=disagreement,
        ),
        _temperature_measurement(
            raw_record_id=raw_record_id,
            timestamp=received_at,
            channel=MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
            raw_deci_c=telemetry.temperature_ntc_deci_c,
            available=telemetry.temperature_ntc_available,
            source=source,
            unavailable_flags=frozenset(ntc_flags),
            disagreement=disagreement,
        ),
    ]

    if telemetry.ina219_available:
        measurements.extend(
            (
                _measurement(
                    raw_record_id=raw_record_id,
                    timestamp=received_at,
                    channel=MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
                    value=telemetry.bus_mv,
                    unit=MeasurementUnit.MILLIVOLT,
                    status=MeasurementStatus.VALID,
                    source=source,
                ),
                _measurement(
                    raw_record_id=raw_record_id,
                    timestamp=received_at,
                    channel=MSP430_HEALTH_CHANNEL_CURRENT,
                    value=telemetry.current_ma,
                    unit=MeasurementUnit.MILLIAMPERE,
                    status=MeasurementStatus.VALID,
                    source=source,
                ),
            )
        )
    else:
        ina_flags = frozenset(
            {
                QualityFlag.MISSING,
                QualityFlag.COMMUNICATION_ERROR,
                QualityFlag.DEVICE_FAULT,
            }
        )
        measurements.extend(
            (
                _measurement(
                    raw_record_id=raw_record_id,
                    timestamp=received_at,
                    channel=MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
                    value=None,
                    unit=MeasurementUnit.MILLIVOLT,
                    status=MeasurementStatus.INVALID,
                    source=source,
                    flags=ina_flags,
                ),
                _measurement(
                    raw_record_id=raw_record_id,
                    timestamp=received_at,
                    channel=MSP430_HEALTH_CHANNEL_CURRENT,
                    value=None,
                    unit=MeasurementUnit.MILLIAMPERE,
                    status=MeasurementStatus.INVALID,
                    source=source,
                    flags=ina_flags,
                ),
            )
        )

    measurements.append(
        _measurement(
            raw_record_id=raw_record_id,
            timestamp=received_at,
            channel=MSP430_HEALTH_CHANNEL_FAN_PWM,
            value=telemetry.pwm_permille / 1000.0,
            unit=MeasurementUnit.RATIO,
            status=MeasurementStatus.VALID,
            source=source,
        )
    )
    return tuple(measurements)


MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES = DeviceCapabilities(
    device_id="msp430-equipment-health-v1-contract",
    profile_name=MSP430_HEALTH_PROFILE_NAME,
    profile_version=MSP430_HEALTH_PROFILE_VERSION,
    adc_channels=(
        MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
        MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
        MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
        MSP430_HEALTH_CHANNEL_CURRENT,
        MSP430_HEALTH_CHANNEL_FAN_PWM,
    ),
    safe_input_ranges=(
        ChannelRange(
            MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
            SafeRange(-3276.7, 3276.7, MeasurementUnit.CELSIUS),
        ),
        ChannelRange(
            MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
            SafeRange(-3276.7, 3276.7, MeasurementUnit.CELSIUS),
        ),
        ChannelRange(
            MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
            SafeRange(0, 0xFFFF, MeasurementUnit.MILLIVOLT),
        ),
        ChannelRange(
            MSP430_HEALTH_CHANNEL_CURRENT,
            SafeRange(-0x8000, 0x7FFF, MeasurementUnit.MILLIAMPERE),
        ),
        ChannelRange(
            MSP430_HEALTH_CHANNEL_FAN_PWM,
            SafeRange(0, 1, MeasurementUnit.RATIO),
        ),
    ),
    supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
    supports_safe_shutdown=False,
)


__all__ = [
    "MSP430_HEALTH_CHANNEL_BUS_VOLTAGE",
    "MSP430_HEALTH_CHANNEL_CURRENT",
    "MSP430_HEALTH_CHANNEL_FAN_PWM",
    "MSP430_HEALTH_CHANNEL_TEMPERATURE_DS",
    "MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC",
    "MSP430_HEALTH_INTERFACE_COMMIT",
    "MSP430_HEALTH_KNOWN_FAULT_MASK",
    "MSP430_HEALTH_MAX_RECORD_BYTES",
    "MSP430_HEALTH_PROFILE_NAME",
    "MSP430_HEALTH_PROFILE_VERSION",
    "MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C",
    "MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES",
    "Msp430Ack",
    "Msp430Config",
    "Msp430ControlMode",
    "Msp430DeviceState",
    "Msp430Fault",
    "Msp430LogRecord",
    "Msp430Message",
    "Msp430Status",
    "Msp430Telemetry",
    "encode_msp430_message",
    "msp430_telemetry_to_measurements",
    "parse_msp430_ack",
    "parse_msp430_config",
    "parse_msp430_log",
    "parse_msp430_message",
    "parse_msp430_status",
    "parse_msp430_telemetry",
]
