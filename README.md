# Configurable Analog Front-End & Validation Platform

Independent, reusable product project for a low-voltage configurable analog front end and controller-neutral validation tooling.

## Current status

**Software Phase 1 is in progress. Step 1 established the installable `analog_validation` package and version `0.1.0.dev0`.** Phase 0 design, idealized LTspice checks, synthetic telemetry, and host-side algorithms remain available during migration. No breadboard, PCB, MSP430 firmware, instrument measurement, electrical limit, accuracy target, or hardware behavior has been verified.

The current execution baseline is software-first: mature the controller-neutral validation software before freezing or purchasing the new AFE hardware. The governing scope, requirements, safety rules, staged acceptance gates, and future hardware plan are defined in `docs/PRODUCT_PLAN.md`. The original development specification remains preserved as a requirements source.

Software Phase 0 has now established the current host baseline and implementation roadmap. See `reports/software-phase0-baseline.md`, `docs/audits/SOFTWARE_PHASE_0_AUDIT.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, and `docs/SOFTWARE_PHASE_1_PLAN.md`. This milestone does not add or validate hardware capability.

Software Phase 1 Step 1 passed editable installation, 25 pytest tests, Ruff and mypy checks for the new package, isolated package builds, and a clean wheel import outside the repository. See `reports/software-phase1-step1.md`.

The independently installed and verified Windows development setup is documented in `docs/DEVELOPMENT_ENVIRONMENT.md`; its verification record is `reports/environment-setup-2026-08-29.md`.

The AFE platform is the product, not an accessory of another controller project. Its analog base unit must operate without an MCU; optional validation controllers and external 3.3 V MCUs connect through documented UART/I2C/SPI/GPIO/analog interfaces. The MSP430 Equipment Health Controller is one compatibility example only. This repository is also independent from the OSU Lab Bench Monitor Capstone.

## Software development quick start

Python 3.10+ and pytest are required for host tests:

```text
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -c "import analog_validation; print(analog_validation.__version__)"
.\.venv\Scripts\python.exe tools/telemetry_simulator.py --count 5
.\.venv\Scripts\python.exe tools/synthetic_sweep_generator.py --points 21
```

See `ASSUMPTIONS.md` before selecting parts or wiring hardware. Protocol details are in `docs/protocol.md`; theory is in `docs/theory.md`; the verification split is in `docs/test-plan.md`.

For a beginner-oriented explanation of the complete roadmap, software setup, safety process, and our checkpoint cadence, see `docs/BEGINNER_PROJECT_GUIDE.md`. The current controller-independent purchase plan is `hardware/bom/INDEPENDENT_PRODUCT_PROCUREMENT.md`; `hardware/bom/independent-product-purchase.xlsx` is its linked, formula-driven order checklist. The earlier CSV and screenshot-cart analysis remain for traceability only.

The confirmed USD 200 budget, selected Klein MM420, and software-heavy fallback if OSU instruments are unavailable are recorded in `docs/BUDGET_AND_FALLBACK_DECISION.md`.

The proposed second-board architecture and comparison of NUCLEO-G474RE, LP-MSPM0G3507, Metro RP2040, Pico H, and a duplicate MSP430 board are in `docs/CONTROLLER_BOARD_SELECTION.md`.

The product boundary, replaceable controller layer, standalone modes, public interfaces, and independence acceptance criteria are in `docs/PRODUCT_ARCHITECTURE.md`.

## Safety and evidence boundary

- Only 0-3.3 V low-voltage work is in scope; no mains experiments.
- Synthetic data is labeled synthetic and is not measurement evidence.
- Idealized SPICE runs are not component-model validation or hardware measurements.
- Software Phase 1 does not require hardware. Physical hardware phases cannot start safely until the parts, instrument access, electrical limits, and wiring questions in `ASSUMPTIONS.md` are answered.
