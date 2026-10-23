# Synthetic SPI clock/control same-net fixtures

These tooling-owned schematics use one fitted synthetic SPI device with native
COPI, CIPO, SCK, and NSS function pins. The fault assigns SCK and COPI to one
native schematic net; the control assigns them to separate nets. Both also
retain separate CIPO and chip-select nets. No product or cohort schematic is
included. Generic SPI pins use passive electrical types so native ERC does not
report un-driven inputs in this isolated connectivity fixture.

The default-off lint asks for review because a symbol's function names do not
prove its configured mode or whether a pin has been multiplexed. It does not
instruct that nets be joined or separated.

The native fixture lane exports each schematic and ERC report twice using
digest-pinned KiCad 10.0.0 and 10.0.5 images. It verifies the fault/control net
assignments, stable normalized netlists, one fault prompt, a quiet control, and
no native ERC errors. Receipts remain under ignored `build/` directories.
