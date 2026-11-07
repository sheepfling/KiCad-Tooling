# Generic JTAG connector fault and control

These are tooling-owned synthetic schematics, created from the tooling's
synthetic generic-header fixture and containing no project board or product
design. They exercise native KiCad XML export for the JTAG TCK/TMS review cue.

| Case                | SHA-256                                                            | Expected result                                                                               |
| ------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| `fault.kicad_sch`   | `814bef2ba33b6886936e3c7536c61b09f89d806a62c23c47a18065e7826461c7` | Generic connector pin 1 shares U1's TMS net and pin 2 shares U1's TCK net; one review prompt. |
| `control.kicad_sch` | `c29d130451022eb095d84fdb709ae7f3253124a23b9d1d3d6bff1378d91681bc` | Connector pins carry unrelated auxiliary nets; no JTAG association prompt.                    |

Each source is exported twice with digest-pinned KiCad 10.0.0 and 10.0.5
images. The check asks for connector association and a reviewed pinout; it does
not require all JTAG signals, grounds, or power contacts to be exposed and
does not prove PCB copper continuity.
