# Synthetic SPI clock/control same-net fixtures

These tooling-owned schematics use one fitted synthetic SPI device with native
COPI, CIPO, SCK, and NSS function pins. `fault.kicad_sch` assigns SCK and COPI
to one native schematic net; `clock-select-fault.kicad_sch` assigns SCK and NSS
to one net; `control.kicad_sch` keeps all four functions on separate nets. No
product or cohort schematic is included. Generic SPI pins use passive electrical
types so native ERC does not report un-driven inputs in this isolated
connectivity fixture.

The default-off lint asks for review because a symbol's function names do not
prove its configured mode or whether a pin has been multiplexed. It does not
instruct that nets be joined or separated.

The native fixture lane exports each schematic and ERC report twice using
digest-pinned KiCad 10.0.0 and 10.0.5 images. It verifies both exact fault
assignments, the shared control, stable normalized netlists, one matching rule
prompt per fault, quiet cross-controls, and no native ERC errors. Receipts
remain under ignored `build/` directories.
