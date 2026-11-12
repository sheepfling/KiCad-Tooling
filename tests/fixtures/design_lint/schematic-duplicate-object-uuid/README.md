# Repeated schematic object UUID

This tooling-owned fixture isolates a source identity warning. The schematic
uses synthetic USB-A and controller symbols. The fault changes only the UUID
stored for placed connector pin 2, making it equal to the UUID on pin 1. The
embedded library definitions, component references, nets, and pin numbers stay
the same.

- `control.kicad_sch` (SHA-256
  `98e594b6c6f8941d9e0f778e838d61d6f1f38a48a8bc83bb9ce13725f73e89a6`): no
  repeated UUID finding.
- `fault.kicad_sch` (SHA-256
  `e21f43f0de09b16c190a45c2e6ac8d2937c016655252bc01d1a3a910ee35fabc`): one
  `schematic.duplicate_object_uuid` REVIEW candidate at J1 pin 1 and pin 2.

The predicate groups UUIDs within one source file at a time. It does not
compare separate files, which avoids comparing a reused hierarchical sheet
file against its own other sheet instances. It reports object kinds and source
lines but does not infer an electrical consequence or select which object
should retain the identifier.

The native compatibility lane exports both files using this digest-pinned
KiCad image:

```text
ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
```

Both exports returned success. Their parsed net assignments are identical,
including `USB_GND` on J1.4; source lint is quiet for the control and reports
one finding for the fault. This result is limited to a placed connector pin
UUID. These synthetic files contain no customer, cohort, or project source.

Run the native regression with:

```sh
KICAD_RUN_NATIVE_SCHEMATIC_SYMBOL_INTEGRITY_FIXTURES=1 \
  .venv/bin/python -I -m pytest \
  tests/test_schematic_duplicate_object_uuid_native.py \
  -m 'design_lint and schematic_lint and evidence_lint and native_kicad and design_lint_rule(rule_id="schematic.duplicate_object_uuid")'
```
