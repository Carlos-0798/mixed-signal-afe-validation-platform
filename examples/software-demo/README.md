# Reproducible software demo

From an installed base package, run:

```powershell
analog-validation demo --output .\analog-validation-demo
```

The command creates a new directory containing deterministic JSON/CSV results,
a self-contained HTML report, SVG, clean replay and intentional-fault replay
examples, and SHA-256 manifests. It refuses to replace an existing directory.

The workflow uses deterministic `SYNTHETIC` observations and the same reviewed
application service, formal DC analysis, acceptance criteria, result export, and
reporting path used by the CLI and Dashboard. It opens no serial port, sends no
application bytes, performs no network operation, and does not validate AFE
hardware.

Exact expected hashes are frozen in
[`test-data/golden/phase5_demo_v1.json`](../../test-data/golden/phase5_demo_v1.json).
