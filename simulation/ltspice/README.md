# LTspice organization

`netlists/` contains Phase 0 idealized, reproducible `.cir` checks. Future schematic sources (`.asc`), vendor macromodels, and model licenses should be separated into named subdirectories rather than overwriting these ideal references.

Generated `.raw` and working `.log` files are ignored. Curated text summaries may be placed in `../expected-results/` with the LTspice version, command, input-file hash, model provenance, and evidence label `SPICE_IDEAL` or `SPICE_COMPONENT_MODEL`.

Run one netlist from PowerShell, adjusting the executable path if necessary:

```text
& "$env:LOCALAPPDATA\Programs\ADI\LTspice\LTspice.exe" -b .\simulation\ltspice\netlists\buffer_ideal.cir
```

See `TASKS.md`. A successful idealized check is not a hardware validation.

