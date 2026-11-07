# Synthetic two-pin I3C connector return review

These tooling-owned, minimal schematics exercise a two-contact generic connector
assigned to exact native I3C SDA/SCL pin-function nets. The fault uses generic
connector pin functions; the control names both connector signals. They test a
review prompt only and do not define a universal I3C return requirement.

The native fixture lane exports both sources twice with the digest-pinned
KiCad 10.0.0 and 10.0.5 images selected by the synthetic template project.
