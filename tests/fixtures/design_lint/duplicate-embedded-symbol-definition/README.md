# Duplicate embedded symbol definition fixture

This tooling-owned synthetic fixture is based on the USB schematic source-integrity fixture.
The fault source adds a second direct `Connector:USB_A` definition whose ground pin number
conflicts with the first definition. The control source contains one definition. The placed
J1 connector makes the duplicate ID relevant. These files are verification fixtures, not
manufacturing designs or evidence about any external project.
