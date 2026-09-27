# Connector return review

An ERC pass can leave connector returns on several valid schematic nets. The
tooling cannot infer whether those returns must be common, bonded at a defined
point, or isolated. Use an independently approved connector pinout to decide.
Project source, pinout requirements, and approvals stay in the project repository.

## Inspect an unreviewed netlist

From a project checkout, capture a fresh netlist with its catalogued exact KiCad
version:

```sh
kicad-team contract-coach --project-id <board-id> --capture --format text
```

The CLI and MCP contract coach report numbered sibling nets with return-like
names, such as `0V CTRL 1` / `0V CTRL 2` or `USB1_GND` / `USB2_GND`, along
with their observed pins. The hint is `UNREVIEWED`: similar names are a reason
to compare the approved pinout with the design, not evidence of a short or an
error. Capture writes only under the project's ignored `build/` directory. A
retained native summary can be inspected with
`--native-summary build/<run>/<board-id>/summary.json` after its source,
toolchain, and netlist hashes are checked.

Native PCB validation now exports the netlist even when the component contract
is empty. It still fails the empty contract and names any detected split returns
in the failure. The detection is deliberately narrow: numbered sibling nets
containing `0V`, `GND`, `VSS`, `RTN`, `RETURN`, or `GROUND` are candidates. A
number can also appear before the return token, as in `SERIAL_1_GND` or
`USB1_GND`. Compact port numbers are recognized only for `USB`, `UART`,
`SERIAL`, `PORT`, and `COM`; this avoids treating protocol names such as
`RS232_GND` and `RS485_GND` as two ports. The hint ignores `USB1_SHIELD` and
similar shield names. It can miss differently named returns and can flag
intentionally separate nets.

## Author the grounding requirement

In the project-owned electrical contract, a required `grounding` section lists
every reviewed ground domain and its exact schematic pins. For example, if an
approved pinout requires three hypothetical connector signal-ground pins
directly on `GND`, all three pins belong in that one domain:

```json
{
  "mode": "required",
  "basis": "Approved connector pinout revision and electrical-owner review",
  "domains": [
    { "net": "GND", "pins": ["J1.4", "J2.4", "J3.4"] }
  ]
}
```

This fragment assumes the example net has exactly those three pins. The pin
numbers are synthetic and are not a USB connector pinout. A real
contract must list *all* pins on each declared ground net and cover every
component with a ground pin or a reasoned `exempt_components` entry. Two
intentionally isolated returns need separate ground domains, each with the
approved pins and an explicit basis for their intended isolation. A specified
bond or net tie needs its own schematic and PCB review; net names alone do not
prove the bond or copper path. Connector shields need their own reviewed
requirement; a signal-ground rule does not silently include them.

The regression cases use synthetic source and requirements:

- Three port signal grounds must share `GND`. Separate `USB1_GND` through
  `USB3_GND` nets fail the exact `GND` pin check and request return-net review.
- Three port signal grounds must share `GND`, but only one port strays to
  `USB3_GND`. The exact pin check still fails even though the naming hint has
  no numbered sibling pair to report.
- Two serial returns must remain isolated. Separate, declared `SERIAL_1_GND`
  and `SERIAL_2_GND` domains pass both exact checks and return-net review.
- Two serial returns must share one net. The same separate nets fail the
  declared common domain.

These cases test the declared topology, not whether a particular protocol
requires common grounds or isolation in every design.

For a misleading return-like name that the approved pinout identifies as
something other than a ground return, use `reviewed_return_exceptions` with the
exact net name and a substantive reason. Do not use this field for an actual
ground return or a missing connector pin. Stale exceptions and nets
declared both as domains and exceptions fail validation.

Once grounding is configured, the native and electrical checks fail when a
numbered return net has neither a declared ground domain nor a reviewed
exception. The existing domain check also fails missing, extra, or ambiguously
connected pins. Run the selected native and electrical verification against the
exact source intended for release:

```sh
kicad-team verify --project <board-id> --depth electrical --format text
```

The schematic check does not establish PCB return continuity. Review connector
pads, planes, net ties, and the intended reference point on the PCB, then test
first-article continuity according to the approved pinout before production
acceptance.
