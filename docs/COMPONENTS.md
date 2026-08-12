# Component and dependency boundaries

[中文](COMPONENTS_ZH.md)

This repository mixes product code with local board support, upstream-derived
sources, managed dependencies, and one prebuilt component. Treating every
`components/` directory as removable or registry-owned is unsafe.

| Area | Classification | Maintenance boundary |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | Example-local source | Provides the SD test glue used by example 05; keep it with that example |
| `08_lvgl_demo_v9/components/bsp_extra` and `12_usb_extend_screen/components/bsp_extra` | Product application extension | Exposes board-specific codec, player, and file APIs; do not replace with the base BSP alone |
| Base `esp32_p4_wifi6_touch_lcd_4_3` dependency in examples 07–12 | Pinned upstream source | Every base-BSP manifest resolves the reviewed upstream commit `ac94f5da7c0e44963828ab970337e89d23e04330` from [upstream PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191), rather than a local copy or registry release |
| Example 11 Brookesia components | Vendored/local integration | `brookesia_core` and the Squareline application are intentionally resolved by local paths; nested test apps are not product CI projects |
| `10_mp4_player/components/esp_extractor` | Prebuilt vendor component | Target-specific static libraries are required by the player; source and complete provenance are not present here |
| Dependencies declared in `idf_component.yml` | Managed or Git dependency | Actions resolves each declared Registry or Git source; generated `managed_components/` trees are not repository source |

Example 10 constrains `espressif/esp_audio_codec` to versions from 2.3 up to,
but not including, 2.6. Version 2.6 and newer require ESP32-P4 silicon revision
3.0, while this product's checked-in defaults intentionally support earlier P4
revisions. Keep this upper bound until the supported hardware floor changes.

Example 11's Brookesia AI path is compiled only with ESP-IDF `v5.5.5`. GMF 0.6
lacks the newer wake and keep-awake APIs used by Brookesia, so the speaking timer
and state flow do not call the unavailable keep-awake API. When the optional AI
framework is enabled, only `brookesia_core` C++ sources add `-fpermissive` for
GMF 0.6 C headers; default and non-AI profiles do not receive that flag. Keep AI
disabled on IDF 6 until the complete, API-coupled GMF dependency set can be
upgraded and validated together: the `gmf_ai_audio` 0.7.2 evidence applies only
to its trigger wake/sleep API and does not establish a keep-awake API or a safe
partial upgrade.

Example 12 downloads `usb_device_uac` 1.2.0 but marks it non-required. Its
component link is enabled only with UAC audio, allowing the minimal HID/display
configuration to resolve without an unconditional UAC build dependency. Older
IDF can still compile the downloaded target. After top-level `project()` creates
managed component targets, a `TARGET` guard applies a private TinyUSB audio
definition only to that UAC target; the product descriptor and app remain
disabled.

The two `bsp_extra` trees remain local product application extensions. They are
not substitutes for the base BSP and are intentionally retained while the base
BSP resolves from the pinned upstream source. The pin is an upstream review
commit, not an ESP Component Registry release; no registry release is used for
this base BSP yet.

After upstream review, resolve and compile the affected examples, then complete
the post-HIL sequence on product hardware: boot the board, verify the 480 × 800
display and GT911 touch, exercise audio and SDIO, and run the applicable USB or
video path. Record that hardware evidence separately from Actions results
before advancing the pin or proposing a registry release.

Do not replace or redistribute the `esp_extractor` archives under a new license
assumption. Any provenance or licensing change needs source-origin and rights
confirmation from the maintainer. This document records technical boundaries;
it is not a third-party license grant.
