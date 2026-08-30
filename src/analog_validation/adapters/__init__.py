"""Controller-neutral device adapter contract."""

from .base import AdapterState, DeviceAdapter
from .simulator import (
    DEFAULT_SIMULATOR_EPOCH,
    SIMULATOR_CONFIG_SCHEMA_VERSION,
    SimulatorAdapter,
    SimulatorConfig,
    generate_afe_telemetry,
)

__all__ = [
    "DEFAULT_SIMULATOR_EPOCH",
    "SIMULATOR_CONFIG_SCHEMA_VERSION",
    "AdapterState",
    "DeviceAdapter",
    "SimulatorAdapter",
    "SimulatorConfig",
    "generate_afe_telemetry",
]
