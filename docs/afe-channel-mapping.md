# AFE Channel Naming Mapping v1

**Schema:** `afe-channel-map.v1`<br>
**Implemented in:** Software Phase 4 Step 2<br>
**Evidence:** HOST_TEST<br>
**Hardware validation:** none

## 1. Why a mapping is necessary

Two already-tested parts of the product used different names for the same AFE
roles:

- the original AFE v1 telemetry mapper emits `afe.chN.input_mv` and
  `afe.chN.output_mv`;
- Simulator and ReadWorkflow configurations use `afe.chN.input` and
  `afe.chN.output`.

The difference is spelling, not electrical meaning. A `Measurement` already
stores its unit separately, so the canonical name does not repeat `_mv`.
Removing `_mv` directly from historical records would silently change frozen
Phase 1–3 results, however. Step 2 therefore adds an explicit, versioned
conversion instead of renaming existing data in place.

## 2. Frozen mapping

| Role | Canonical name | Legacy AFE telemetry v1 name |
|---|---|---|
| input | `afe.chN.input` | `afe.chN.input_mv` |
| output | `afe.chN.output` | `afe.chN.output_mv` |
| gain | `afe.chN.gain` | `afe.chN.gain` |
| threshold | `afe.chN.threshold` | `afe.chN.threshold` |

`N` is an integer from 0 through 255 with no leading zero aliases. Canonical
names match the existing Simulator/ReadWorkflow vocabulary. Gain and threshold
happen to have identical spellings in both vocabularies, but callers still
declare the source and target naming modes so the conversion boundary remains
auditable.

## 3. Explicit conversion rule

The implementation lives in `analog_validation.protocol.afe_channels`.
Conversion requires both the source and target vocabulary:

```python
from analog_validation.protocol.afe_channels import (
    AfeChannelNaming,
    convert_afe_channel,
)

canonical = convert_afe_channel(
    "afe.ch0.input_mv",
    source=AfeChannelNaming.LEGACY_TELEMETRY_V1,
    target=AfeChannelNaming.CANONICAL,
)
assert canonical == "afe.ch0.input"
```

The parser rejects unknown roles, wrong prefixes, leading-zero aliases,
out-of-range channel numbers, and a name supplied under the wrong declared
vocabulary. It never guesses whether a string is legacy or canonical.

## 4. Compatibility behavior

The frozen `telemetry_to_measurements()` API continues to emit its historical
legacy names. Its signature, record IDs, values, units, status, quality, and
provenance are unchanged. Future AFE serial-profile integration will cross the
explicit mapping boundary before using canonical adapter/workflow channel names.

This avoids two unsafe outcomes:

1. old reports or golden data changing without a version migration;
2. configuration code relying on an undocumented string replacement.

## 5. Evidence boundary

Host tests cover every role in both vocabularies, channel boundaries, invalid
names, typed modes, legacy telemetry preservation, explicit conversion, and
alignment with Simulator names. This proves deterministic software mapping
only. It does not prove that a physical channel is wired correctly, measured in
millivolts, or connected to any AFE/controller.
