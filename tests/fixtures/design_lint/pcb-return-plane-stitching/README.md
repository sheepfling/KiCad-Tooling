# Same-net planes without a copper stitch

These tooling-owned synthetic boards exercise the LINT-025 direct copper-path
contract when front and back return planes have the same KiCad net assignment.

| Board fixture                                                          | Physical path                                                               | Expected result |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------- | --------------- |
| `kicad_tooling/hwrepo/fixtures/pcb-return-unstitched-planes.kicad_pcb` | J1.1 is on the front plane and J2.1 is on the back plane; no via joins them | Contract `FAIL` |
| `kicad_tooling/hwrepo/fixtures/pcb-return-stitched-planes.kicad_pcb`   | One plated through via joins the same two filled planes                     | Contract `PASS` |

Both pads keep the same `RETURN` net assignment in both boards. Only the via changes. The pair is a
synthetic reproduction of the missing interlayer bond class described in the public
[cohort issue #3787](https://github.com/rjwalters/kicad-tools/issues/3787). No board source,
fixture, or analyzer code from that repository was copied.

The exact-image native lane verifies the zone layer and island observations,
pad-to-plane assignments, via geometry, stable repeat capture, and contract
outcome on KiCad 10.0.0 and 10.0.5. This proves the contract can detect the
stated synthetic copper break. It does not discover required paths without a
project-authored map, verify DRC results, infer a universal need to stitch
planes, establish manufactured continuity, or assess current capacity.
