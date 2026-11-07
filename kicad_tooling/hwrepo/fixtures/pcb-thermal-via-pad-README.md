# Synthetic thermal-pad via fixture

This board is a tooling-owned KiCad fixture. It contains one 3 mm square SMD
pad on `GND` and two through vias on the same net, both centered inside the
pad's copper shape. The native regression checks pad-component membership,
layer transition, count, and center-distance reporting. The fixture does not
represent a product board or certify thermal performance.
