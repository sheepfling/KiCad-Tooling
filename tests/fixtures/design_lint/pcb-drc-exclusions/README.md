# Synthetic PCB DRC exclusions

These settings fragments exercise the KiCad 10.0 per-violation DRC exclusion
review. Their marker IDs, positions, UUIDs, and comments are synthetic. They are
not copied from a product or customer project and do not model a real board.

- `fault.kicad_pro` contains two persisted exclusion records: an unconnected
  items record without a comment and a clearance record with a comment.
- `control.kicad_pro` contains an empty exclusion list.

The linter reports stored exclusions for review. It does not assert that a
current board still has the excluded violation or that the exclusion is wrong.
