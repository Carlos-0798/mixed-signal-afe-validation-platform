"""Public serial-profile extension point and concrete product profiles."""

from .afe_v1 import (
    AFE_V1_SEQUENCE_BITS,
    AFE_V1_SERIAL_IDENTITY,
    AfeV1SerialProfile,
)
from .core import (
    MAX_PROFILE_IDENTITY_CHARS,
    SERIAL_PROFILE_SCHEMA_VERSION,
    SerialProfile,
    SerialProfileIdentity,
    SerialProfileRecord,
    SerialProfileResetResult,
)
from .errors import SerialProfileError, SerialProfileStateError
from .msp430_health_v1 import (
    MSP430_HEALTH_V1_SEQUENCE_BITS,
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    Msp430HealthV1SerialProfile,
)

__all__ = [
    "AFE_V1_SEQUENCE_BITS",
    "AFE_V1_SERIAL_IDENTITY",
    "MAX_PROFILE_IDENTITY_CHARS",
    "MSP430_HEALTH_V1_SEQUENCE_BITS",
    "MSP430_HEALTH_V1_SERIAL_IDENTITY",
    "SERIAL_PROFILE_SCHEMA_VERSION",
    "AfeV1SerialProfile",
    "Msp430HealthV1SerialProfile",
    "SerialProfile",
    "SerialProfileError",
    "SerialProfileIdentity",
    "SerialProfileRecord",
    "SerialProfileResetResult",
    "SerialProfileStateError",
]
