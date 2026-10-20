# Footprint-alias mode-dependent named signal fixtures

These tooling-owned synthetic schematics exercise the default-review rule
`connector.footprint_named_signal_mode_dependent_open_outlier`. Distinct
synthetic connector symbols share the same value, footprint, complete two-pin
inventory, and native pin metadata. Pin 1 is a bidirectional `DATA_IO` contact;
pin 2 is a passive common anchor. The fault assigns `DATA_IO` on J1 and leaves
J2 open. The control assigns both contacts to one net.

The finding is only a review prompt. Similarity and the common anchor do not
prove the contacts share a role or must connect. The sources are not based on a
product board, project expectation, or cohort export.

SHA-256 source digests:

- `fault.kicad_sch`: `96314806f6a6b21e43c9de2b86754d6a9b6f9f15d8ed19b204c61415d9c40e49`
- `control.kicad_sch`: `6375edf7f06cd00f66fcbd8d19675f151c428ebf9114b04891e7b9aff8977e3b`
