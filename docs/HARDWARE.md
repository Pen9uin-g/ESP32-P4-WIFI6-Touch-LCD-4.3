# Schematic-backed hardware audit

[中文](HARDWARE_ZH.md)

This audit compares the checked-in
[schematic](../schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf) with the
reviewed upstream BSP source pinned by examples 06–12. It is a repository review,
not a substitute for checking the physical board revision.

## Confirmed product interfaces

| Function | Schematic / BSP result |
| --- | --- |
| Main and wireless processors | ESP32-P4 application processor plus ESP32-C6-MINI-1 wireless coprocessor |
| External flash | U10 is GD25Q256, a 256-Mbit (32 MB) NOR device; all product example defaults select 32 MB |
| Display | 4.3-inch 480 × 800 ST7701, 2-lane MIPI-DSI; backlight GPIO26 and LCD reset GPIO27 |
| Touch | GT911 on I2C; SCL GPIO8, SDA GPIO7, touch reset GPIO23 |
| Audio | ES8311 codec, ES7210 input front end, NS4150B amplifier; MCLK GPIO13, SCLK GPIO12, LRCK GPIO10, DOUT GPIO9, DIN GPIO11, PA enable GPIO53 |
| MicroSD | SDMMC D0/D1/D2/D3 GPIO39/40/41/42, CMD GPIO44, CLK GPIO43 |
| USB | Separate USB high-speed OTG and USB-to-UART paths are present |

## Items deliberately not changed by this audit

- The schematic exposes a `TP_INT` net while the current BSP configures the
  GT911 interrupt pin as not connected. The extracted schematic text does not
  prove the complete net-to-GPIO mapping, so changing the driver would be an
  unsupported hardware assumption.
- The schematic contains three key components, while the BSP advertises zero
  buttons and defines no button GPIO API. Exposing them requires a product-level
  behavior decision and physical validation.
- Actions compilation cannot validate MIPI timing, camera signal integrity,
  touch interrupts, audio routing, SDIO communication, or USB electrical behavior.

These open items should be resolved from the source design/netlist and a known
board revision, then validated on hardware before BSP capability flags or pins
are changed.
