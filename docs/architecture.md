# Software Phase 1 architecture

The AFE Validation Platform is the product. It is not an accessory or subordinate module of the MSP430 Equipment Health Controller. The analog base unit must operate without a microcontroller; optional controllers and host adapters automate it through versioned public interfaces.

```text
Independent AFE Base Unit
  +-- manual configuration and analog/digital outputs
  +-- optional Reference Validation Controller
  +-- optional MSP430 / other 3.3 V MCU integration
  +-- controller-neutral Python Host Software
```

```text
Synthetic tool / future adapter
            |
            v
 analog_validation.protocol  ---> versioned AFE v1 records
            |
            v
 analog_validation.domain    ---> provenance / capability / TestRun
            |
            +----> future adapters and runners
            +----> future CLI / Dashboard / reports
```

`src/analog_validation/` is the only formal product core. An executable architecture test rejects third-party, serial, GUI, board-SDK, `dashboard`, or `tools` imports from that package. The remaining `dashboard/measurements/` files are explicitly legacy Phase 0 analysis algorithms awaiting Software Phase 3 migration; they are not dependencies of the formal core.

Hardware, reference-controller firmware, integration profiles, and host tools are separate boundaries. Firmware remains a later-phase placeholder. Public integration with the independent MSP430 project is one future supported profile, limited to documented protocol and electrical interfaces; no application code, ownership, or product identity is shared. See `PRODUCT_ARCHITECTURE.md`.
