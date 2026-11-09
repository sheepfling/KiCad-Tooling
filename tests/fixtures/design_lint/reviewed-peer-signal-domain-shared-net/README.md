# Reviewed peer signal on one net across mapped domains

`shared-net.kicad_sch` is a tooling-owned synthetic schematic with generic
contacts `J1.2` and `J2.7` from unlike USB-like and serial-like connector
symbols. Both contacts have the same native net. A complete source-matched map
that places them in one reviewed peer group, assigns the same signal name, and
declares different voltage-domain identifiers produces a configurable review
prompt. Mapping both contacts to the same domain is the valid control over the
same exact native export.

The domain identifiers are authored labels. They do not establish nominal
voltages or electrical incompatibility. The rule asks a reviewer to confirm
whether sharing one net is intended and compatible; this fixture contains no
product or customer design.

Source SHA-256:

- `shared-net.kicad_sch`: `0bb12e09a610f4e3255a0c84e7f7c6cdd2dd8ae41d9cc39a30537800bf37a36d`

The exact-version lane repeats the native netlist export with digest-pinned
KiCad 10.0.0 and 10.0.5 images and checks the normalized typed-netlist hash.

The same generic two-contact source also controls the separate
`connector.reviewed_peer_distinct_signals_shared_net` heuristic. Its synthetic
map assigns `UART_TX` and `UART_RX` to the two contacts in one reviewed peer
group and one exact voltage domain; because the native fixture joins them to
one net, the distinct-signal rule requests review. Assigning both contacts the
same mapped signal is the valid peer-sharing control. This reuses the native
source with a different authored map interpretation.
