"""Public package for Analog Validation Studio.

The package is controller-neutral: importing it must not require a serial
driver, GUI toolkit, board SDK, or physical hardware.
"""

from .version import __version__

__all__ = ["__version__"]
