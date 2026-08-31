"""Deterministic tests for the optional receive-only pyserial backend."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest

from analog_validation.profiles import MSP430_HEALTH_V1_SERIAL_IDENTITY
from analog_validation.transport import (
    SerialBackendDisconnected,
    SerialConnectionSettings,
    SerialParity,
    SerialPollStatus,
    SerialSession,
    SerialStopBits,
)
from analog_validation_pyserial import (
    PySerialBackend,
    PySerialBackendStateError,
    PySerialUnavailableError,
)


class FakeSerialException(Exception):
    """Injected equivalent of pyserial.SerialException."""


class FakePort:
    """Record configuration order and provide scripted bounded reads."""

    events: list[tuple[str, object]]
    constructor_arguments: dict[str, object]
    reads: list[object]
    fail_open: Exception | None
    fail_close: Exception | None
    report_open: bool
    read_calls: list[tuple[int, object]]
    is_open: bool
    timeout: object

    def __init__(
        self,
        constructor_arguments: dict[str, object],
        *,
        reads: list[object],
        fail_open: Exception | None = None,
        fail_close: Exception | None = None,
        report_open: bool = True,
    ) -> None:
        object.__setattr__(self, "events", [])
        object.__setattr__(self, "constructor_arguments", constructor_arguments)
        object.__setattr__(self, "reads", reads)
        object.__setattr__(self, "fail_open", fail_open)
        object.__setattr__(self, "fail_close", fail_close)
        object.__setattr__(self, "report_open", report_open)
        object.__setattr__(self, "read_calls", [])
        object.__setattr__(self, "is_open", False)
        object.__setattr__(self, "timeout", constructor_arguments["timeout"])

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"dtr", "rts", "port", "timeout"} and hasattr(self, "events"):
            self.events.append((name, value))
        object.__setattr__(self, name, value)

    def open(self) -> None:
        self.events.append(("open", None))
        if self.fail_open is not None:
            raise self.fail_open
        self.is_open = self.report_open

    def read(self, size: int) -> object:
        self.read_calls.append((size, self.timeout))
        action = self.reads.pop(0) if self.reads else b""
        if isinstance(action, Exception):
            raise action
        return action

    def close(self) -> None:
        self.events.append(("close", None))
        self.is_open = False
        if self.fail_close is not None:
            raise self.fail_close


class FakeDriver:
    FIVEBITS = "BITS5"
    SIXBITS = "BITS6"
    SEVENBITS = "BITS7"
    EIGHTBITS = "BITS8"
    PARITY_NONE = "PARITY_NONE"
    PARITY_EVEN = "PARITY_EVEN"
    PARITY_ODD = "PARITY_ODD"
    STOPBITS_ONE = "STOP_1"
    STOPBITS_ONE_POINT_FIVE = "STOP_1_5"
    STOPBITS_TWO = "STOP_2"
    SerialException = FakeSerialException

    def __init__(
        self,
        *,
        reads: tuple[object, ...] = (),
        fail_open: Exception | None = None,
        fail_close: Exception | None = None,
        report_open: bool = True,
    ) -> None:
        self.reads = list(reads)
        self.fail_open = fail_open
        self.fail_close = fail_close
        self.report_open = report_open
        self.instances: list[FakePort] = []
        self.constructor_calls: list[dict[str, object]] = []

    def Serial(self, **kwargs: object) -> FakePort:
        self.constructor_calls.append(kwargs)
        port = FakePort(
            kwargs,
            reads=self.reads,
            fail_open=self.fail_open,
            fail_close=self.fail_close,
            report_open=self.report_open,
        )
        self.instances.append(port)
        return port


@dataclass
class DiscoveredPort:
    device: object
    description: object

    @property
    def hwid(self) -> str:
        raise AssertionError("privacy boundary must not read hardware IDs")


def settings(**overrides: object) -> SerialConnectionSettings:
    values: dict[str, object] = {
        "port_id": "COM4",
        "profile_name": MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
        "max_record_bytes": MSP430_HEALTH_V1_SERIAL_IDENTITY.max_record_bytes,
    }
    values.update(overrides)
    return SerialConnectionSettings(**cast(Any, values))


def backend(
    driver: FakeDriver,
    ports: tuple[object, ...] = (),
) -> PySerialBackend:
    return PySerialBackend(driver=driver, port_enumerator=lambda: ports)


def test_constructor_requires_complete_injection_pair() -> None:
    with pytest.raises(PySerialBackendStateError, match="supplied together"):
        PySerialBackend(driver=FakeDriver())
    with pytest.raises(PySerialBackendStateError, match="supplied together"):
        PySerialBackend(port_enumerator=lambda: ())


def test_missing_dependency_is_lazy_and_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_: str) -> object:
        raise ModuleNotFoundError("injected missing dependency")

    monkeypatch.setattr("analog_validation_pyserial.backend.import_module", missing)
    concrete = PySerialBackend()

    assert concrete.is_open is False
    with pytest.raises(PySerialUnavailableError, match=r"\[serial\]"):
        concrete.discover_ports()


def test_discovery_is_receive_only_bounded_and_privacy_minimal() -> None:
    driver = FakeDriver()
    long_description = "  MSP\tApplication UART1  " + "X" * 200
    concrete = backend(
        driver,
        (
            DiscoveredPort("COM4", long_description),
            DiscoveredPort("COM5", None),
            DiscoveredPort("COM6", " \t "),
        ),
    )

    ports = concrete.discover_ports()

    assert tuple(port.port_id for port in ports) == ("COM4", "COM5", "COM6")
    assert ports[0].description is not None
    assert ports[0].description.startswith("MSP Application UART1")
    assert len(ports[0].description) == 128
    assert ports[1].description is None
    assert ports[2].description is None
    assert driver.constructor_calls == []
    assert not hasattr(concrete, "write")


def test_discovery_rejects_invalid_device_name() -> None:
    concrete = backend(FakeDriver(), (DiscoveredPort(None, "invalid"),))

    with pytest.raises(PySerialBackendStateError, match="device name"):
        concrete.discover_ports()


@pytest.mark.parametrize(
    ("data_bits", "expected"),
    [(5, "BITS5"), (6, "BITS6"), (7, "BITS7"), (8, "BITS8")],
)
def test_open_maps_every_data_bit_selection(data_bits: int, expected: str) -> None:
    driver = FakeDriver()
    concrete = backend(driver)

    concrete.open(settings(data_bits=data_bits))

    assert driver.constructor_calls[0]["bytesize"] == expected


@pytest.mark.parametrize(
    ("parity", "stop_bits", "expected_parity", "expected_stop"),
    [
        (SerialParity.NONE, SerialStopBits.ONE, "PARITY_NONE", "STOP_1"),
        (SerialParity.EVEN, SerialStopBits.ONE_POINT_FIVE, "PARITY_EVEN", "STOP_1_5"),
        (SerialParity.ODD, SerialStopBits.TWO, "PARITY_ODD", "STOP_2"),
    ],
)
def test_open_maps_line_settings_and_disables_flow_control(
    parity: SerialParity,
    stop_bits: SerialStopBits,
    expected_parity: str,
    expected_stop: str,
) -> None:
    driver = FakeDriver()
    concrete = backend(driver)

    concrete.open(settings(parity=parity, stop_bits=stop_bits, baud_rate=115_200))

    kwargs = driver.constructor_calls[0]
    assert kwargs == {
        "port": None,
        "baudrate": 115_200,
        "bytesize": "BITS8",
        "parity": expected_parity,
        "stopbits": expected_stop,
        "timeout": 0.25,
        "xonxoff": False,
        "rtscts": False,
        "write_timeout": 0,
        "dsrdtr": False,
        "inter_byte_timeout": None,
    }
    port = driver.instances[0]
    assert port.events[:4] == [
        ("dtr", False),
        ("rts", False),
        ("port", "COM4"),
        ("open", None),
    ]
    assert concrete.is_open is True


def test_open_validates_lifecycle_and_cleans_failed_instance() -> None:
    driver = FakeDriver(fail_open=FakeSerialException("busy"))
    concrete = backend(driver)

    with pytest.raises(FakeSerialException, match="busy"):
        concrete.open(settings())

    assert concrete.is_open is False
    assert driver.instances[0].events[-1] == ("close", None)

    healthy = backend(FakeDriver())
    healthy.open(settings())
    with pytest.raises(PySerialBackendStateError, match="already open"):
        healthy.open(settings())
    with pytest.raises(PySerialBackendStateError, match="settings"):
        backend(FakeDriver()).open(cast(Any, "COM4"))


def test_open_rejects_false_open_state_and_preserves_primary_error() -> None:
    not_open = backend(FakeDriver(report_open=False))
    with pytest.raises(PySerialBackendStateError, match="did not report"):
        not_open.open(settings())
    assert not_open.is_open is False

    primary = FakeSerialException("primary open failure")
    close = RuntimeError("secondary close failure")
    both_fail = backend(FakeDriver(fail_open=primary, fail_close=close))
    with pytest.raises(FakeSerialException, match="primary open failure") as raised:
        both_fail.open(settings())
    assert raised.value is primary


def test_bounded_read_updates_timeout_and_returns_bytes() -> None:
    driver = FakeDriver(reads=(bytearray(b"TEL\n"), memoryview(b"NEXT\n"), b""))
    concrete = backend(driver)
    concrete.open(settings())

    assert concrete.read(8, 0.5) == b"TEL\n"
    assert concrete.read(8, 0.75) == b"NEXT\n"
    assert concrete.read(8, 0.1) == b""
    assert driver.instances[0].read_calls == [(8, 0.5), (8, 0.75), (8, 0.1)]


@pytest.mark.parametrize(
    ("max_bytes", "timeout"),
    [(0, 0.1), (True, 0.1), (1, 0.0), (1, float("inf")), (1, True)],
)
def test_read_rejects_unbounded_arguments(max_bytes: object, timeout: object) -> None:
    concrete = backend(FakeDriver())
    concrete.open(settings())

    with pytest.raises(PySerialBackendStateError):
        concrete.read(cast(Any, max_bytes), cast(Any, timeout))


@pytest.mark.parametrize("error", [FakeSerialException("lost"), OSError("lost")])
def test_driver_disconnects_map_to_core_reconnect_signal(error: Exception) -> None:
    concrete = backend(FakeDriver(reads=(error,)))
    concrete.open(settings())

    with pytest.raises(SerialBackendDisconnected, match="receive failed") as raised:
        concrete.read(16, 0.1)

    assert raised.value.__cause__ is error
    assert concrete.is_open is True


def test_unrelated_driver_read_error_is_not_mislabeled_as_disconnect() -> None:
    error = ValueError("driver contract bug")
    concrete = backend(FakeDriver(reads=(error,)))
    concrete.open(settings())

    with pytest.raises(ValueError, match="contract bug") as raised:
        concrete.read(16, 0.1)

    assert raised.value is error


@pytest.mark.parametrize("action", ["text", b"12345"])
def test_read_rejects_driver_contract_violations(action: object) -> None:
    concrete = backend(FakeDriver(reads=(action,)))
    concrete.open(settings())

    with pytest.raises(PySerialBackendStateError, match="pyserial read"):
        concrete.read(4, 0.1)


def test_read_requires_open_and_close_is_idempotent() -> None:
    concrete = backend(FakeDriver())

    with pytest.raises(PySerialBackendStateError, match="not open"):
        concrete.read(1, 0.1)
    concrete.close()

    concrete.open(settings())
    concrete.close()
    concrete.close()
    assert concrete.is_open is False


def test_close_clears_reference_even_when_driver_close_fails() -> None:
    concrete = backend(FakeDriver(fail_close=RuntimeError("close failed")))
    concrete.open(settings())

    with pytest.raises(RuntimeError, match="close failed"):
        concrete.close()

    assert concrete.is_open is False


def test_serial_session_composes_with_concrete_backend() -> None:
    driver = FakeDriver(reads=(b"partial", b" record\n", b""))
    concrete = backend(
        driver,
        (DiscoveredPort("COM4", "MSP Application UART1"),),
    )
    connection = settings(read_chunk_bytes=32)
    session = SerialSession(concrete, connection)

    assert session.discover_ports()[0].port_id == "COM4"
    session.open()
    first = session.poll()
    second = session.poll()
    timeout = session.poll()
    session.close()

    assert first.status is SerialPollStatus.DATA
    assert first.records == ()
    assert second.records[0].raw_bytes == b"partial record\n"
    assert timeout.status is SerialPollStatus.TIMEOUT
    assert not hasattr(concrete, "write")


def test_lazy_dependency_loader_accepts_official_module_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = FakeDriver()
    inventory = (DiscoveredPort("COM4", "MSP Application UART1"),)
    list_ports = SimpleNamespace(comports=lambda: inventory)
    loaded: list[str] = []

    def load(name: str) -> object:
        loaded.append(name)
        return driver if name == "serial" else list_ports

    monkeypatch.setattr("analog_validation_pyserial.backend.import_module", load)
    concrete = PySerialBackend()

    assert concrete.discover_ports()[0].port_id == "COM4"
    assert concrete.discover_ports()[0].port_id == "COM4"
    assert loaded == ["serial", "serial.tools.list_ports"]


def test_lazy_dependency_loader_rejects_missing_comports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = FakeDriver()

    def load(name: str) -> object:
        return driver if name == "serial" else SimpleNamespace()

    monkeypatch.setattr("analog_validation_pyserial.backend.import_module", load)

    with pytest.raises(PySerialUnavailableError, match="enumeration API"):
        PySerialBackend().discover_ports()


def test_open_rejects_incomplete_driver_api() -> None:
    incomplete = SimpleNamespace(Serial=lambda **_: None)
    concrete = PySerialBackend(driver=incomplete, port_enumerator=lambda: ())

    with pytest.raises(PySerialUnavailableError, match="FIVEBITS"):
        concrete.open(settings())
