# Component and dependency boundaries

[中文](COMPONENTS_ZH.md)

This repository mixes product code with local board support, upstream-derived
sources, managed dependencies, and one prebuilt component. Treating every
`components/` directory as removable or registry-owned is unsafe.

| Area | Classification | Maintenance boundary |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | Example-local source | Provides the SD test glue used by example 05; keep it with that example |
| `08_lvgl_demo_v9/components/bsp_extra` and `12_usb_extend_screen/components/bsp_extra` | Product application extension | Exposes board-specific codec, player, and file APIs; do not replace with the base BSP alone |
| Local `esp32_p4_wifi6_touch_lcd_4_3` copies in examples 07–12 | Product BSP snapshot | Local resolution wins over a same-named managed dependency; retain until a registry release is proven API-, Kconfig-, and hardware-equivalent |
| Example 11 Brookesia components | Vendored/local integration | `brookesia_core` and the Squareline application are intentionally resolved by local paths; nested test apps are not product CI projects |
| `10_mp4_player/components/esp_extractor` | Prebuilt vendor component | Target-specific static libraries are required by the player; source and complete provenance are not present here |
| Dependencies declared in `idf_component.yml` | Managed dependency | Actions resolves them from the ESP Component Registry; generated `managed_components/` trees are not repository source |

The exact registry artifact corresponding to the local 4.3-inch BSP has not
been established as equivalent to this snapshot. A future migration must pin a
candidate, compare public headers and Kconfig, preserve the board's 480 × 800
ST7701/GT911/audio/SDIO behavior, and pass the complete Actions matrix before
the local copies are removed.

Do not replace or redistribute the `esp_extractor` archives under a new license
assumption. Any provenance or licensing change needs source-origin and rights
confirmation from the maintainer. This document records technical boundaries;
it is not a third-party license grant.
