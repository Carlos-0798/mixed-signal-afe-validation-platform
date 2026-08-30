"""Tests for the versioned, controller-neutral AFE v1 profile."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    CapabilityError,
    ChannelRange,
    ConfigurationError,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    SafeRange,
    UnsupportedProtocolVersion,
    ValidationError,
)
from analog_validation.errors import ProtocolError
from analog_validation.protocol import (
    AFE_NAMESPACE,
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeCapabilityMessage,
    AfeCapabilityRequest,
    AfeCommand,
    AfeCommandKind,
    AfeTelemetry,
    CapabilityChannelKind,
    capabilities_to_messages,
    capability_messages_to_domain,
    commands_from_mask,
    commands_to_mask,
    encode_afe_message,
    encode_frame,
    parse_afe_message,
    telemetry_to_measurements,
    validate_command_capability,
)


def make_telemetry(**changes: Any) -> AfeTelemetry:
    values: dict[str, Any] = {
        "seq": 120,
        "time_ms": 45120,
        "channel": 0,
        "input_mv": 500,
        "output_mv": 2487,
        "gain_milli": 4974,
        "threshold": 1,
        "fault_flags": 0,
    }
    values.update(changes)
    return AfeTelemetry(**values)


def make_capabilities(**changes: Any) -> DeviceCapabilities:
    values: dict[str, Any] = {
        "device_id": "simulator-001",
        "profile_name": AFE_PROFILE_NAME,
        "profile_version": AFE_PROFILE_VERSION,
        "adc_channels": ("adc0",),
        "dac_channels": ("dac0",),
        "pwm_channels": ("pwm0",),
        "digital_input_channels": ("din0",),
        "safe_input_ranges": (
            ChannelRange("adc0", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)),
        ),
        "safe_output_ranges": (
            ChannelRange("dac0", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)),
            ChannelRange("pwm0", SafeRange(0, 1, MeasurementUnit.RATIO)),
        ),
        "supported_commands": frozenset(DeviceCommand),
        "supports_safe_shutdown": True,
    }
    values.update(changes)
    return DeviceCapabilities(**values)


def frame(*fields: object) -> str:
    return encode_frame((AFE_NAMESPACE, *fields))


def test_profile_constants_and_enum_values_are_stable() -> None:
    assert (AFE_NAMESPACE, AFE_PROFILE_NAME, AFE_PROFILE_VERSION) == (
        "AFE",
        "afe",
        "1",
    )
    assert [kind.value for kind in CapabilityChannelKind] == [
        "ADC",
        "DAC",
        "PWM",
        "DIN",
    ]
    assert [kind.value for kind in AfeCommandKind] == [
        "GET_STATUS",
        "READ_DIGITAL",
        "SET_GAIN",
        "SET_FILTER",
        "SET_STIMULUS_MV",
        "SET_PWM_PERMILLE",
        "RUN_DC_SWEEP",
        "RUN_HYSTERESIS",
        "RUN_FREQUENCY_SWEEP",
        "SAVE_CALIBRATION",
        "SAFE_SHUTDOWN",
    ]
    assert QualityFlag.DEVICE_FAULT.value == "DEVICE_FAULT"


def test_telemetry_round_trip_has_explicit_profile_version() -> None:
    telemetry = make_telemetry()
    record = encode_afe_message(telemetry)

    assert record.startswith("AFE,1,TEL,")
    assert parse_afe_message(record) == telemetry
    assert parse_afe_message(record.encode("ascii")) == telemetry


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seq", True),
        ("seq", -1),
        ("time_ms", 0x100000000),
        ("channel", 0x100),
        ("input_mv", -0x8001),
        ("output_mv", 0x8000),
        ("gain_milli", 0x10000),
        ("threshold", 2),
        ("fault_flags", 0x10000),
    ],
)
def test_telemetry_model_rejects_wrong_types_and_ranges(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError, match=field):
        make_telemetry(**{field: value})


def test_parser_rejects_other_version_unknown_type_and_bad_telemetry() -> None:
    with pytest.raises(UnsupportedProtocolVersion, match="version"):
        parse_afe_message(frame("2", "TEL", 1))
    with pytest.raises(ProtocolError, match="message type"):
        parse_afe_message(frame("1", "UNKNOWN", 1))
    with pytest.raises(ProtocolError, match="eleven"):
        parse_afe_message(frame("1", "TEL", 1))
    with pytest.raises(ProtocolError, match="fault flags"):
        parse_afe_message(
            frame("1", "TEL", 1, 2, 0, 10, 20, 1000, 1, "00ff")
        )
    with pytest.raises(ProtocolError, match="not a valid integer") as invalid:
        parse_afe_message(
            frame("1", "TEL", "seq", 2, 0, 10, 20, 1000, 1, "0000")
        )
    assert isinstance(invalid.value.__cause__, ValueError)
    with pytest.raises(ProtocolError, match="outside") as outside:
        parse_afe_message(
            frame("1", "TEL", 1, 2, 0, 10, 20, 1000, 2, "0000")
        )
    assert isinstance(outside.value.__cause__, ValidationError)


COMMAND_CASES = [
    (
        AfeCommand(1, AfeCommandKind.GET_STATUS, 0),
        DeviceCommand.READ_MEASUREMENT,
    ),
    (
        AfeCommand(2, AfeCommandKind.READ_DIGITAL, 0),
        DeviceCommand.READ_DIGITAL_STATE,
    ),
    (
        AfeCommand(3, AfeCommandKind.SET_GAIN, 0, 3),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(4, AfeCommandKind.SET_FILTER, 0, 2),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(5, AfeCommandKind.SET_STIMULUS_MV, 0, 1650),
        DeviceCommand.SET_ANALOG_STIMULUS,
    ),
    (
        AfeCommand(6, AfeCommandKind.SET_PWM_PERMILLE, 0, 500),
        DeviceCommand.SET_PWM_STIMULUS,
    ),
    (
        AfeCommand(7, AfeCommandKind.RUN_DC_SWEEP, 0),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(8, AfeCommandKind.RUN_HYSTERESIS, 0),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(9, AfeCommandKind.RUN_FREQUENCY_SWEEP, 0),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(10, AfeCommandKind.SAVE_CALIBRATION),
        DeviceCommand.RUN_DEVICE_COMMAND,
    ),
    (
        AfeCommand(11, AfeCommandKind.SAFE_SHUTDOWN),
        DeviceCommand.SAFE_SHUTDOWN,
    ),
]


@pytest.mark.parametrize(("command", "required"), COMMAND_CASES)
def test_all_command_shapes_round_trip_and_map_to_capability(
    command: AfeCommand, required: DeviceCommand
) -> None:
    record = encode_afe_message(command)

    assert parse_afe_message(record) == command
    assert command.required_capability is required


def test_command_model_rejects_inconsistent_fields() -> None:
    with pytest.raises(ValidationError, match="kind"):
        AfeCommand(1, cast(AfeCommandKind, "GET_STATUS"), 0)
    with pytest.raises(ValidationError, match="channel"):
        AfeCommand(1, AfeCommandKind.GET_STATUS)
    with pytest.raises(ValidationError, match="does not accept a channel"):
        AfeCommand(1, AfeCommandKind.SAFE_SHUTDOWN, 0)
    with pytest.raises(ValidationError, match="value"):
        AfeCommand(1, AfeCommandKind.SET_GAIN, 0)
    with pytest.raises(ValidationError, match="does not accept a value"):
        AfeCommand(1, AfeCommandKind.GET_STATUS, 0, 1)
    with pytest.raises(ValidationError, match="outside"):
        AfeCommand(1, AfeCommandKind.SET_PWM_PERMILLE, 0, 1001)


def test_command_parser_rejects_missing_unsupported_and_invalid_values() -> None:
    with pytest.raises(ProtocolError, match="missing fields"):
        parse_afe_message(frame("1", "CMD", 1, "SAFE"))
    with pytest.raises(ProtocolError, match="unsupported"):
        parse_afe_message(frame("1", "CMD", 1, "ERASE", "ALL"))
    with pytest.raises(ProtocolError, match="channel"):
        parse_afe_message(frame("1", "CMD", 1, "GET", "STATUS", "x"))
    with pytest.raises(ProtocolError, match="outside"):
        parse_afe_message(
            frame("1", "CMD", 1, "SET", "PWM_PERMILLE", 0, 1001)
        )


def test_capability_request_round_trip_and_shape_validation() -> None:
    request = AfeCapabilityRequest(42)

    assert parse_afe_message(encode_afe_message(request)) == request
    with pytest.raises(ValidationError, match="seq"):
        AfeCapabilityRequest(-1)
    with pytest.raises(ProtocolError, match="unexpected"):
        parse_afe_message(frame("1", "CAP_REQ", 1, "EXTRA"))


def test_command_mask_round_trip_and_validation() -> None:
    commands = frozenset(DeviceCommand)

    assert commands_to_mask(commands) == 0x003F
    assert commands_from_mask(0x003F) == commands
    assert commands_from_mask(0) == frozenset()
    with pytest.raises(ValidationError, match="iterable"):
        commands_to_mask(cast(Any, None))
    with pytest.raises(ValidationError, match="unknown"):
        commands_to_mask(cast(Any, {"READ"}))
    with pytest.raises(ProtocolError, match="integer") as wrong_type:
        commands_from_mask(cast(int, True))
    assert isinstance(wrong_type.value.__cause__, ValidationError)
    with pytest.raises(ProtocolError, match="unsupported"):
        commands_from_mask(0x0040)


def test_capability_models_freeze_and_validate_fields() -> None:
    mutable_commands = {DeviceCommand.READ_MEASUREMENT}
    device = AfeCapabilityDevice(1, "sim-1", cast(Any, mutable_commands))
    mutable_commands.clear()

    assert device.supported_commands == frozenset({DeviceCommand.READ_MEASUREMENT})
    assert AfeCapabilityChannel(
        1, CapabilityChannelKind.ADC, 0, 0, 3300, MeasurementUnit.MILLIVOLT
    ).maximum == 3300.0
    assert AfeCapabilityChannel(1, CapabilityChannelKind.DIGITAL_INPUT, 0).unit is None
    assert AfeCapabilityEnd(1, 2).entry_count == 2

    with pytest.raises(ValidationError, match="non-empty"):
        AfeCapabilityDevice(1, "")
    with pytest.raises(ValidationError, match="device_id"):
        AfeCapabilityDevice(1, "bad id")
    with pytest.raises(ValidationError, match="kind"):
        AfeCapabilityChannel(1, cast(CapabilityChannelKind, "GPIO"), 0)
    with pytest.raises(ValidationError, match="cannot declare"):
        AfeCapabilityChannel(
            1,
            CapabilityChannelKind.DIGITAL_INPUT,
            0,
            0,
            1,
            MeasurementUnit.BOOLEAN,
        )
    with pytest.raises(ValidationError, match="requires"):
        AfeCapabilityChannel(1, CapabilityChannelKind.ADC, 0)
    with pytest.raises(ValidationError, match="less than"):
        AfeCapabilityChannel(
            1, CapabilityChannelKind.ADC, 0, 5, 5, MeasurementUnit.VOLT
        )
    with pytest.raises(ValidationError, match="entry_count"):
        AfeCapabilityEnd(1, 256)


def test_each_capability_response_record_round_trips() -> None:
    messages: tuple[AfeCapabilityMessage, ...] = (
        AfeCapabilityDevice(10, "sim-1", frozenset(DeviceCommand)),
        AfeCapabilityChannel(
            10,
            CapabilityChannelKind.ADC,
            0,
            0,
            3.3,
            MeasurementUnit.VOLT,
        ),
        AfeCapabilityChannel(10, CapabilityChannelKind.DIGITAL_INPUT, 0),
        AfeCapabilityEnd(10, 2),
    )

    for message in messages:
        assert parse_afe_message(encode_afe_message(message)) == message


def test_capability_parser_rejects_malformed_records() -> None:
    with pytest.raises(ProtocolError, match="missing fields"):
        parse_afe_message(frame("1", "CAP", 1, "END"))
    with pytest.raises(ProtocolError, match="command mask"):
        parse_afe_message(frame("1", "CAP", 1, "DEVICE", "sim", "003f"))
    with pytest.raises(ProtocolError, match="unsupported capability command bits"):
        parse_afe_message(frame("1", "CAP", 1, "DEVICE", "sim", "0040"))
    with pytest.raises(ProtocolError, match="channel kind"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "GPIO", 0, 0, 1, "V")
        )
    with pytest.raises(ProtocolError, match="must use"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "DIN", 0, 0, 1, "bool")
        )
    with pytest.raises(ProtocolError, match="not a valid number"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "ADC", 0, "low", 1, "V")
        )
    with pytest.raises(ProtocolError, match="finite"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "ADC", 0, 0, "inf", "V")
        )
    with pytest.raises(ProtocolError, match="measurement unit"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "ADC", 0, 0, 1, "volts")
        )
    with pytest.raises(ProtocolError, match="invalid capability channel range"):
        parse_afe_message(
            frame("1", "CAP", 1, "CHANNEL", "ADC", 0, 2, 1, "V")
        )
    with pytest.raises(ProtocolError, match="response shape"):
        parse_afe_message(frame("1", "CAP", 1, "UNKNOWN", 0))


def test_capability_domain_wire_round_trip() -> None:
    capabilities = make_capabilities()
    messages = capabilities_to_messages(capabilities, 77)
    parsed = tuple(parse_afe_message(encode_afe_message(item)) for item in messages)
    typed = cast(tuple[AfeCapabilityMessage, ...], parsed)

    assert isinstance(messages[0], AfeCapabilityDevice)
    assert isinstance(messages[-1], AfeCapabilityEnd)
    assert len(messages) == 6
    assert capability_messages_to_domain(typed) == capabilities


def test_domain_to_profile_mapping_rejects_wrong_profile_and_channel_names() -> None:
    with pytest.raises(UnsupportedProtocolVersion, match="expected profile"):
        capabilities_to_messages(make_capabilities(profile_name="other"), 1)
    with pytest.raises(UnsupportedProtocolVersion, match="version"):
        capabilities_to_messages(make_capabilities(profile_version="2"), 1)
    with pytest.raises(ValidationError, match="seq"):
        capabilities_to_messages(make_capabilities(), -1)

    odd_range = (ChannelRange("analog0", SafeRange(0, 1, MeasurementUnit.VOLT)),)
    with pytest.raises(CapabilityError, match="adc<0..255>"):
        capabilities_to_messages(
            DeviceCapabilities(
                "sim",
                AFE_PROFILE_NAME,
                AFE_PROFILE_VERSION,
                adc_channels=("analog0",),
                safe_input_ranges=odd_range,
            ),
            1,
        )
    high_range = (ChannelRange("adc256", SafeRange(0, 1, MeasurementUnit.VOLT)),)
    with pytest.raises(CapabilityError, match="outside"):
        capabilities_to_messages(
            DeviceCapabilities(
                "sim",
                AFE_PROFILE_NAME,
                AFE_PROFILE_VERSION,
                adc_channels=("adc256",),
                safe_input_ranges=high_range,
            ),
            1,
        )


def test_capability_aggregation_rejects_incomplete_or_inconsistent_sequences() -> None:
    device = AfeCapabilityDevice(1, "sim")
    channel = AfeCapabilityChannel(
        1, CapabilityChannelKind.ADC, 0, 0, 1, MeasurementUnit.VOLT
    )
    end = AfeCapabilityEnd(1, 1)

    with pytest.raises(ProtocolError, match="requires DEVICE and END"):
        capability_messages_to_domain(())
    with pytest.raises(ProtocolError, match="begin with DEVICE"):
        capability_messages_to_domain((channel, end))
    with pytest.raises(ProtocolError, match="end with END"):
        capability_messages_to_domain((device, channel))
    with pytest.raises(ProtocolError, match="middle records"):
        capability_messages_to_domain(
            cast(Any, (device, AfeCapabilityDevice(1, "second"), end))
        )
    with pytest.raises(ProtocolError, match="sequence numbers"):
        capability_messages_to_domain(
            (device, AfeCapabilityChannel(2, CapabilityChannelKind.DIGITAL_INPUT, 0), end)
        )
    with pytest.raises(ProtocolError, match="entry count"):
        capability_messages_to_domain((device, channel, AfeCapabilityEnd(1, 2)))
    with pytest.raises(ProtocolError, match="invalid capability response") as duplicate:
        capability_messages_to_domain((device, channel, channel, AfeCapabilityEnd(1, 2)))
    assert isinstance(duplicate.value.__cause__, ValidationError)


def test_command_capability_validation_accepts_supported_safe_operations() -> None:
    capabilities = make_capabilities()

    for command in [case[0] for case in COMMAND_CASES]:
        validate_command_capability(command, capabilities)


def test_command_capability_validation_distinguishes_support_and_safety() -> None:
    capabilities = make_capabilities()
    with pytest.raises(UnsupportedProtocolVersion, match="expected profile"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.GET_STATUS, 0),
            make_capabilities(profile_name="other"),
        )
    with pytest.raises(UnsupportedProtocolVersion, match="version"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.GET_STATUS, 0),
            make_capabilities(profile_version="2"),
        )

    read_only = DeviceCapabilities(
        "sim",
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        adc_channels=("adc0",),
        safe_input_ranges=(
            ChannelRange("adc0", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)),
        ),
        supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
    )
    with pytest.raises(CapabilityError, match="does not support"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.READ_DIGITAL, 0), read_only
        )
    with pytest.raises(CapabilityError, match="input channel"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.GET_STATUS, 1), capabilities
        )
    with pytest.raises(CapabilityError, match="digital input channel"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.READ_DIGITAL, 1), capabilities
        )
    with pytest.raises(ConfigurationError, match="outside"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.SET_STIMULUS_MV, 0, 3301), capabilities
        )
    with pytest.raises(ConfigurationError, match="outside"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.SET_PWM_PERMILLE, 0, 1000),
            make_capabilities(
                safe_output_ranges=(
                    ChannelRange(
                        "dac0", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)
                    ),
                    ChannelRange("pwm0", SafeRange(0, 0.5, MeasurementUnit.RATIO)),
                )
            ),
        )


def test_output_without_safe_shutdown_is_capability_error() -> None:
    no_shutdown = make_capabilities(
        supported_commands=frozenset(
            {
                DeviceCommand.READ_MEASUREMENT,
                DeviceCommand.SET_ANALOG_STIMULUS,
            }
        ),
        supports_safe_shutdown=False,
    )

    with pytest.raises(CapabilityError, match="SAFE_SHUTDOWN"):
        validate_command_capability(
            AfeCommand(1, AfeCommandKind.SET_STIMULUS_MV, 0, 1000), no_shutdown
        )


def test_telemetry_maps_to_four_explicit_measurements() -> None:
    eastern = timezone(timedelta(hours=-4))
    received = datetime(2026, 8, 29, 8, 0, tzinfo=eastern)
    measurements = telemetry_to_measurements(
        make_telemetry(),
        received_at=received,
        raw_record_id="raw-001",
        source=EvidenceSource.SYNTHETIC,
    )

    assert [item.channel for item in measurements] == [
        "afe.ch0.input_mv",
        "afe.ch0.output_mv",
        "afe.ch0.gain",
        "afe.ch0.threshold",
    ]
    assert [item.value for item in measurements] == [500.0, 2487.0, 4.974, 1.0]
    assert [item.unit for item in measurements] == [
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.RATIO,
        MeasurementUnit.BOOLEAN,
    ]
    assert all(item.status is MeasurementStatus.VALID for item in measurements)
    assert all(item.quality_flags == frozenset() for item in measurements)
    assert all(item.raw_record_id == "raw-001" for item in measurements)
    assert all(item.timestamp.tzinfo is timezone.utc for item in measurements)


def test_faulted_telemetry_is_suspect_not_silently_valid() -> None:
    measurements = telemetry_to_measurements(
        make_telemetry(fault_flags=1),
        received_at=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
        raw_record_id="raw-002",
        source=EvidenceSource.HOST_TEST,
    )

    assert all(item.status is MeasurementStatus.SUSPECT for item in measurements)
    assert all(
        item.quality_flags == frozenset({QualityFlag.DEVICE_FAULT})
        for item in measurements
    )


def test_telemetry_mapping_requires_explicit_valid_provenance() -> None:
    with pytest.raises(ValidationError, match="raw_record_id"):
        telemetry_to_measurements(
            make_telemetry(),
            received_at=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
            raw_record_id="bad id",
            source=EvidenceSource.SYNTHETIC,
        )
    with pytest.raises(ValidationError, match="source"):
        telemetry_to_measurements(
            make_telemetry(),
            received_at=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
            raw_record_id="raw-003",
            source=cast(EvidenceSource, "SYNTHETIC"),
        )
    with pytest.raises(ValidationError, match="timezone"):
        telemetry_to_measurements(
            make_telemetry(),
            received_at=datetime(2026, 8, 29, 12),  # noqa: DTZ001
            raw_record_id="raw-003",
            source=EvidenceSource.SYNTHETIC,
        )


def test_encode_rejects_unknown_message_object() -> None:
    with pytest.raises(ProtocolError, match="message object"):
        encode_afe_message(cast(Any, object()))
