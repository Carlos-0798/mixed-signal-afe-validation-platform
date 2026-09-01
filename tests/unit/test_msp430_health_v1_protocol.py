"""Focused MSP430 Protocol v1 parsing, semantics, and mapping tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import FrameTooLong, FramingError, ProtocolError
from analog_validation.protocol.envelope import encode_crc_envelope
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
    MSP430_HEALTH_CHANNEL_CURRENT,
    MSP430_HEALTH_CHANNEL_FAN_PWM,
    MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
    MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
    MSP430_HEALTH_KNOWN_FAULT_MASK,
    MSP430_HEALTH_MAX_RECORD_BYTES,
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C,
    MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES,
    Msp430Ack,
    Msp430Config,
    Msp430ControlMode,
    Msp430DeviceState,
    Msp430Fault,
    Msp430LogRecord,
    Msp430Message,
    Msp430Status,
    Msp430Telemetry,
    encode_msp430_message,
    msp430_telemetry_to_measurements,
    parse_msp430_ack,
    parse_msp430_config,
    parse_msp430_log,
    parse_msp430_message,
    parse_msp430_status,
    parse_msp430_telemetry,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def telemetry(**changes: Any) -> Msp430Telemetry:
    values: dict[str, Any] = {
        "sequence": 10,
        "uptime_ms": 1000,
        "temperature_ds_deci_c": 421,
        "temperature_ntc_deci_c": 418,
        "bus_mv": 5012,
        "current_ma": 186,
        "power_mw": 932,
        "pwm_permille": 650,
        "state": Msp430DeviceState.COOLING_HIGH,
        "fault_flags": 0,
    }
    values.update(changes)
    return Msp430Telemetry(**values)


def config(**changes: Any) -> Msp430Config:
    values: dict[str, Any] = {
        "request_sequence": 7,
        "storage_sequence": 3,
        "t_low_on_deci_c": 350,
        "t_high_on_deci_c": 420,
        "t_warning_deci_c": 500,
        "t_critical_deci_c": 600,
        "hysteresis_deci_c": 30,
        "pwm_low_permille": 400,
        "pwm_high_permille": 700,
        "start_boost_ms": 750,
        "manual_timeout_s": 300,
        "fan_baseline_ma": 0,
    }
    values.update(changes)
    return Msp430Config(**values)


def messages() -> tuple[Msp430Message, ...]:
    return (
        telemetry(),
        Msp430Ack(1, True),
        Msp430Ack(2, False, "BAD_CRC"),
        Msp430Status(
            3,
            10_000,
            Msp430ControlMode.MANUAL,
            500,
            Msp430DeviceState.WARNING,
            0x0080,
        ),
        config(),
        Msp430LogRecord(4, 2, 17, 9, 255, 0xA5, -32768, -20, 5000),
    )


@pytest.mark.parametrize("message", messages())
def test_every_device_output_type_round_trips(message: Msp430Message) -> None:
    record = encode_msp430_message(message)

    assert record.endswith("\n")
    assert len(record.encode("ascii")) <= MSP430_HEALTH_MAX_RECORD_BYTES
    assert parse_msp430_message(record) == message


def test_public_type_specific_parsers_accept_bytes_crlf_and_lowercase_hex() -> None:
    tel = telemetry(fault_flags=0x00AF)
    tel_record = encode_crc_envelope(
        (
            "TEL", tel.sequence, tel.uptime_ms, tel.temperature_ds_deci_c,
            tel.temperature_ntc_deci_c, tel.bus_mv, tel.current_ma,
            tel.power_mw, tel.pwm_permille, tel.state.value, "00af",
        )
    ).replace("\n", "\r\n")
    body, checksum = tel_record[:-2].rsplit(",", 1)
    lowercase_crc = f"{body},{checksum.lower()}\r\n".encode("ascii")
    ack = Msp430Ack(1, True)
    status = Msp430Status(
        2, 3, Msp430ControlMode.AUTO, 0, Msp430DeviceState.NORMAL, 0
    )
    cfg = config()
    log = Msp430LogRecord(1, 0, 2, 3, 4, 5, 6, 7, 8)

    assert parse_msp430_telemetry(lowercase_crc) == tel
    assert parse_msp430_ack(encode_msp430_message(ack)) == ack
    assert parse_msp430_status(encode_msp430_message(status)) == status
    assert parse_msp430_config(encode_msp430_message(cfg)) == cfg
    assert parse_msp430_log(encode_msp430_message(log)) == log


@pytest.mark.parametrize(
    ("parser", "record", "match"),
    [
        (parse_msp430_telemetry, encode_msp430_message(Msp430Ack(1, True)), "expected TEL"),
        (parse_msp430_ack, encode_msp430_message(telemetry()), "ACK has"),
        (parse_msp430_status, encode_msp430_message(Msp430Ack(1, True)), "expected STS"),
        (parse_msp430_config, encode_msp430_message(Msp430Ack(1, True)), "expected CFG"),
        (parse_msp430_log, encode_msp430_message(Msp430Ack(1, True)), "expected LOG"),
    ],
)
def test_type_specific_parsers_reject_the_wrong_family(parser: Any, record: str, match: str) -> None:
    with pytest.raises(ProtocolError, match=match):
        parser(record)


def test_fault_properties_preserve_known_and_unknown_bits_and_availability() -> None:
    message = telemetry(
        temperature_ds_deci_c=MSP430_HEALTH_TEMPERATURE_UNAVAILABLE_DECI_C,
        temperature_ntc_deci_c=300,
        fault_flags=int(Msp430Fault.DS18B20_MISSING | Msp430Fault.INA219_COMM) | 0x8000,
    )

    assert message.known_faults == (
        Msp430Fault.DS18B20_MISSING | Msp430Fault.INA219_COMM
    )
    assert message.unknown_fault_bits == 0x8000
    assert not message.temperature_ds_available
    assert message.temperature_ntc_available
    assert not message.ina219_available
    assert MSP430_HEALTH_KNOWN_FAULT_MASK == 0x0FFF


def test_normal_telemetry_maps_five_supported_units_and_preserves_raw_power() -> None:
    message = telemetry()

    mapped = msp430_telemetry_to_measurements(
        message,
        received_at=NOW,
        raw_record_id="raw-msp-normal",
        source=EvidenceSource.HOST_TEST,
    )

    assert [item.channel for item in mapped] == [
        MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
        MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
        MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
        MSP430_HEALTH_CHANNEL_CURRENT,
        MSP430_HEALTH_CHANNEL_FAN_PWM,
    ]
    assert [item.value for item in mapped] == [42.1, 41.8, 5012.0, 186.0, 0.65]
    assert [item.unit for item in mapped] == [
        MeasurementUnit.CELSIUS,
        MeasurementUnit.CELSIUS,
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.MILLIAMPERE,
        MeasurementUnit.RATIO,
    ]
    assert all(item.status is MeasurementStatus.VALID for item in mapped)
    assert all(item.source is EvidenceSource.HOST_TEST for item in mapped)
    assert all(item.raw_record_id == "raw-msp-normal" for item in mapped)
    assert message.power_mw == 932
    assert all("power" not in item.channel for item in mapped)


def test_unavailable_sentinels_and_ina_fault_never_become_true_zero() -> None:
    message = telemetry(
        temperature_ds_deci_c=-32768,
        temperature_ntc_deci_c=-32768,
        bus_mv=0,
        current_ma=0,
        power_mw=0,
        pwm_permille=0,
        state=Msp430DeviceState.FAULT,
        fault_flags=0x0015,
    )

    mapped = msp430_telemetry_to_measurements(
        message,
        received_at=NOW,
        raw_record_id="raw-msp-unavailable",
        source=EvidenceSource.HOST_TEST,
    )
    by_channel = {item.channel: item for item in mapped}

    for channel in (
        MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
        MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
        MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
        MSP430_HEALTH_CHANNEL_CURRENT,
    ):
        assert by_channel[channel].value is None
        assert by_channel[channel].status is MeasurementStatus.INVALID
        assert QualityFlag.MISSING in by_channel[channel].quality_flags
    assert QualityFlag.OUT_OF_RANGE in by_channel[
        MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC
    ].quality_flags
    for channel in (MSP430_HEALTH_CHANNEL_BUS_VOLTAGE, MSP430_HEALTH_CHANNEL_CURRENT):
        assert QualityFlag.COMMUNICATION_ERROR in by_channel[channel].quality_flags
        assert QualityFlag.DEVICE_FAULT in by_channel[channel].quality_flags
    assert by_channel[MSP430_HEALTH_CHANNEL_FAN_PWM].value == 0.0
    assert by_channel[MSP430_HEALTH_CHANNEL_FAN_PWM].status is MeasurementStatus.VALID
    assert message.bus_mv == message.current_ma == message.power_mw == 0


def test_crc_fault_makes_ds_unavailable_while_disagreement_marks_ntc_suspect() -> None:
    message = telemetry(
        fault_flags=int(Msp430Fault.DS18B20_CRC | Msp430Fault.SENSOR_DISAGREE)
    )

    ds, ntc, *_ = msp430_telemetry_to_measurements(
        message,
        received_at=NOW,
        raw_record_id="raw-msp-fault",
        source=EvidenceSource.HOST_TEST,
    )

    assert ds.value is None
    assert ds.status is MeasurementStatus.INVALID
    assert ds.quality_flags == frozenset(
        {
            QualityFlag.MISSING,
            QualityFlag.DEVICE_FAULT,
            QualityFlag.COMMUNICATION_ERROR,
        }
    )
    assert ntc.value == 41.8
    assert ntc.status is MeasurementStatus.SUSPECT
    assert ntc.quality_flags == frozenset({QualityFlag.DEVICE_FAULT})


def test_ntc_range_fault_discards_numeric_value_but_retains_it_in_message() -> None:
    message = telemetry(fault_flags=int(Msp430Fault.NTC_RANGE))

    _, ntc, *_ = msp430_telemetry_to_measurements(
        message,
        received_at=NOW,
        raw_record_id="raw-msp-ntc",
        source=EvidenceSource.HOST_TEST,
    )

    assert message.temperature_ntc_deci_c == 418
    assert ntc.value is None
    assert ntc.quality_flags == frozenset(
        {QualityFlag.MISSING, QualityFlag.DEVICE_FAULT, QualityFlag.OUT_OF_RANGE}
    )


def test_zero_electrical_values_without_ina_fault_remain_valid_zero() -> None:
    message = telemetry(bus_mv=0, current_ma=0, power_mw=0)
    mapped = msp430_telemetry_to_measurements(
        message,
        received_at=NOW,
        raw_record_id="raw-msp-zero",
        source=EvidenceSource.HOST_TEST,
    )

    assert mapped[2].value == mapped[3].value == 0.0
    assert mapped[2].status is mapped[3].status is MeasurementStatus.VALID


def test_static_capabilities_are_explicitly_read_only_and_not_hardware_detection() -> None:
    capabilities = MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES

    assert capabilities.device_id == "msp430-equipment-health-v1-contract"
    assert capabilities.profile_name == MSP430_HEALTH_PROFILE_NAME
    assert capabilities.profile_version == MSP430_HEALTH_PROFILE_VERSION
    assert capabilities.is_read_only
    assert not capabilities.supports_safe_shutdown
    assert not capabilities.automated_output_allowed
    assert capabilities.supported_commands == frozenset({DeviceCommand.READ_MEASUREMENT})
    assert capabilities.dac_channels == capabilities.pwm_channels == ()
    assert capabilities.adc_channels == tuple(
        item.channel for item in capabilities.safe_input_ranges
    )
    assert all("power" not in channel for channel in capabilities.adc_channels)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"sequence": True}, "sequence must be an integer"),
        ({"sequence": -1}, "sequence is outside"),
        ({"uptime_ms": 0x1_0000_0000}, "uptime_ms is outside"),
        ({"temperature_ds_deci_c": -0x8001}, "temperature_ds_deci_c is outside"),
        ({"temperature_ntc_deci_c": 0x8000}, "temperature_ntc_deci_c is outside"),
        ({"bus_mv": -1}, "bus_mv is outside"),
        ({"current_ma": 0x8000}, "current_ma is outside"),
        ({"power_mw": -1}, "power_mw is outside"),
        ({"pwm_permille": 1001}, "pwm_permille is outside"),
        ({"state": "NORMAL"}, "state must be"),
        ({"fault_flags": 0x10000}, "fault_flags is outside"),
    ],
)
def test_telemetry_model_rejects_invalid_construction(
    change: dict[str, Any], match: str
) -> None:
    with pytest.raises(ProtocolError, match=match):
        telemetry(**change)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Msp430Ack(-1, True),
        lambda: Msp430Ack(1, cast(Any, 1)),
        lambda: Msp430Ack(1, True, "BAD_CRC"),
        lambda: Msp430Ack(1, False),
        lambda: Msp430Ack(1, False, "bad"),
        lambda: Msp430Status(-1, 0, Msp430ControlMode.AUTO, 0, Msp430DeviceState.NORMAL, 0),
        lambda: Msp430Status(1, 0, cast(Any, "AUTO"), 0, Msp430DeviceState.NORMAL, 0),
        lambda: Msp430Status(1, 0, Msp430ControlMode.AUTO, 1001, Msp430DeviceState.NORMAL, 0),
        lambda: Msp430Status(1, 0, Msp430ControlMode.AUTO, 0, cast(Any, "NORMAL"), 0),
        lambda: Msp430Status(1, 0, Msp430ControlMode.AUTO, 0, Msp430DeviceState.NORMAL, -1),
        lambda: config(hysteresis_deci_c=0),
        lambda: config(pwm_low_permille=1000),
        lambda: config(start_boost_ms=0),
        lambda: Msp430LogRecord(1, 0x10000, 0, 0, 0, 0, 0, 0, 0),
        lambda: Msp430LogRecord(1, 0, 0, 0, 0x100, 0, 0, 0, 0),
    ],
)
def test_other_models_reject_invalid_construction(factory: Any) -> None:
    with pytest.raises(ProtocolError):
        factory()


@pytest.mark.parametrize(
    ("record", "error", "match"),
    [
        (cast(Any, bytearray(b"ACK,42,OK,6996\n")), FramingError, "str or bytes"),
        ("ACK,42,OK,\u6d4b\u8bd5\n", FramingError, "ASCII"),
        ("ACK,42,OK,6996", FramingError, "LF-terminated"),
        ("NO-COMMA\n", FramingError, "no CRC"),
        (b"ACK,42,OK,\xff\n", FramingError, "CRC"),
        ("ACK,42,OK,XYZ1\n", FramingError, "CRC"),
        ("X" * 128 + "\n", FrameTooLong, "128 bytes"),
    ],
)
def test_framing_edges_are_typed(record: Any, error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        parse_msp430_message(record)


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        (("TEL", 1, 2), "TEL requires"),
        (("TEL", "NOPE", 1, 0, 0, 0, 0, 0, 0, "NORMAL", "0000"), "decimal"),
        (("TEL", 1, 1, 0, 0, 0, 0, 0, 0, "UNKNOWN", "0000"), "unknown device"),
        (("STS", 1, 1, "UNKNOWN", 0, "NORMAL", "0000"), "unknown control"),
        (("ACK", 1, "MAYBE"), "ACK result"),
        (("ACK", 1, "ERR", "bad"), "uppercase token"),
        (("CFG", 1, 1), "CFG requires"),
        (("LOG", 1, 1), "LOG requires"),
        (("CMD", 1, "GET", "STATUS"), "unsupported MSP430"),
    ],
)
def test_business_field_rejections_are_typed(fields: tuple[object, ...], match: str) -> None:
    with pytest.raises(ProtocolError, match=match):
        parse_msp430_message(encode_crc_envelope(fields))


def test_mapping_rejects_the_wrong_typed_input_and_encoder_rejects_unknown_object() -> None:
    with pytest.raises(ProtocolError, match="telemetry must"):
        msp430_telemetry_to_measurements(
            cast(Any, object()),
            received_at=NOW,
            raw_record_id="raw-wrong",
            source=EvidenceSource.HOST_TEST,
        )
    with pytest.raises(ProtocolError, match="supported MSP430"):
        encode_msp430_message(cast(Any, object()))


def test_models_are_immutable_and_replace_revalidates() -> None:
    message = telemetry()
    assert replace(message, sequence=11).sequence == 11
    with pytest.raises(ProtocolError):
        replace(message, sequence=-1)
