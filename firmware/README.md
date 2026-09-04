# Firmware status

No reference-controller firmware for the future configurable AFE is
implemented or claimed. The software repository contains host-side protocols,
profiles, fixtures, adapters, and product workflows; those are not embedded
firmware and do not prove a physical controller implementation.

The AFE product remains controller-independent, and its standalone manual
analog functions cannot require firmware.

Future firmware is split into:

- controller-neutral `afe/`, `protocol/`, and test behavior;
- replaceable `board/` and `drivers/` implementations for the reference validation controller;
- separate compatibility profiles for MSP430, RP2040, or other 3.3 V controllers;
- a host-visible capability description so unsupported ADC/DAC/PWM features are detected rather than assumed.

The future C tree will contain `app/`, `board/`, `drivers/`, `afe/`, `protocol/`, and `tests/`. Pin definitions must be centralized under board-specific files after each integration map is confirmed; no MSP430 register or pin name may leak into the controller-neutral protocol or measurement algorithms.

The existing MSP430 Equipment Health v1 support is a receive-only host
compatibility profile for a separate peer product. This repository does not
copy, own, merge, or version that project's firmware. A future reference
controller and any MSP430 compatibility firmware must have independent build,
flash, test, and evidence records before hardware claims can be made.
