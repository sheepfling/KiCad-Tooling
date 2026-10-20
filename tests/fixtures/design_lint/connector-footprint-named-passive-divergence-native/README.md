# Synthetic named passive connector divergence fixtures

These tooling-owned schematics exercise a review heuristic for explicitly named
passive contacts on comparable connector peers. The fault assigns J1.1 and J2.1
to different synthetic nets while pins 2 share a separate common anchor. The
control assigns both named contacts to one net. The pair is synthetic and is
not derived from any product board or project source.

| Fixture             | Passive contact assignment      | Anchor          | Expected result |
| ------------------- | ------------------------------- | --------------- | --------------- |
| `fault.kicad_sch`   | `AUX_DETECT_A` / `AUX_DETECT_B` | `COMMON_ANCHOR` | `REVIEW`        |
| `control.kicad_sch` | shared `AUX_DETECT`             | `COMMON_ANCHOR` | no lint finding |

A matching function name, passive electrical type, footprint, value, pin
inventory, and common anchor are review clues. They do not prove that the
assignments are wrong or that the nets should be joined. Separate passive
domains can be intentional. The check does not establish PCB copper
continuity.

SHA-256 source digests:

- `fault.kicad_sch`: `ff33080326c28271c1a0efa214dd788288800695cba6b8fd4865ebf1b587a32b`
- `control.kicad_sch`: `0c8a06ee56f2e058cb58b3515ff7f65f95c8df457dfc4ab9d87bdb40ff501aa7`

The hosted native lane exports each schematic repeatedly with the digest-pinned
KiCad 10.0.0 and 10.0.5 images. Generated receipts stay under ignored `build/`
directories.
