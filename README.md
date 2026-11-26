# EENOUR BLE Probe

Probe integration for reverse-engineering the EENOUR P2001 PLUS (G2) BLE protocol.
Connects to the unit, dumps its GATT table, logs all notifications, and exposes an
`eenour_probe.write` service for protocol experiments.
