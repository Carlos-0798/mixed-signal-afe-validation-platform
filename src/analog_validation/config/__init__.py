"""Safe, versioned configuration API."""

from .models import (
    VALIDATION_CONFIG_SCHEMA_VERSION,
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    TimeoutConfig,
    ValidationConfig,
)
from .validation import (
    MAX_CONFIG_BYTES,
    dump_validation_config_json,
    load_validation_config,
    parse_validation_config_json,
    validate_config_capabilities,
    validation_config_to_dict,
)

__all__ = [
    "MAX_CONFIG_BYTES",
    "VALIDATION_CONFIG_SCHEMA_VERSION",
    "ChannelConfig",
    "ChannelRole",
    "ProfileConfig",
    "TimeoutConfig",
    "ValidationConfig",
    "dump_validation_config_json",
    "load_validation_config",
    "parse_validation_config_json",
    "validate_config_capabilities",
    "validation_config_to_dict",
]
