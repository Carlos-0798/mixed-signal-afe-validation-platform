"""Versioned AFE v1 messages and domain mappings."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TypeAlias, cast

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
from analog_validation.errors import (
    CapabilityError,
    ProtocolError,
    UnsupportedProtocolVersion,
    ValidationError,
)

from .framing import decode_frame, encode_frame

AFE_PROFILE_NAME = "afe"
AFE_PROFILE_VERSION = "1"
AFE_NAMESPACE = "AFE"

_HEX4 = re.compile(r"^[0-9A-F]{4}$")
_TOKEN_MIN = 0x21
_TOKEN_MAX = 0x7E


class AfeCommandKind(str, Enum):
    """Supported AFE v1 command meanings."""

    GET_STATUS = "GET_STATUS"
    READ_DIGITAL = "READ_DIGITAL"
    SET_GAIN = "SET_GAIN"
    SET_FILTER = "SET_FILTER"
    SET_STIMULUS_MV = "SET_STIMULUS_MV"
    SET_PWM_PERMILLE = "SET_PWM_PERMILLE"
    RUN_DC_SWEEP = "RUN_DC_SWEEP"
    RUN_HYSTERESIS = "RUN_HYSTERESIS"
    RUN_FREQUENCY_SWEEP = "RUN_FREQUENCY_SWEEP"
    SAVE_CALIBRATION = "SAVE_CALIBRATION"
    SAFE_SHUTDOWN = "SAFE_SHUTDOWN"


class CapabilityChannelKind(str, Enum):
    """Channel classes advertised by AFE v1 capability responses."""

    ADC = "ADC"
    DAC = "DAC"
    PWM = "PWM"
    DIGITAL_INPUT = "DIN"


_COMMAND_BITS = {
    DeviceCommand.READ_MEASUREMENT: 0x0001,
    DeviceCommand.READ_DIGITAL_STATE: 0x0002,
    DeviceCommand.SET_ANALOG_STIMULUS: 0x0004,
    DeviceCommand.SET_PWM_STIMULUS: 0x0008,
    DeviceCommand.RUN_DEVICE_COMMAND: 0x0010,
    DeviceCommand.SAFE_SHUTDOWN: 0x0020,
}
_ALL_COMMAND_BITS = sum(_COMMAND_BITS.values())


def _require_int(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValidationError(f"{name} is outside {minimum}..{maximum}")
    return value


def _require_token(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} must be a non-empty string")
    if any(
        character == "," or not _TOKEN_MIN <= ord(character) <= _TOKEN_MAX
        for character in value
    ):
        raise ValidationError(f"{name} must be one printable ASCII token")
    return value


def _freeze_commands(values: object) -> frozenset[DeviceCommand]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError("supported_commands must be an iterable")
    commands: frozenset[object] = frozenset(values)
    if not all(isinstance(command, DeviceCommand) for command in commands):
        raise ValidationError("supported_commands contains an unknown command")
    return cast(frozenset[DeviceCommand], commands)


@dataclass(frozen=True, slots=True)
class AfeTelemetry:
    """One validated AFE v1 telemetry message."""

    seq: int
    time_ms: int
    channel: int
    input_mv: int
    output_mv: int
    gain_milli: int
    threshold: int
    fault_flags: int

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)
        _require_int("time_ms", self.time_ms, 0, 0xFFFFFFFF)
        _require_int("channel", self.channel, 0, 0xFF)
        _require_int("input_mv", self.input_mv, -0x8000, 0x7FFF)
        _require_int("output_mv", self.output_mv, -0x8000, 0x7FFF)
        _require_int("gain_milli", self.gain_milli, 0, 0xFFFF)
        _require_int("threshold", self.threshold, 0, 1)
        _require_int("fault_flags", self.fault_flags, 0, 0xFFFF)


_CHANNEL_COMMANDS = {
    AfeCommandKind.GET_STATUS,
    AfeCommandKind.READ_DIGITAL,
    AfeCommandKind.SET_GAIN,
    AfeCommandKind.SET_FILTER,
    AfeCommandKind.SET_STIMULUS_MV,
    AfeCommandKind.SET_PWM_PERMILLE,
    AfeCommandKind.RUN_DC_SWEEP,
    AfeCommandKind.RUN_HYSTERESIS,
    AfeCommandKind.RUN_FREQUENCY_SWEEP,
}
_VALUE_RANGES = {
    AfeCommandKind.SET_GAIN: (0, 0xFF),
    AfeCommandKind.SET_FILTER: (0, 0xFF),
    AfeCommandKind.SET_STIMULUS_MV: (-0x8000, 0x7FFF),
    AfeCommandKind.SET_PWM_PERMILLE: (0, 1000),
}
_COMMAND_CAPABILITIES = {
    AfeCommandKind.GET_STATUS: DeviceCommand.READ_MEASUREMENT,
    AfeCommandKind.READ_DIGITAL: DeviceCommand.READ_DIGITAL_STATE,
    AfeCommandKind.SET_GAIN: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.SET_FILTER: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.SET_STIMULUS_MV: DeviceCommand.SET_ANALOG_STIMULUS,
    AfeCommandKind.SET_PWM_PERMILLE: DeviceCommand.SET_PWM_STIMULUS,
    AfeCommandKind.RUN_DC_SWEEP: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.RUN_HYSTERESIS: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.RUN_FREQUENCY_SWEEP: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.SAVE_CALIBRATION: DeviceCommand.RUN_DEVICE_COMMAND,
    AfeCommandKind.SAFE_SHUTDOWN: DeviceCommand.SAFE_SHUTDOWN,
}


@dataclass(frozen=True, slots=True)
class AfeCommand:
    """One validated AFE v1 command."""

    seq: int
    kind: AfeCommandKind
    channel: int | None = None
    value: int | None = None

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)
        if not isinstance(self.kind, AfeCommandKind):
            raise ValidationError("kind must be a supported AfeCommandKind")
        if self.kind in _CHANNEL_COMMANDS:
            _require_int("channel", self.channel, 0, 0xFF)
        elif self.channel is not None:
            raise ValidationError(f"{self.kind.value} does not accept a channel")

        value_range = _VALUE_RANGES.get(self.kind)
        if value_range is not None:
            _require_int("value", self.value, *value_range)
        elif self.value is not None:
            raise ValidationError(f"{self.kind.value} does not accept a value")

    @property
    def required_capability(self) -> DeviceCommand:
        """Return the generic capability required to execute this command."""

        return _COMMAND_CAPABILITIES[self.kind]


@dataclass(frozen=True, slots=True)
class AfeCapabilityRequest:
    """Request all capability records for one response sequence."""

    seq: int

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)


@dataclass(frozen=True, slots=True)
class AfeCapabilityDevice:
    """Capability response header containing device identity and command bits."""

    seq: int
    device_id: str
    supported_commands: frozenset[DeviceCommand] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)
        _require_token("device_id", self.device_id)
        object.__setattr__(
            self, "supported_commands", _freeze_commands(self.supported_commands)
        )


@dataclass(frozen=True, slots=True)
class AfeCapabilityChannel:
    """One capability response entry for one numeric channel index."""

    seq: int
    kind: CapabilityChannelKind
    index: int
    minimum: float | None = None
    maximum: float | None = None
    unit: MeasurementUnit | None = None

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)
        _require_int("index", self.index, 0, 0xFF)
        if not isinstance(self.kind, CapabilityChannelKind):
            raise ValidationError("kind must be a supported CapabilityChannelKind")
        if self.kind is CapabilityChannelKind.DIGITAL_INPUT:
            if any(
                value is not None for value in (self.minimum, self.maximum, self.unit)
            ):
                raise ValidationError(
                    "digital input channel cannot declare a numeric range"
                )
            return
        if self.minimum is None or self.maximum is None or self.unit is None:
            raise ValidationError(
                "analog/PWM channel requires minimum, maximum, and unit"
            )
        safe_range = SafeRange(self.minimum, self.maximum, self.unit)
        object.__setattr__(self, "minimum", safe_range.minimum)
        object.__setattr__(self, "maximum", safe_range.maximum)


@dataclass(frozen=True, slots=True)
class AfeCapabilityEnd:
    """Capability response terminator with the advertised entry count."""

    seq: int
    entry_count: int

    def __post_init__(self) -> None:
        _require_int("seq", self.seq, 0, 0xFFFF)
        _require_int("entry_count", self.entry_count, 0, 0xFF)


AfeCapabilityMessage: TypeAlias = (
    AfeCapabilityDevice | AfeCapabilityChannel | AfeCapabilityEnd
)
AfeMessage: TypeAlias = (
    AfeTelemetry | AfeCommand | AfeCapabilityRequest | AfeCapabilityMessage
)


def commands_to_mask(commands: Iterable[DeviceCommand]) -> int:
    """Encode a generic command set as the stable AFE v1 bit mask."""

    frozen = _freeze_commands(commands)
    mask = 0
    for command in frozen:
        mask |= _COMMAND_BITS[command]
    return mask


def commands_from_mask(mask: int) -> frozenset[DeviceCommand]:
    """Decode an AFE v1 command mask and reject unknown bits."""

    try:
        validated = _require_int("command_mask", mask, 0, 0xFFFF)
    except ValidationError as error:
        raise ProtocolError(str(error)) from error
    unknown = validated & ~_ALL_COMMAND_BITS
    if unknown:
        raise ProtocolError(f"unsupported capability command bits: {unknown:04X}")
    return frozenset(
        command for command, bit in _COMMAND_BITS.items() if validated & bit
    )


def _number_token(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return format(value, ".12g")


def _command_fields(message: AfeCommand) -> tuple[object, ...]:
    prefix: tuple[object, ...] = (
        AFE_NAMESPACE,
        AFE_PROFILE_VERSION,
        "CMD",
        message.seq,
    )
    fixed = {
        AfeCommandKind.GET_STATUS: ("GET", "STATUS"),
        AfeCommandKind.READ_DIGITAL: ("READ", "DIGITAL"),
        AfeCommandKind.SET_GAIN: ("SET", "GAIN"),
        AfeCommandKind.SET_FILTER: ("SET", "FILTER"),
        AfeCommandKind.SET_STIMULUS_MV: ("SET", "STIMULUS_MV"),
        AfeCommandKind.SET_PWM_PERMILLE: ("SET", "PWM_PERMILLE"),
        AfeCommandKind.RUN_DC_SWEEP: ("RUN", "DC_SWEEP"),
        AfeCommandKind.RUN_HYSTERESIS: ("RUN", "HYSTERESIS"),
        AfeCommandKind.RUN_FREQUENCY_SWEEP: ("RUN", "FREQUENCY_SWEEP"),
        AfeCommandKind.SAVE_CALIBRATION: ("SAVE", "CALIBRATION"),
        AfeCommandKind.SAFE_SHUTDOWN: ("SAFE", "SHUTDOWN"),
    }[message.kind]
    if message.kind in _VALUE_RANGES:
        return prefix + fixed + (message.channel, message.value)
    if message.kind in _CHANNEL_COMMANDS:
        return prefix + fixed + (message.channel,)
    return prefix + fixed


def encode_afe_message(message: AfeMessage) -> str:
    """Encode one validated AFE v1 message."""

    if isinstance(message, AfeTelemetry):
        fields: tuple[object, ...] = (
            AFE_NAMESPACE,
            AFE_PROFILE_VERSION,
            "TEL",
            message.seq,
            message.time_ms,
            message.channel,
            message.input_mv,
            message.output_mv,
            message.gain_milli,
            message.threshold,
            f"{message.fault_flags:04X}",
        )
    elif isinstance(message, AfeCommand):
        fields = _command_fields(message)
    elif isinstance(message, AfeCapabilityRequest):
        fields = (AFE_NAMESPACE, AFE_PROFILE_VERSION, "CAP_REQ", message.seq)
    elif isinstance(message, AfeCapabilityDevice):
        fields = (
            AFE_NAMESPACE,
            AFE_PROFILE_VERSION,
            "CAP",
            message.seq,
            "DEVICE",
            message.device_id,
            f"{commands_to_mask(message.supported_commands):04X}",
        )
    elif isinstance(message, AfeCapabilityChannel):
        if message.kind is CapabilityChannelKind.DIGITAL_INPUT:
            range_fields: tuple[object, object, object] = ("-", "-", "-")
        else:
            assert message.minimum is not None
            assert message.maximum is not None
            assert message.unit is not None
            range_fields = (
                _number_token(message.minimum),
                _number_token(message.maximum),
                message.unit.value,
            )
        fields = (
            AFE_NAMESPACE,
            AFE_PROFILE_VERSION,
            "CAP",
            message.seq,
            "CHANNEL",
            message.kind.value,
            message.index,
            *range_fields,
        )
    elif isinstance(message, AfeCapabilityEnd):
        fields = (
            AFE_NAMESPACE,
            AFE_PROFILE_VERSION,
            "CAP",
            message.seq,
            "END",
            message.entry_count,
        )
    else:
        raise ProtocolError("unsupported AFE v1 message object")
    return encode_frame(fields)


def _parse_int(value: str, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as error:
        raise ProtocolError(f"{name} is not a valid integer") from error
    try:
        return _require_int(name, parsed, minimum, maximum)
    except ValidationError as error:
        raise ProtocolError(str(error)) from error


def _parse_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ProtocolError(f"{name} is not a valid number") from error
    if not math.isfinite(parsed):
        raise ProtocolError(f"{name} must be finite")
    return parsed


def _parse_unit(value: str) -> MeasurementUnit:
    try:
        return MeasurementUnit(value)
    except ValueError as error:
        raise ProtocolError(f"unsupported measurement unit: {value}") from error


def _parse_command(fields: tuple[str, ...]) -> AfeCommand:
    if len(fields) < 6:
        raise ProtocolError("AFE v1 command is missing fields")
    seq = _parse_int(fields[3], "seq", 0, 0xFFFF)
    tail = fields[4:]
    no_argument = {
        ("SAVE", "CALIBRATION"): AfeCommandKind.SAVE_CALIBRATION,
        ("SAFE", "SHUTDOWN"): AfeCommandKind.SAFE_SHUTDOWN,
    }
    if tail in no_argument:
        return AfeCommand(seq, no_argument[tail])

    one_argument = {
        ("GET", "STATUS"): AfeCommandKind.GET_STATUS,
        ("READ", "DIGITAL"): AfeCommandKind.READ_DIGITAL,
        ("RUN", "DC_SWEEP"): AfeCommandKind.RUN_DC_SWEEP,
        ("RUN", "HYSTERESIS"): AfeCommandKind.RUN_HYSTERESIS,
        ("RUN", "FREQUENCY_SWEEP"): AfeCommandKind.RUN_FREQUENCY_SWEEP,
    }
    if len(tail) == 3 and tail[:2] in one_argument:
        return AfeCommand(
            seq,
            one_argument[tail[:2]],
            channel=_parse_int(tail[2], "channel", 0, 0xFF),
        )

    two_argument = {
        ("SET", "GAIN"): AfeCommandKind.SET_GAIN,
        ("SET", "FILTER"): AfeCommandKind.SET_FILTER,
        ("SET", "STIMULUS_MV"): AfeCommandKind.SET_STIMULUS_MV,
        ("SET", "PWM_PERMILLE"): AfeCommandKind.SET_PWM_PERMILLE,
    }
    if len(tail) == 4 and tail[:2] in two_argument:
        return AfeCommand(
            seq,
            two_argument[tail[:2]],
            channel=_parse_int(tail[2], "channel", 0, 0xFF),
            value=_parse_int(tail[3], "value", *_VALUE_RANGES[two_argument[tail[:2]]]),
        )
    raise ProtocolError("unsupported AFE v1 command shape")


def _parse_capability(fields: tuple[str, ...]) -> AfeCapabilityMessage:
    if len(fields) < 6:
        raise ProtocolError("AFE v1 capability response is missing fields")
    seq = _parse_int(fields[3], "seq", 0, 0xFFFF)
    subtype = fields[4]
    if subtype == "DEVICE" and len(fields) == 7:
        if not _HEX4.fullmatch(fields[6]):
            raise ProtocolError(
                "command mask must be four uppercase hexadecimal digits"
            )
        return AfeCapabilityDevice(
            seq,
            fields[5],
            commands_from_mask(int(fields[6], 16)),
        )
    if subtype == "CHANNEL" and len(fields) == 10:
        try:
            kind = CapabilityChannelKind(fields[5])
        except ValueError as error:
            raise ProtocolError(
                f"unsupported capability channel kind: {fields[5]}"
            ) from error
        index = _parse_int(fields[6], "index", 0, 0xFF)
        if kind is CapabilityChannelKind.DIGITAL_INPUT:
            if fields[7:] != ("-", "-", "-"):
                raise ProtocolError(
                    "digital input capability must use '-' range fields"
                )
            return AfeCapabilityChannel(seq, kind, index)
        try:
            return AfeCapabilityChannel(
                seq,
                kind,
                index,
                _parse_float(fields[7], "minimum"),
                _parse_float(fields[8], "maximum"),
                _parse_unit(fields[9]),
            )
        except ValidationError as error:
            raise ProtocolError(f"invalid capability channel range: {error}") from error
    if subtype == "END" and len(fields) == 6:
        return AfeCapabilityEnd(seq, _parse_int(fields[5], "entry_count", 0, 0xFF))
    raise ProtocolError("unsupported AFE v1 capability response shape")


def parse_afe_message(record: str | bytes) -> AfeMessage:
    """Parse one framed AFE v1 message and reject other profile versions."""

    fields = decode_frame(record).fields
    if fields[1] != AFE_PROFILE_VERSION:
        raise UnsupportedProtocolVersion(
            f"unsupported AFE profile version: {fields[1]}"
        )
    message_type = fields[2]
    if message_type == "TEL":
        if len(fields) != 11:
            raise ProtocolError("AFE v1 telemetry must contain eleven payload fields")
        if not _HEX4.fullmatch(fields[10]):
            raise ProtocolError("fault flags must be four uppercase hexadecimal digits")
        return AfeTelemetry(
            seq=_parse_int(fields[3], "seq", 0, 0xFFFF),
            time_ms=_parse_int(fields[4], "time_ms", 0, 0xFFFFFFFF),
            channel=_parse_int(fields[5], "channel", 0, 0xFF),
            input_mv=_parse_int(fields[6], "input_mv", -0x8000, 0x7FFF),
            output_mv=_parse_int(fields[7], "output_mv", -0x8000, 0x7FFF),
            gain_milli=_parse_int(fields[8], "gain_milli", 0, 0xFFFF),
            threshold=_parse_int(fields[9], "threshold", 0, 1),
            fault_flags=int(fields[10], 16),
        )
    if message_type == "CMD":
        return _parse_command(fields)
    if message_type == "CAP_REQ":
        if len(fields) != 4:
            raise ProtocolError("AFE v1 capability request has unexpected fields")
        return AfeCapabilityRequest(_parse_int(fields[3], "seq", 0, 0xFFFF))
    if message_type == "CAP":
        return _parse_capability(fields)
    raise ProtocolError(f"unsupported AFE v1 message type: {message_type}")


def capabilities_to_messages(
    capabilities: DeviceCapabilities, seq: int
) -> tuple[AfeCapabilityMessage, ...]:
    """Map generic capabilities into a complete AFE v1 response sequence."""

    _require_int("seq", seq, 0, 0xFFFF)
    if capabilities.profile_name != AFE_PROFILE_NAME:
        raise UnsupportedProtocolVersion(
            f"expected profile {AFE_PROFILE_NAME}, got {capabilities.profile_name}"
        )
    if capabilities.profile_version != AFE_PROFILE_VERSION:
        raise UnsupportedProtocolVersion(
            f"unsupported AFE profile version: {capabilities.profile_version}"
        )

    input_ranges = {
        item.channel: item.safe_range for item in capabilities.safe_input_ranges
    }
    output_ranges = {
        item.channel: item.safe_range for item in capabilities.safe_output_ranges
    }
    channels: list[AfeCapabilityChannel] = []
    for kind, names, ranges in (
        (CapabilityChannelKind.ADC, capabilities.adc_channels, input_ranges),
        (CapabilityChannelKind.DAC, capabilities.dac_channels, output_ranges),
        (CapabilityChannelKind.PWM, capabilities.pwm_channels, output_ranges),
    ):
        prefix = kind.value.lower()
        for name in names:
            index = _channel_index(name, prefix)
            safe_range = ranges[name]
            channels.append(
                AfeCapabilityChannel(
                    seq,
                    kind,
                    index,
                    safe_range.minimum,
                    safe_range.maximum,
                    safe_range.unit,
                )
            )
    for name in capabilities.digital_input_channels:
        channels.append(
            AfeCapabilityChannel(
                seq,
                CapabilityChannelKind.DIGITAL_INPUT,
                _channel_index(name, "din"),
            )
        )
    return (
        AfeCapabilityDevice(
            seq, capabilities.device_id, capabilities.supported_commands
        ),
        *channels,
        AfeCapabilityEnd(seq, len(channels)),
    )


def _channel_index(name: str, prefix: str) -> int:
    if not name.startswith(prefix) or not name[len(prefix) :].isdigit():
        raise CapabilityError(
            f"AFE v1 {prefix} channel must use {prefix}<0..255> naming"
        )
    index = int(name[len(prefix) :])
    if not 0 <= index <= 0xFF:
        raise CapabilityError(f"AFE v1 channel index is outside 0..255: {name}")
    return index


def capability_messages_to_domain(
    messages: Iterable[AfeCapabilityMessage],
) -> DeviceCapabilities:
    """Validate and aggregate one AFE v1 capability response sequence."""

    values = tuple(messages)
    if len(values) < 2:
        raise ProtocolError("capability response requires DEVICE and END records")
    if not isinstance(values[0], AfeCapabilityDevice):
        raise ProtocolError("capability response must begin with DEVICE")
    if not isinstance(values[-1], AfeCapabilityEnd):
        raise ProtocolError("capability response must end with END")
    header = cast(AfeCapabilityDevice, values[0])
    end = cast(AfeCapabilityEnd, values[-1])
    channel_values = values[1:-1]
    if not all(isinstance(item, AfeCapabilityChannel) for item in channel_values):
        raise ProtocolError("capability response middle records must be CHANNEL")
    channels = cast(tuple[AfeCapabilityChannel, ...], channel_values)
    if end.seq != header.seq or any(item.seq != header.seq for item in channels):
        raise ProtocolError("capability response sequence numbers do not match")
    if end.entry_count != len(channels):
        raise ProtocolError("capability response entry count does not match")

    adc_channels: list[str] = []
    dac_channels: list[str] = []
    pwm_channels: list[str] = []
    digital_channels: list[str] = []
    input_ranges: list[ChannelRange] = []
    output_ranges: list[ChannelRange] = []
    for item in channels:
        name = f"{item.kind.value.lower()}{item.index}"
        if item.kind is CapabilityChannelKind.DIGITAL_INPUT:
            name = f"din{item.index}"
            digital_channels.append(name)
            continue
        assert item.minimum is not None
        assert item.maximum is not None
        assert item.unit is not None
        channel_range = ChannelRange(
            name, SafeRange(item.minimum, item.maximum, item.unit)
        )
        if item.kind is CapabilityChannelKind.ADC:
            adc_channels.append(name)
            input_ranges.append(channel_range)
        elif item.kind is CapabilityChannelKind.DAC:
            dac_channels.append(name)
            output_ranges.append(channel_range)
        else:
            pwm_channels.append(name)
            output_ranges.append(channel_range)

    try:
        return DeviceCapabilities(
            device_id=header.device_id,
            profile_name=AFE_PROFILE_NAME,
            profile_version=AFE_PROFILE_VERSION,
            adc_channels=tuple(adc_channels),
            dac_channels=tuple(dac_channels),
            pwm_channels=tuple(pwm_channels),
            digital_input_channels=tuple(digital_channels),
            safe_input_ranges=tuple(input_ranges),
            safe_output_ranges=tuple(output_ranges),
            supported_commands=header.supported_commands,
            supports_safe_shutdown=DeviceCommand.SAFE_SHUTDOWN
            in header.supported_commands,
        )
    except ValidationError as error:
        raise ProtocolError(f"invalid capability response: {error}") from error


def validate_command_capability(
    command: AfeCommand, capabilities: DeviceCapabilities
) -> None:
    """Reject unsupported operations separately from unsafe output values."""

    if capabilities.profile_name != AFE_PROFILE_NAME:
        raise UnsupportedProtocolVersion(
            f"expected profile {AFE_PROFILE_NAME}, got {capabilities.profile_name}"
        )
    if capabilities.profile_version != AFE_PROFILE_VERSION:
        raise UnsupportedProtocolVersion(
            f"unsupported AFE profile version: {capabilities.profile_version}"
        )
    capabilities.require_command(command.required_capability)

    if command.kind is AfeCommandKind.SET_STIMULUS_MV:
        assert command.channel is not None and command.value is not None
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            f"dac{command.channel}",
            command.value,
            MeasurementUnit.MILLIVOLT,
        )
    elif command.kind is AfeCommandKind.SET_PWM_PERMILLE:
        assert command.channel is not None and command.value is not None
        capabilities.require_automated_output(
            DeviceCommand.SET_PWM_STIMULUS,
            f"pwm{command.channel}",
            command.value / 1000.0,
            MeasurementUnit.RATIO,
        )
    elif command.kind is AfeCommandKind.READ_DIGITAL:
        assert command.channel is not None
        if f"din{command.channel}" not in capabilities.digital_input_channels:
            raise CapabilityError("digital input channel is not declared")
    elif command.channel is not None:
        if f"adc{command.channel}" not in capabilities.adc_channels:
            raise CapabilityError("AFE input channel is not declared")


def telemetry_to_measurements(
    message: AfeTelemetry,
    *,
    received_at: datetime,
    raw_record_id: str,
    source: EvidenceSource,
) -> tuple[Measurement, ...]:
    """Map one AFE v1 telemetry message to explicit generic measurements."""

    _require_token("raw_record_id", raw_record_id)
    if not isinstance(source, EvidenceSource):
        raise ValidationError("source must be a supported EvidenceSource")
    status = (
        MeasurementStatus.SUSPECT if message.fault_flags else MeasurementStatus.VALID
    )
    flags = (
        frozenset({QualityFlag.DEVICE_FAULT}) if message.fault_flags else frozenset()
    )
    values = (
        ("input_mv", float(message.input_mv), MeasurementUnit.MILLIVOLT),
        ("output_mv", float(message.output_mv), MeasurementUnit.MILLIVOLT),
        ("gain", message.gain_milli / 1000.0, MeasurementUnit.RATIO),
        ("threshold", float(message.threshold), MeasurementUnit.BOOLEAN),
    )
    return tuple(
        Measurement(
            record_id=f"{raw_record_id}:{suffix}",
            raw_record_id=raw_record_id,
            timestamp=received_at,
            channel=f"afe.ch{message.channel}.{suffix}",
            value=value,
            unit=unit,
            status=status,
            source=source,
            quality_flags=flags,
        )
        for suffix, value, unit in values
    )


__all__ = [
    "AFE_NAMESPACE",
    "AFE_PROFILE_NAME",
    "AFE_PROFILE_VERSION",
    "AfeCapabilityChannel",
    "AfeCapabilityDevice",
    "AfeCapabilityEnd",
    "AfeCapabilityMessage",
    "AfeCapabilityRequest",
    "AfeCommand",
    "AfeCommandKind",
    "AfeMessage",
    "AfeTelemetry",
    "CapabilityChannelKind",
    "capabilities_to_messages",
    "capability_messages_to_domain",
    "commands_from_mask",
    "commands_to_mask",
    "encode_afe_message",
    "parse_afe_message",
    "telemetry_to_measurements",
    "validate_command_capability",
]
