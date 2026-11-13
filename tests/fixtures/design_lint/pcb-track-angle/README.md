# Synthetic track-angle DRC fixtures

These small tooling-owned boards exercise KiCad's per-net `track_angle`
constraint. The fault board contains a 135-degree connected segment corner on
`CLOCK_OUT`, below the authored 150-degree minimum. The control replaces the
diagonal segment with a collinear continuation. Both use the same project
settings and `.kicad_dru` rule.

The native fixture test repeats DRC for both boards with the digest-pinned KiCad
10.0.0 and 10.0.5 images. It requires the fault to report `track_angle`, the
control to omit it, and all other reported violation types to match. This
verifies the native constraint behavior on these fixtures; it does not select a
universal routing policy or establish a real board's electrical requirements.

Fixture SHA-256 values:

| File                | SHA-256                                                            |
| ------------------- | ------------------------------------------------------------------ |
| `board.kicad_dru`   | `99b0a40eb14c8d9e2fe188a7239c6654b3b9738df33bb10d2e0b7ffc03d52cdf` |
| `board.kicad_pro`   | `8a425ec5146b893183eb7105d263ccab994c53d1775d8385e42407ca5bdb741d` |
| `control.kicad_pcb` | `a988582d101df640ed0b47135b66710679341490d60ee64580203957b4bbb554` |
| `fault.kicad_pcb`   | `f29c496bbda3f760a9deef763b045b1555d5fa2bcd8633b55842303ab6967f22` |
