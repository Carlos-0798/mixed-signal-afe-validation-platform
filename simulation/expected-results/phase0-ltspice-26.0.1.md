# Phase 0 LTspice ideal-check record

- Evidence label: `SPICE_IDEAL`
- Simulator: LTspice for Windows 26.0.1 (file version 26.0.1.0)
- Run time: 2026-08-28 23:51 America/New_York
- Invocation: `LTspice.exe -b <absolute-path-to-netlist.cir>`
- Model provenance: only ideal LTspice primitives and its built-in proprietary `SCHMITT` A-device; no MCP6004 or MCP6544 macromodel was used.

## Actual batch results

All four final batch processes exited with code 0.

| Netlist | SHA-256 | Measurement copied from generated log |
|---|---|---|
| `buffer_ideal.cir` | `F83ABC22377CB1C18D9F922AA4A3570E6E5A301250C4A19262F9089D4E9D0137` | `vout_at_1v = 1 V`; `vout_at_3v = 3 V` |
| `gain_stage_ideal.cir` | `161866100F43177CA2C8E9FE418092FA2489476D8C8E668A52842FACD44EF6BE` | `vout_at_1v = 1.99999594688 V` |
| `rc_lowpass_ideal.cir` | `FA49F02973AC5279813C24541F0C888257F8BED44EA747CA573992EC99138CF6` | `fc = 99.4718380026 Hz`; magnitude at 100 Hz = `-3.03335936198 dB` |
| `schmitt_ideal.cir` | `7FA271CCF4ACDDD05B42EDD4E9A0492A5C3031A002D3C24564E8D182AE6A79F3` | input-rising trip = `1.80082432926 V`; input-falling trip = `1.49917552869 V` |

## Execution note

The first Schmitt attempt exited with code 1 because it incorrectly used `.model` syntax for the LTspice A-device. The netlist was corrected using the locally installed LTspice help syntax, measurement names were made explicit about input direction, and the final four-netlist batch above was rerun. The failed attempt is not counted as a pass.

## Interpretation limit

The small differences from exact nominal values arise from finite ideal-op-amp gain and transient measurement time resolution in these netlists. These runs check equations and analysis wiring only. They do not validate the chosen ICs, rail behavior, tolerances, parasitics, physical wiring, or any target accuracy.

