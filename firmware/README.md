# Firmware placeholder

No physical-controller firmware is implemented in Phase 0. The AFE product is controller-independent and its standalone analog functions cannot require firmware.

Future firmware is split into:

- controller-neutral `afe/`, `protocol/`, and test behavior;
- replaceable `board/` and `drivers/` implementations for the reference validation controller;
- separate compatibility profiles for MSP430, RP2040, or other 3.3 V controllers;
- a host-visible capability description so unsupported ADC/DAC/PWM features are detected rather than assumed.

The future C tree will contain `app/`, `board/`, `drivers/`, `afe/`, `protocol/`, and `tests/`. Pin definitions must be centralized under board-specific files after each integration map is confirmed; no MSP430 register or pin name may leak into the controller-neutral protocol or measurement algorithms.
