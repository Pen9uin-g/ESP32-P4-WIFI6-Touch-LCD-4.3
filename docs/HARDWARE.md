# Schematic-backed hardware audit

[中文](HARDWARE_ZH.md)

This audit compares the checked-in
[schematic](../schematic/ESP32-P4-WIFI6-Touch-LCD-4.3-schematic.pdf), the product
configuration, and the reviewed BSP update in
[upstream PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191).
The product manifests must remain on their temporary reviewed source pin until
that BSP is published in the ESP Component Registry. This is a repository
review, not a substitute for checking the physical board revision.

## Confirmed product interfaces

| Function | Schematic / BSP result |
| --- | --- |
| Main and wireless processors | ESP32-P4 application processor plus ESP32-C6-MINI-1 wireless coprocessor |
| External flash | U10 is GD25Q256, a 256-Mbit (32 MB) NOR device; all product example defaults select 32 MB |
| Display | 4.3-inch 480 × 800 ST7701, 2-lane MIPI-DSI; backlight GPIO26 and LCD reset GPIO27 |
| Touch | GT911 on I2C; SCL GPIO8 and SDA GPIO7. The reviewed BSP update and Arduino adapter assign neither INT nor RST and probe `0x5D`, then `0x14`, for polling operation |
| Audio | ES8311 codec, ES7210 input front end, NS4150B amplifier; MCLK GPIO13, SCLK GPIO12, LRCK GPIO10, DOUT GPIO9, DIN GPIO11, PA enable GPIO53 |
| MicroSD | SDMMC D0/D1/D2/D3 GPIO39/40/41/42, CMD GPIO44, CLK GPIO43 |
| USB | Separate USB high-speed OTG and USB-to-UART paths are present |

## Board revision and clock selection

The public schematic checked into this repository is labelled PCB `Rev1.2`; no
separate public Rev1.3/Rev3.x schematic was available during this audit. It
proves the common 40 MHz crystal and peripheral wiring, but not a PCB-level
difference between those two product revisions. The confirmed software and
silicon-profile differences are:

| Setting | Rev1.3 compatibility profile | Rev3.x default profile |
| --- | --- | --- |
| ESP-IDF minimum revision | `REV_MIN_100` with the pre-v3 selection | `REV_MIN_300` |
| CPU frequency selected by IDF defaults | 360 MHz | 400 MHz |
| PSRAM frequency used here | 200 MHz | 250 MHz |
| MIPI DSI PHY PLL reference | PLL_F20M, 20 MHz | 40 MHz XTAL |
| Panel link and pixel clock | 2 lanes × 500 Mbps; DPI 30 MHz | Same |
| ST7701 timing | 480 × 800; H 42/12/42; V 2/8/60 | Same |

`REV_MIN_100` is ESP-IDF's v1.0 floor and is the correct available selection
for a Rev1.3 board; `REV_MIN_1` means v0.1 and must not be used as a Rev1.3
profile. The BSP's MIPI bus sets the PHY clock source to zero so ESP-IDF chooses
PLL_F20M on pre-v3 silicon and XTAL on Rev3.x. The older
`MIPI_DSI_PHY_CLK_SRC_DEFAULT` compatibility macro always names PLL_F20M and can
abort during Rev3.x display initialization. The 30 MHz pixel clock and
576 × 870 total timing imply about 59.87 Hz in either profile. LDO channel 3 at
2.5 V is the DPHY supply, not a clock.

Arduino-ESP32 `3.3.11` is not equivalent to this ESP-IDF profile. Its valid
`ChipVariant=postv3` FQBN selects prebuilt libraries with
`CONFIG_ESP32P4_REV_MIN_301` and 200 MHz PSRAM. Use it only on P4 Rev3.1 or
newer; it does not cover Rev3.0 or the ESP-IDF 250 MHz PSRAM configuration.

## Items deliberately not changed by this audit

- The schematic exposes `TP_INT` and `TP_RST` nets, but the BSP update and
  Arduino adapter deliberately assign neither line. GT911 is polled after
  probing `0x5D` and `0x14`; adding either GPIO requires confirmed revision-
  specific wiring and hardware validation.
- The public product page and schematic identify no onboard CAN or RS485
  transceiver, bus connector, or verified transceiver pin map. The expansion
  header can be used with an externally wired physical layer, but no onboard
  CAN/RS485 example should be inferred from the ESP32-P4 peripheral alone.
- The schematic contains three key components, while the BSP advertises zero
  buttons and defines no button GPIO API. Exposing them requires a product-level
  behavior decision and physical validation.
- Actions compilation cannot validate MIPI timing, camera signal integrity,
  touch interrupts, audio routing, SDIO communication, or USB electrical behavior.

These open items should be resolved from the source design/netlist and a known
board revision, then validated on hardware before BSP capability flags or pins
are changed.
