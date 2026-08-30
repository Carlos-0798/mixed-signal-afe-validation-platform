"""Controller-neutral device adapter contract."""

from .base import AdapterState, DeviceAdapter
from .csv_replay import (
    CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    ReplayChannelConfig,
    ReplayChannelKind,
    ReplayTimingMode,
)
from .simulator import (
    DEFAULT_SIMULATOR_EPOCH,
    SIMULATOR_CONFIG_SCHEMA_VERSION,
    SimulatorAdapter,
    SimulatorConfig,
    SimulatorFaultMode,
    generate_afe_telemetry,
)

__all__ = [
    "CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION",
    "DEFAULT_SIMULATOR_EPOCH",
    "SIMULATOR_CONFIG_SCHEMA_VERSION",
    "AdapterState",
    "CsvReplayAdapter",
    "CsvReplayAdapterConfig",
    "DeviceAdapter",
    "ReplayChannelConfig",
    "ReplayChannelKind",
    "ReplayTimingMode",
    "SimulatorAdapter",
    "SimulatorConfig",
    "SimulatorFaultMode",
    "generate_afe_telemetry",
]
