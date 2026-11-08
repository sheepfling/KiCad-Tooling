# PCB alternate-net reference fixture

This tooling-owned KiCad 10 board contains one synthetic `DATA` track and two
non-overlapping filled-zone outlines on the adjacent back copper layer. The
`GND` zone ends before most of the route; the `VCC` zone covers a portion of
the route. It exercises project-opt-in review for alternate-net coverage.

The board was derived from the tooling-owned narrow-void reference fixture and
contains no product project or proprietary board data.

- SHA-256: `bbf656775e95405e508e451577f464686983c8988c6bf48b4e93a381a963ec86`
- Expected observation: native KiCad refill reports both `GND` and `VCC` zones
  on `B.Cu`; a mapped `DATA` track on `F.Cu` has nonzero `VCC` centerline
  coverage on adjacent `B.Cu`.
- Limits: this is a geometry fixture, not an electrical design or endorsement
  that `GND` and `VCC` should be connected.
