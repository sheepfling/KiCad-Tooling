# Capacitor hold-up native fixture

These two schematics are tooling-owned synthetic inputs. They test the
project-authored nominal-capacitance estimate using a one-farad capacitor,
5 V starting voltage, 3 V minimum load voltage, and 1 A constant-current
load. The control meets the 2,000 ms limit exactly. The fault changes the
native value to 1 mF while retaining the mapped part identity, so both the
component-value mismatch and the below-minimum estimate remain visible.

The fixture tests source-bound KiCad 10 exports only. It does not model a real
storage circuit or establish electrical adequacy.

| Case                      | SHA-256                                                            |
| ------------------------- | ------------------------------------------------------------------ |
| `control.kicad_sch`       | `1b845d0d869a300c8bb5ba2ebd703b1df767d6355b70c66fb928b2d5bfbac1db` |
| `below-minimum.kicad_sch` | `7dacdde5769904e4f0e0912f734ed55983c9afafdb3e51b5d1bcb582ac1da283` |
