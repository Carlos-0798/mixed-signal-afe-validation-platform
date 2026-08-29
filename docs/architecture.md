# Phase 0 architecture

The AFE Validation Platform is the product. It is not an accessory or subordinate module of the MSP430 Equipment Health Controller. The analog base unit must operate without a microcontroller; optional controllers and host adapters automate it through versioned public interfaces.

```text
Independent AFE Base Unit
  +-- manual configuration and analog/digital outputs
  +-- optional Reference Validation Controller
  +-- optional MSP430 / other 3.3 V MCU integration
  +-- controller-neutral Python Host Software
```

```text
Synthetic source or future UART
            |
            v
 dashboard.protocol  ---> validated AFE CSV frames
            |
            +----> measurements.dc_sweep (linear fit and saturation exclusion)
            +----> measurements.hysteresis (transition thresholds)
            +----> future dashboard/reporting
```

Hardware, reference-controller firmware, integration profiles, and host tools are separate boundaries. Firmware is a Phase 1+ placeholder. Public integration with the independent MSP430 project is one supported profile, limited to documented protocol and electrical interfaces; no application code, ownership, or product identity is shared. See `PRODUCT_ARCHITECTURE.md`.
