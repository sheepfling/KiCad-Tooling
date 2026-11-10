# Reviewed peer power-output open fixtures

These synthetic schematics exercise
`connector.reviewed_peer_power_output_open`. They use unlike connector symbols,
distinct values and footprints, `power_out` pins named VBUS and VDD_OUT, and
current source-matched output maps in one reviewed peer group. `fault.kicad_sch`
leaves J1.1 without a net while J2.1 is assigned; `control.kicad_sch` assigns
both contacts to one common net.

The open contact has no authored unconnected reason in the synthetic map. The
rule reports REVIEW only; it does not require a connection, select the peer's
net as a target, or claim that PCB copper is continuous. These tooling-owned
fixtures do not reproduce a product schematic.

The native test exports both schematics twice with digest-pinned KiCad 10.0.0
and 10.0.5 Docker images, checks normalized netlist repeatability, then
evaluates the current source-matched maps.

SHA-256 source digests:

- `fault.kicad_sch`: `9decb551ed29ee2a92f7909ae5066fe8d9f0ac7f4118dff04c484b05f7b8152d`
- `control.kicad_sch`: `a3e5a9915ae3b3192730100e45835cb1ceb16606b380d286b06c0e2fbc83b380`
