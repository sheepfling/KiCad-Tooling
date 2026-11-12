# Embedded and placed symbol pin-number fixtures

These schematics are tooling-owned synthetic regressions. The multi-unit
control and fault were derived from this directory's existing synthetic
single-unit fixture; they contain no product-board or customer source.

The multi-unit symbols define separate pin-bearing groups for units 1 and 2.
The placed J1 instance selects unit 2 and records pin 5. Its unit-2 embedded
definition also uses pin 5 in the control and pin 9 in the fault. Unit 1 has
pins 1, 2, and 4; unit 2 also has a pin 7 in alternate convert 2. Neither
group affects this convert-1 comparison. KiCad 10.0.5 exports `USB_GND` on
J1.5 for the multi-unit control and J1.9 for the fault.

The shared-unit fixtures add unit-0 pin 8 to unit 2's placed pin list and
connect it to `USB_SHARED`. The expected comparison includes pins 8 and 5
from unit 0 and unit 2, respectively; the convert-2 pin remains excluded.
KiCad 10.0.5 exports `USB_SHARED` on J1.8 in both cases, while the `USB_GND`
assignment changes from J1.5 to J1.9 in the fault.

| Fixture                              | SHA-256                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `control.kicad_sch`                  | `98e594b6c6f8941d9e0f778e838d61d6f1f38a48a8bc83bb9ce13725f73e89a6` |
| `fault.kicad_sch`                    | `03aa63be61f21145e4dcadd7c98d2656a342b042137d56b30879051b6d55d509` |
| `multi-unit-control.kicad_sch`       | `f123489bc9c2e7e70ae5bc6ba8b1c6937ced5647a2dd76814b3cbb2195a3846e` |
| `multi-unit-fault.kicad_sch`         | `2f16dd82c83d32578aeb944913095970c8bd5cbaf547e9cc355ce5ade76c5ada` |
| `shared-unit-zero-control.kicad_sch` | `b4332086458eed80f9f3a9d5648144eae4904342063bfa2cbb67f9e75a115a56` |
| `shared-unit-zero-fault.kicad_sch`   | `36e0c91985c2214e3f3a8e0f337b334005a09d23efd21b52ef66fe166ceb5919` |

The exact native experiment uses this digest-pinned KiCad 10.0.5 image:

```text
ghcr.io/kicad/kicad:10.0.5@sha256:fdcfa0e8d41f640d16edfb28e027fe8862ab31af9e45dcacbc662cec5c916e4c
```

It validates only these schematic sources and this KiCad image. It does not
validate datasheet pin mapping, electrical connectivity, footprint mapping, or
PCB copper continuity.
