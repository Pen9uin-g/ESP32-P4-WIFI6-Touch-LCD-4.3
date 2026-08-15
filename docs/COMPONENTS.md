# Component and dependency boundaries

[中文](COMPONENTS_ZH.md)

This repository mixes product code with local board support, upstream-derived
sources, managed dependencies, and one prebuilt component. Treating every
`components/` directory as removable or registry-owned is unsafe.

| Area | Classification | Maintenance boundary |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | Example-local source | Provides the SD test glue used by example 05; keep it with that example |
| `12_usb_extend_screen/components/bsp_extra` | Product application extension | Exposes board-specific codec, player, and file APIs used by example 12; do not replace it with the base BSP alone |
| Base `esp32_p4_wifi6_touch_lcd_4_3` dependency in examples 06–12 | Pinned upstream source | Every base-BSP manifest resolves the reviewed upstream commit `ac94f5da7c0e44963828ab970337e89d23e04330` from [upstream PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191), rather than a local copy or registry release |
| Example 11 Brookesia components | Vendored/local integration | `brookesia_core` and the Squareline application are intentionally resolved by local paths; nested test apps are not product CI projects |
| `10_mp4_player/components/esp_extractor` | Prebuilt vendor component | Target-specific static libraries are required by the player; source and complete provenance are not present here |
| Dependencies declared in `idf_component.yml` | Managed or Git dependency | Actions resolves each declared Registry or Git source; generated `managed_components/` trees are not repository source |

Example 10 constrains `espressif/esp_audio_codec` to versions from 2.3 up to,
but not including, 2.6. Version 2.6 and newer require ESP32-P4 silicon revision
3.0, while this product's checked-in defaults intentionally support earlier P4
revisions. Keep this upper bound until the supported hardware floor changes.

Example 11's Brookesia AI path is compiled with both ESP-IDF `v5.5.5` and
`v6.0.2`. Its conditional manifest rules resolve the coherent GMF 0.6 dependency
set whenever AI is enabled. GMF 0.6 lacks the newer keep-awake API, so the
speaking timer and state flow do not call that unavailable function. Only
AI-enabled `brookesia_core` C++ sources add `-fpermissive` for the GMF 0.6 C
headers; default and non-AI profiles do not receive that flag. Any future GMF
upgrade must keep the API-coupled dependency set coherent and validate both IDF
lines rather than partially advancing one component.

Example 12 downloads `usb_device_uac` 1.2.0 but marks it non-required. Its
component link is enabled only with UAC audio, allowing the minimal HID/display
configuration to resolve without an unconditional UAC build dependency. Older
IDF can still compile the downloaded target. After top-level `project()` creates
managed component targets, a `TARGET` guard applies a private TinyUSB audio
definition only to that UAC target; the product descriptor and app remain
disabled.

The example 12 `bsp_extra` tree remains a local product application extension.
It is not a substitute for the base BSP and is intentionally retained while the
base BSP resolves from the pinned upstream source. Example 08 calls no extension
API, so its unused copy and audio dependencies are removed. The pin is an
upstream review commit, not an ESP Component Registry release; no registry
release is used for this base BSP yet.

After upstream review, resolve and compile the affected examples, then complete
the post-HIL sequence on product hardware: boot the board, verify the 480 × 800
display and GT911 touch, exercise audio and SDIO, and run the applicable USB or
video path. Record that hardware evidence separately from Actions results
before advancing the pin or proposing a registry release.

Do not replace or redistribute the `esp_extractor` archives under a new license
assumption. Any provenance or licensing change needs source-origin and rights
confirmation from the maintainer. This document records technical boundaries;
it is not a third-party license grant.
