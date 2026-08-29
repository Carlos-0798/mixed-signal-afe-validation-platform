# LTspice simulation task list

## Phase 0 ideal checks

- [x] Buffer DC transfer: swept 0-3.3 V with the deliberately ideal source model.
- [x] Non-inverting gain: checked the nominal x2 topology.
- [ ] Add x5.02 and x10.09 variants after resistor inventory is confirmed.
- [x] RC low-pass: swept 16 kOhm/100 nF and measured the nominal -3 dB cutoff.
- [x] Ideal Schmitt element: used a slow triangle input and measured rising/falling-input transitions.
- [x] Archived the actual log measurements, LTspice version, and evidence label in `../expected-results/phase0-ltspice-26.0.1.md`.

## Before Phase 1 claims

- [ ] Obtain legally redistributable MCP6004 and MCP6544 vendor models or document why a validated substitute is used.
- [ ] Add measured/selected load, output pull-up if applicable, source impedance, clamp diodes, rail values, and VBIAS network.
- [ ] Check DC operating point, common-mode limits, output swing, supply current, and resistor tolerance corners.
- [ ] Run transient stability/startup checks with decoupling and representative breadboard parasitics.
- [ ] Sweep filter tolerances and compare against the analytic bounds.
- [ ] Keep component-model simulation results separate from ideal netlists and later bench data.
