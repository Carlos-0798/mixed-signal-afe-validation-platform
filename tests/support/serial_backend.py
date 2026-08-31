"""Scriptable in-memory implementation of the driver-neutral serial port."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from analog_validation.transport import (
    SerialBackendTimeout,
    SerialConnectionSettings,
    SerialPortInfo,
)


def _raise_or_return(action: object) -> object:
    if isinstance(action, BaseException):
        raise action
    return action


@dataclass
class MemorySerialBackend:
    """A deterministic backend with scripted discovery/open/read/close outcomes."""

    ports: tuple[SerialPortInfo, ...] = ()
    discover_actions: deque[object] = field(default_factory=deque)
    open_actions: deque[object] = field(default_factory=deque)
    read_actions: deque[object] = field(default_factory=deque)
    close_actions: deque[object] = field(default_factory=deque)
    discover_calls: int = 0
    open_calls: list[SerialConnectionSettings] = field(default_factory=list)
    read_calls: list[tuple[int, float]] = field(default_factory=list)
    close_calls: int = 0
    is_open: bool = False

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        self.discover_calls += 1
        action = self.discover_actions.popleft() if self.discover_actions else self.ports
        return _raise_or_return(action)  # type: ignore[return-value]

    def open(self, settings: SerialConnectionSettings) -> None:
        self.open_calls.append(settings)
        action = self.open_actions.popleft() if self.open_actions else None
        _raise_or_return(action)
        self.is_open = True

    def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
        self.read_calls.append((max_bytes, timeout_seconds))
        if not self.is_open:
            raise RuntimeError("memory backend is closed")
        action = (
            self.read_actions.popleft()
            if self.read_actions
            else SerialBackendTimeout()
        )
        return _raise_or_return(action)  # type: ignore[return-value]

    def close(self) -> None:
        self.close_calls += 1
        self.is_open = False
        action = self.close_actions.popleft() if self.close_actions else None
        _raise_or_return(action)

    @classmethod
    def scripted(
        cls,
        *,
        ports: tuple[SerialPortInfo, ...] = (),
        discover: tuple[object, ...] = (),
        opens: tuple[object, ...] = (),
        reads: tuple[object, ...] = (),
        closes: tuple[object, ...] = (),
    ) -> MemorySerialBackend:
        """Build a backend from immutable action sequences for concise tests."""

        return cls(
            ports=ports,
            discover_actions=deque(discover),
            open_actions=deque(opens),
            read_actions=deque(reads),
            close_actions=deque(closes),
        )


__all__ = ["MemorySerialBackend"]
