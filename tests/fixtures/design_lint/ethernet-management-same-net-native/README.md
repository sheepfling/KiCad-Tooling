# Ethernet management MDC/MDIO same-net fixtures

These source-hashed schematics are synthetic tooling fixtures. They use native
MDC and MDIO pin functions based on the public [TI DP83826E/DP83826I
datasheet](https://www.ti.com/lit/gpn/DP83826I); they contain no project or
customer design data.

- `control.kicad_sch` assigns MDC and MDIO to distinct neutral nets.
- `fault.kicad_sch` assigns both exact native pins to `MII_MANAGEMENT`.

Reviewed SHA-256 values:

- `control.kicad_sch`: `82e11329b60720420e3a3fab66dc44eaa389cad5e495e31afd57622a252ea795`
- `fault.kicad_sch`: `a556ce7d31c1157efbc6ae2bb49f703b73d42aa91c6d042f392372c3eee1430b`

The native lane exports both schematics twice with digest-pinned KiCad 10.0.0
and 10.0.5 images. It compares repeatable normalized netlists, exact pin
functions and assignments, a quiet distinct-net control, and one localized
same-net REVIEW finding. The container has no network access and mounts only
these synthetic schematics and an output directory.
