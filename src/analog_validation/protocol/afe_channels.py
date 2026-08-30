"""Explicit AFE channel-name mapping between legacy and canonical forms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from analog_validation.errors import ValidationError

AFE_CHANNEL_MAPPING_SCHEMA_VERSION = "afe-channel-map.v1"
_CHANNEL_PATTERN = re.compile(r"^afe\.ch(0|[1-9][0-9]{0,2})\.([a-z_]+)$")


class AfeChannelRole(str, Enum):
    """Meaning of one AFE telemetry-derived measurement channel."""

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    GAIN = "GAIN"
    THRESHOLD = "THRESHOLD"


class AfeChannelNaming(str, Enum):
    """Versioned channel-name vocabulary used at an interface boundary."""

    CANONICAL = "CANONICAL"
    LEGACY_TELEMETRY_V1 = "LEGACY_TELEMETRY_V1"


_SUFFIXES: dict[AfeChannelNaming, dict[AfeChannelRole, str]] = {
    AfeChannelNaming.CANONICAL: {
        AfeChannelRole.INPUT: "input",
        AfeChannelRole.OUTPUT: "output",
        AfeChannelRole.GAIN: "gain",
        AfeChannelRole.THRESHOLD: "threshold",
    },
    AfeChannelNaming.LEGACY_TELEMETRY_V1: {
        AfeChannelRole.INPUT: "input_mv",
        AfeChannelRole.OUTPUT: "output_mv",
        AfeChannelRole.GAIN: "gain",
        AfeChannelRole.THRESHOLD: "threshold",
    },
}


def _require_channel(channel: int) -> int:
    if isinstance(channel, bool) or not isinstance(channel, int):
        raise ValidationError("AFE channel index must be an integer")
    if not 0 <= channel <= 0xFF:
        raise ValidationError("AFE channel index must be between 0 and 255")
    return channel


def _require_role(role: AfeChannelRole) -> AfeChannelRole:
    if not isinstance(role, AfeChannelRole):
        raise ValidationError("role must be an AfeChannelRole")
    return role


def _require_naming(naming: AfeChannelNaming) -> AfeChannelNaming:
    if not isinstance(naming, AfeChannelNaming):
        raise ValidationError("naming must be an AfeChannelNaming")
    return naming


@dataclass(frozen=True, slots=True)
class AfeChannelReference:
    """Device channel index and semantic role independent of spelling."""

    channel: int
    role: AfeChannelRole

    def __post_init__(self) -> None:
        _require_channel(self.channel)
        _require_role(self.role)


def format_afe_channel(
    channel: int,
    role: AfeChannelRole,
    *,
    naming: AfeChannelNaming,
) -> str:
    """Render one reference using an explicitly selected naming vocabulary."""

    index = _require_channel(channel)
    selected_role = _require_role(role)
    selected_naming = _require_naming(naming)
    return f"afe.ch{index}.{_SUFFIXES[selected_naming][selected_role]}"


def parse_afe_channel(
    channel_name: str,
    *,
    naming: AfeChannelNaming,
) -> AfeChannelReference:
    """Parse one name only under the explicitly declared vocabulary."""

    selected_naming = _require_naming(naming)
    if not isinstance(channel_name, str):
        raise ValidationError("channel_name must be a string")
    match = _CHANNEL_PATTERN.fullmatch(channel_name)
    if match is None:
        raise ValidationError("channel_name must use afe.ch<0..255>.<role> form")
    channel = _require_channel(int(match.group(1)))
    suffix = match.group(2)
    roles_by_suffix = {
        value: role for role, value in _SUFFIXES[selected_naming].items()
    }
    try:
        role = roles_by_suffix[suffix]
    except KeyError as error:
        raise ValidationError(
            f"channel_name is not valid for {selected_naming.value}"
        ) from error
    return AfeChannelReference(channel, role)


def convert_afe_channel(
    channel_name: str,
    *,
    source: AfeChannelNaming,
    target: AfeChannelNaming,
) -> str:
    """Convert only when both source and target vocabularies are explicit."""

    reference = parse_afe_channel(channel_name, naming=source)
    return format_afe_channel(reference.channel, reference.role, naming=target)


__all__ = [
    "AFE_CHANNEL_MAPPING_SCHEMA_VERSION",
    "AfeChannelNaming",
    "AfeChannelReference",
    "AfeChannelRole",
    "convert_afe_channel",
    "format_afe_channel",
    "parse_afe_channel",
]
