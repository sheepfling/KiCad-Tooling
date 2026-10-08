# Synthetic USB-C CC role-map coverage fixtures

These tooling-owned schematics verify native CC pin-function export and the
USB-C role-map coverage prompt. They are not a connector pinout, USB-C
implementation, or product design.

## Source identity

- `connector.kicad_sch` SHA-256:
  `42935f2e21f3b86acc33a87916072b466d5c75b61cddd472a40fb6219d59ce9a`
- The source and sink topology controls are shared with the
  [cohort comparison fixtures](../cohort-usb-c-roles/README.md):
  `source-rp-control.kicad_sch` SHA-256
  `b9913fa1e44adaaa3837257dc0756bcb39411b9bb79dcd1568c1a264248a1f8f` and
  `sink-rd-control.kicad_sch` SHA-256
  `5ac40420e4adcc7f2005e1808f1ebdeb765fd4907113bfa5be657407d2d6d789`.
- KiCad schematic format: `20231120`
- Source contains no proprietary project material.

## Expected behavior

- With no authored USB-C port role map, native KiCad exports both pin
  functions, and `bus.usb_c_unreviewed_port` reports `J1` at `REVIEW`.
- The same role-map prompt remains on the 56 kΩ source and 5.1 kΩ sink CC
  topology controls when neither has a project role record. Their resistor
  values and net assignments are checked so the controls cannot silently
  become incomplete or unknown-role cases.
- With a synthetic role map listing `J1`, this coverage prompt is suppressed.
  The unit tests separately cover a mapped connector plus an unmapped peer,
  DNP and non-connector exclusions, incomplete pin-function controls, and
  review/block/off/exact-ignore decisions.
- The map membership prompt does not validate source/sink role, Rp/Rd values,
  controller behavior, VBUS, ground, protection, or physical continuity.

The digest-pinned native fixture lane exports all three sources twice against
each project-selected KiCad 10.0.0 and 10.0.5 image. It checks the native pin
functions, source/sink resistor topology, role-map prompts, and mapped control.
The source is mounted read-only; only the generated output directory is
writable. Receipts remain under ignored `build/ci/` paths.
