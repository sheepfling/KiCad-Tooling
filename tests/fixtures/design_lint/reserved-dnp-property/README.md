# Reserved DNP property fixtures

These small tooling-owned schematics are synthetic and not for manufacture.
The fault cases place an ordinary lowercase `dnp` property on J1. One case is
fitted with a custom value of `yes`; the other is natively DNP with a custom
value of `no`. KiCad 10.0.0, 10.0.5, and 10.0.8 exports confirm the user field
collides with native netlist metadata: the custom-only value was previously
misread as DNP, while the native marker plus custom field produced repeated
`dnp` properties. Controls cover an ordinary fitted symbol, a native DNP
symbol, and a library-definition-only `dnp` field.
