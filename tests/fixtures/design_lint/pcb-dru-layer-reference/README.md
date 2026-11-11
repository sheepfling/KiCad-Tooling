# Custom DRC layer-reference fixtures

These files contain tooling-owned synthetic KiCad custom-rule inputs. They
contain no product project or board data. The faults cover board display-name
aliases, an unrecognized layer name, and a known copper layer absent from the
probe board's saved two-layer inventory. The control uses canonical copper
layer names.

The advisory flags display aliases even though a default KiCad 10.0.8 native
probe accepted the tested silkscreen spelling. It requests stable file-format
names because board aliases can depend on local board names and setup. An
absent inner layer can be intentional for another stackup. The unknown-name
native result is specific to the digest-pinned KiCad 10.0.8 trial and does not
claim identical behavior for every KiCad version or project setup.
