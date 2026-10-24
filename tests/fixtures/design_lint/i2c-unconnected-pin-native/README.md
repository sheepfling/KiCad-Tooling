# Synthetic partial I2C pair fault and control

These tooling-owned schematics exercise one bounded case: a fitted component
has exactly one recognized SDA and one recognized SCL function, one pin is
assigned to a native net, and the other has an explicit no-connect marker. The
control assigns both pins to separate nets. The lint remains default-off and
does not infer that every named I2C pair is required.

The exact KiCad 10.0.0 and 10.0.5 lane exports each schematic twice, checks the
normalized netlist and ERC evidence, then evaluates the typed design-lint
finding with explicit `review` mode. These fixtures contain no product board
or project data.
