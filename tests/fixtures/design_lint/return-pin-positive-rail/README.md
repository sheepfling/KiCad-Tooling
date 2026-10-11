# Connector return pin on a positive rail

These are tooling-owned synthetic schematics. They are not copied from a
customer board and are not suitable for manufacture.

The fault assigns J1 pins 1 and 2, whose native symbol functions are `GND`, to
`+5V`. J2 keeps its return pins on `GND`. The control assigns the return pins
of both connectors to `GND`. The lint asks for review; it does not infer that
the connector pins must be joined, prove rail potential, or establish PCB or
off-board continuity.

The connector-return native fixture lane exports both sources twice with the
digest-pinned KiCad 10.0.0 and 10.0.5 images. The source hashes are:

| Case    | SHA-256                                                            |
| ------- | ------------------------------------------------------------------ |
| Fault   | `1837bf8f8cec031d5dff5fb7ddb65ad59f87fdf7aa80706d142b969c7fc8a967` |
| Control | `9584fbcc1f0560ac66306691f49d161617199b240cb7520588ad298a69b72176` |

The fault must produce `connector.return_pin_on_positive_rail` for J1.1 and
J1.2; the common-return control must not produce that rule.
