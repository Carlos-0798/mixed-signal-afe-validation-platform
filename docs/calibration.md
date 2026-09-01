# Calibration status

No hardware calibration has been performed. Software Phase 3 now contains a host-tested linear calibration model, but its tests use `SYNTHETIC` and `HOST_TEST` records only. The presence of coefficients does not make them instrument-traceable or safe to copy into firmware.

The formal software behavior is documented in [calibration-and-frequency-response.md](calibration-and-frequency-response.md). It fits `reference = scale × observed + offset`, freezes the coefficient identity/version and every included input reference, reports before/after errors, and creates derived Measurements without changing the original records.

A future bench calibration record must additionally include hardware revision, component population, instrument model, instrument verification/calibration status, supply and reference voltages, ambient conditions, raw ADC codes, unmodified measurements, fitting method, coefficients, residuals, and date. Only those future records may support physical calibration claims.
