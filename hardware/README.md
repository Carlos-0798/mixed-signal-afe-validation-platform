# Hardware status

**Current state:** deferred design preparation; no configurable AFE has been
purchased as a complete set, assembled, powered, or measured.

The software product can be evaluated without this directory. Simulator,
Replay, analysis, reporting, and public adapter work do not imply that a
breadboard, schematic, KiCad PCB, BOM, or datasheet set is hardware-verified.
The files below are planning artifacts for a later, separately gated hardware
program.

Planning artifacts:

- `bom/INDEPENDENT_PRODUCT_PROCUREMENT.md`: current frozen purchase plan for a controller-independent AFE product, including power, manual configuration, budget, and channels.
- `bom/independent-product-purchase.xlsx`: current linked, formula-driven purchase checklist; change status only after an item is actually ordered or received.
- `bom/independent-product-purchase.csv`: previous plain-CSV snapshot retained for traceability; the linked XLSX supersedes it for checkout.
- `bom/PROCUREMENT_PLAN.md`: historical reuse review and earlier staged-purchase analysis.
- `bom/procurement-checklist.csv`: historical checklist retained for traceability; superseded for new orders.

Before any purchase or construction, the owner must reconfirm available
components, instruments, controller choice, power/protection design, budget,
and actual wiring. Before first power, the project requires a reviewed
schematic/net list, resistance checks, current limit, common-ground plan, and
stop conditions. Hardware evidence must be recorded separately from
`SYNTHETIC`, `HOST_TEST`, `CSV_REPLAY`, and `SPICE_*` results.

The MSP430 Equipment Health Controller is an independent peer product. Its
receive-only compatibility record does not validate the future AFE and does not
make either repository a subproject of the other.
