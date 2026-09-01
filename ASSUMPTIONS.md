# Assumptions and user confirmations

Nothing in this file is evidence that hardware exists, is wired, or has passed a measurement. Items marked **OPEN** must be confirmed before Phase 1.

## MSP430 toolchain

- **PARTIAL:** One MSP-EXP430FR6989 LaunchPad is reported available. Record its board revision and verify it with a known-good example before Phase 1.
- **PARTIAL:** The computer has USB-A. Confirm the Windows version and installed Code Composer Studio version.
- **OPEN:** Choose TI MSP430 Clang or another supported compiler; record exact compiler and linker versions.
- **OPEN:** Confirm whether MSP430Ware/DriverLib will be used and pin its version.
- **OPEN:** Confirm the LaunchPad debug probe firmware is current and the board can be programmed with a known-good example.
- **CONFIRMED FOR PASSIVE STEP 7 ONLY:** Windows identified `MSP Application UART1 (COM4)` and `MSP Debug Interface (COM5)`; this repository opened only COM4 at 115200 8N1 and received five consecutive CRC-valid TEL records with zero application writes. Exact current firmware, control-line electrical behavior, and future AFE wiring remain unconfirmed.
- **OPEN:** Compare the future `board_pins.h` map with the independent MSP430 Equipment Health Controller before connecting the projects.

The formal core assumes Python 3.10+ and uses only the standard library. Pytest is needed for tests; pyserial is an optional `[serial]` extra and is not required for simulation, replay, analysis, or core imports.

## Parts actually on hand

- **CONFIRMED:** The 2026-08-29 screenshot is an unpurchased cart. None of its entries count as on-hand inventory.
- **CONFIRMED:** One MSP-EXP430FR6989 LaunchPad is reported available. A second controller need not be the same model.
- **PROPOSED:** Use an STM32 NUCLEO-G474RE only as a replaceable reference validation controller. The AFE platform remains the independent product; MSP430FR6989 is one external compatibility profile, not the target/DUT that defines the product. User confirmation of the additional STM32Cube toolchain is required before purchase.
- **OPEN:** Inventory MCP6004 and MCP6544 parts, including package, exact suffix, quantity, and source.
- **OPEN:** Confirm 1% resistor values available for 10.0 kOhm, 40.2 kOhm, 90.9 kOhm, and the selected Schmitt network. Substitutions require recalculation.
- **OPEN:** Confirm capacitor measured/marked values for 10 nF, 100 nF, and 1 uF; note dielectric and tolerance.
- **OPEN:** Identify the exact Schottky clamp diode and check its current and capacitance data before use.
- **OPEN:** Confirm breadboard, jumpers, 10 kOhm potentiometers, LED resistors, and 100 nF local decoupling capacitors.
- **OPEN:** Confirm whether ADS1115 and AD9833 are absent/deferred or already available. They are not required for Phase 1.
- **OPEN:** Record datasheet revisions for the actual op amp and comparator before replacing idealized SPICE models.

## Instrument access and permission

- **PLANNED:** Purchase a Klein Tools MM420 DMM. Record the actual seller, serial/model label, receipt, and known-voltage sanity check after arrival; it is not a calibration-grade reference.
- **PARTIAL:** OSU lab access may be possible but is not guaranteed. The project must remain executable without OSU instruments; if access is granted, record permission, supervision, scheduling, and data-export rules.
- **OPEN:** If using a Labrador or similar USB instrument, record exact hardware/software versions and accepted bandwidth/power limitations.
- **PROPOSED:** Independent supply chain is Adafruit #276 5 V adapter -> #373 barrel jack -> MF-R025 resettable fuse -> THT reverse-polarity Schottky -> MCP1702-3302E/TO with data-sheet capacitors -> 3.3 V AFE rail. This is a parts/design decision only; confirm empty-board voltage, polarity, thermal behavior, rail current, and safe common ground before installing signal ICs. It is not a precision reference or a laboratory current-limited bench supply.
- **OPEN:** Confirm whether photographs and anonymized plots from the permitted workspace may be published.

No OSU laboratory access is assumed by this repository.

## Budget and build tools

- **CONFIRMED:** The USD 200 ceiling is for AFE project purchases only. Both the other project's USD 137.75 unpurchased cart and the planned Klein MM420 are paid outside this ceiling.
- **CONFIRMED:** The linked two-store plan uses Adafruit plus Mouser. The independent Base Unit (A) planning subtotal is USD 85.85. Adding the recommended automation add-on (B) gives USD 106.25; adding the proposed NUCLEO-G474RE and USB data cable (C) gives USD 129.33, leaving USD 70.67 before tax and shipping. The ceiling is not a spending target; current sources are `hardware/bom/INDEPENDENT_PRODUCT_PROCUREMENT.md` and `hardware/bom/independent-product-purchase.xlsx`.
- **CONFIRMED:** No soldering iron or solder is currently available; ventilation is available. Soldering equipment is deferred because Phase 1-4 begin on solderless breadboard.
- **CONFIRMED:** Do not purchase a Labrador, AD9833, second Perma-Proto, custom PCB, or soldering system until its later decision gate is reached.
- **OPEN:** Choose the validation controller: proposed NUCLEO-G474RE; simpler alternatives are Metro RP2040/CircuitPython or an LP-MSPM0G3507 when authorized stock stabilizes.

## Physical wiring required before Phase 1 power-up

- **OPEN:** Provide a marked-up wiring diagram or clear photos showing every rail, ground, IC orientation, and pin number.
- **OPEN:** Confirm the MCP6004 and MCP6544 pinouts against their exact packages.
- **OPEN:** Confirm 100 nF decoupling at each IC supply pair and the bulk capacitor location.
- **OPEN:** Confirm 3.3 V rail-to-ground resistance/continuity with power removed.
- **OPEN:** Confirm VBIAS divider and buffer wiring; measure VBIAS before connecting signal stages.
- **OPEN:** Confirm input series resistance and clamps, including diode orientation.
- **OPEN:** Confirm the gain-jumper truth table and ensure no setting shorts an output or rail.
- **OPEN:** Confirm the comparator output type and any required pull-up; keep LED current out of the threshold network.
- **OPEN:** Confirm a single common ground among source, AFE, LaunchPad, and instruments before signal connection.
- **OPEN:** Confirm every MCU/ADC/GPIO node remains between 0 V and its actual supply under all planned stimuli.

## Phase 0 calculation assumptions

- Nominal supply/reference examples use 3.300 V, not a measured rail.
- The ADC examples assume an ideal unipolar 12-bit converter and do not include reference, offset, gain, INL, DNL, noise, source impedance, or settling errors.
- LTspice Phase 0 netlists use idealized sources/elements. They do not establish MCP6004 common-mode range, output swing, GBW/stability, comparator delay, output topology, or breadboard parasitics.
- Synthetic sweep noise and clipping are generated by software and must never be reported as bench results.
