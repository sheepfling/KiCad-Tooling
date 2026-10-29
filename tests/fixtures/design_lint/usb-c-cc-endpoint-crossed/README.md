# Crossed USB-C CC endpoint fixtures

These are minimal synthetic KiCad schematics for the `bus.usb_c_cc_endpoint_crossed`
review heuristic. They contain only synthetic schematic data.

- `fault.kicad_sch` swaps the connector-side CC1/CC2 net labels relative to the
  controller functions. Source SHA-256:
  `64171977c2fe6012b153a351453a87bdf6122a5a5b95baefab69a14a167a5b4e`.
- `control.kicad_sch` connects matching CC1 and CC2 roles directly. Source
  SHA-256:
  `9782df476a406bdbb8f353c0b700e7b41e2d34cdd7279497c53685f8b544e7d0`.

The native fixture lane exports each schematic twice with digest-pinned KiCad
10.0.0 and 10.0.5 images, checks exact pin functions and net assignments,
requires no ERC errors, and compares normalized netlists and lint findings.
The fault is a deterministic prompt for review, not an assertion that all
crossed CC mappings are incorrect.
