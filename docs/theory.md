# Phase 0 theoretical calculations

These are nominal calculations, not LTspice component-model results or physical measurements. Resistance, capacitance, supply, reference, offset, noise, loading, common-mode range, output swing, and temperature tolerances must be added later.

## Non-inverting gain

For a non-inverting amplifier,

```text
G = Vout / Vin = 1 + Rf / Rg
Vout,ideal = G * Vin
```

The x1 setting is a voltage follower: output is wired to the inverting input and the resistor formula is not used with a fictitious zero-ohm denominator.

| Target | Proposed nominal network | Calculated gain | Nominal error from target |
|---:|---|---:|---:|
| x1 | voltage follower | 1.000 | 0.00% |
| x2 | Rg = 10.0 kOhm, Rf = 10.0 kOhm | 2.000 | 0.00% |
| x5 | Rg = 10.0 kOhm, Rf = 40.2 kOhm | 5.020 | +0.40% |
| x10 | Rg = 10.0 kOhm, Rf = 90.9 kOhm | 10.090 | +0.90% |

For independent resistor tolerances, a conservative first-order bound is applied to `Rf/Rg`, not directly to the entire gain:

```text
delta_G ~= (Rf/Rg) * (delta_Rf/Rf - delta_Rg/Rg)
```

At large gain with two independent 1% resistors, the ratio worst-case bound is approximately 2%. Real acceptance limits must also include amplifier and measurement error.

The useful input range is limited by the actual output swing:

```text
Vin,max_linear <= Vout,max_linear / G
```

Using 3.3 V as if it were an attainable output rail is only an ideal calculation; the MCP6004 datasheet and bench results must set the real margin.

## First-order RC low-pass cutoff

```text
H(jf) = 1 / (1 + j*f/fc)
fc = 1 / (2*pi*R*C)
|H(fc)| = 1/sqrt(2) ~= 0.7071 (-3.0103 dB)
```

With nominal R = 16.0 kOhm:

| C | Calculated fc | Intended band |
|---:|---:|---:|
| 1.0 uF | 9.947 Hz | about 10 Hz |
| 100 nF | 99.472 Hz | about 100 Hz |
| 10 nF | 994.718 Hz | about 1 kHz |

For small independent tolerances, a conservative cutoff bound is approximately `|delta_fc/fc| <= |delta_R/R| + |delta_C/C|`. Source and load impedances alter the effective R and must be included in the final circuit.

## Inverting Schmitt trigger thresholds

The Phase 0 reference topology drives the comparator inverting input with `Vin`. Its non-inverting node connects to `Vout` through `R_OUT` and to `VREF` through `R_REF`:

```text
Vout --- R_OUT ---+--- (+) comparator
                  |
VREF --- R_REF ---+
Vin --------------(-)
```

Ignoring input current,

```text
Vplus = (R_REF*Vout + R_OUT*VREF) / (R_OUT + R_REF)

VTH_HIGH = (R_REF*VOH + R_OUT*VREF) / (R_OUT + R_REF)
VTH_LOW  = (R_REF*VOL + R_OUT*VREF) / (R_OUT + R_REF)
VHYS     = VTH_HIGH - VTH_LOW
         = R_REF*(VOH - VOL) / (R_OUT + R_REF)
```

For the nominal example `R_OUT = 100 kOhm`, `R_REF = 10 kOhm`, `VREF = 1.650 V`, `VOH = 3.300 V`, and `VOL = 0 V`:

| Quantity | Nominal value |
|---|---:|
| Rising-input trip, VTH_HIGH | 1.800 V |
| Falling-input trip, VTH_LOW | 1.500 V |
| Hysteresis width | 0.300 V |

These values depend on the real comparator output levels and resistor network. The exact MCP6544 output behavior, loading, propagation delay, input offset, and supply conditions remain unverified.

## ADC code and engineering units

For an ideal unipolar N-bit ADC whose endpoint mapping is represented as code `0 ... 2^N-1`:

```text
voltage_mv = code * vref_mv / (2^N - 1)
code       = round(voltage_mv * (2^N - 1) / vref_mv)
```

For a 12-bit code and nominal 3300 mV reference:

| Code | Endpoint-scaled nominal voltage |
|---:|---:|
| 0 | 0.000 mV |
| 2048 | 1650.403 mV |
| 4095 | 3300.000 mV |

The ideal quantization step is `Vref / 2^N = 3300/4096 = 0.805664 mV/code`; this is distinct from the convenient endpoint-scaling denominator `4095`. Firmware must choose and document one conversion convention, keep the raw code, and use a measured/reference-calibrated `vref_mv` when available.

For an analog path with calibrated gain `Gcal` and output-referred offset `Voffset`:

```text
input_mv = (adc_mv - Voffset_mv) / Gcal
```

No calibration coefficient is valid until it comes from traceable hardware data.

