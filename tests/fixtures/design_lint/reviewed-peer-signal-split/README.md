# Reviewed connector peer signal split

`peers.kicad_sch` contains two different tooling-owned connector symbols: a
USB-like port contact `J1.2` and a serial-like port contact `J2.7`. Their
generic native pins use separate nets. A complete source-matched interface map
that places both contacts in one reviewed peer group and maps them to
`UART_RX` in the same voltage domain produces a configurable review prompt.
Mapping the contacts to distinct signals is the valid control over the same
native export.

The peer group and matching map names are review scope only. They do not prove
the contacts must be common, or establish external wiring or PCB copper
continuity. The fixture contains no product or customer design.

Source SHA-256:

- `peers.kicad_sch`: `1f755fc59dfd41d6e337f8e58f64cb605e351fe862035b91893a9c5827302193`

The exact-version lane repeats the native netlist export with digest-pinned
KiCad 10.0.0 and 10.0.5 images and checks the normalized typed-netlist hash.
