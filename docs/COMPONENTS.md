# Component and dependency boundaries

[中文](COMPONENTS_ZH.md)

This repository mixes product code with local board support, upstream-derived
sources, managed dependencies, and one prebuilt component. Treating every
`components/` directory as removable or registry-owned is unsafe.

| Area | Classification | Maintenance boundary |
| --- | --- | --- |
| `05_sdmmc/components/sd_card` | Example-local source | Provides the SD test glue used by example 05; keep it with that example |
| `12_usb_extend_screen/components/bsp_extra` | Product application extension | Exposes board-specific codec, player, and file APIs used by example 12; do not replace it with the base BSP alone |
| Base `esp32_p4_wifi6_touch_lcd_4_3` dependency in examples 06–12 | Published managed BSP | All seven base-BSP manifests select exact Registry release `1.0.1`, published from [upstream PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191). It contains the revision-aware MIPI PHY clock update and no-INT/RST GT911 probing |
| Example 11 Brookesia components | Vendored/local integration | `brookesia_core` and the Squareline application are intentionally resolved by local paths; nested test apps are not product CI projects |
| `10_mp4_player/components/esp_extractor` | Prebuilt vendor component | Target-specific static libraries are required by the player; source and complete provenance are not present here |
| Dependencies declared in `idf_component.yml` | Managed or Git dependency | Actions resolves each declared Registry or Git source; generated `managed_components/` trees are not repository source |

Example 10 constrains `espressif/esp_audio_codec` to versions from 2.3 up to,
but not including, 2.6. Version 2.6 and newer require ESP32-P4 silicon revision
3.0, while the explicit Rev1.3 compatibility profile still supports earlier P4
silicon. Keep this upper bound until that compatibility requirement changes.

Example 11's Brookesia AI path compiles on ESP-IDF `v5.5.5` only. Its conditional
manifest rules resolve the coherent GMF 0.6 dependency set whenever AI is
enabled on that line. The GMF 0.6.x AI components call `idf_build_set_property`
at the top level of their CMake files; ESP-IDF v6.0 rejects that call during its
early `component_get_requirements` pass, so the AI overlay is not a v6 lane yet.
GMF 0.6 also lacks the newer keep-awake API, so the speaking timer and state flow
do not call that unavailable function. Only AI-enabled `brookesia_core` C++
sources add `-fpermissive` for the GMF 0.6 C headers; default and non-AI profiles
do not receive that flag. Any future GMF upgrade must keep the API-coupled
dependency set coherent, restore the v6 AI lane, and validate both IDF lines
rather than partially advancing one component.

Example 12 downloads `usb_device_uac` 1.2.0 but marks it non-required. Its
component link is enabled only with UAC audio, allowing the minimal HID/display
configuration to resolve without an unconditional UAC build dependency. Older
IDF can still compile the downloaded target. After top-level `project()` creates
managed component targets, a `TARGET` guard applies a private TinyUSB audio
definition only to that UAC target; the product descriptor and app remain
disabled.

The example 12 `bsp_extra` tree remains a local product application extension.
It is not a substitute for the base BSP and is intentionally retained while the
base BSP resolves from Registry release `1.0.1`. Example 08 calls no extension
API, so its unused copy and audio dependencies are removed. The published BSP
uses ESP-IDF's revision-aware MIPI PHY clock selection and probes GT911 at
`0x5D` and `0x14` with both INT and RST unassigned. Its ST7701 and GT911
dependencies are already published upstream components, so no separate LCD
driver PR is required for this product fix.

The release and product migration sequence for this update is:

1. merge component/BSP PR #191 after its component CI passes;
2. publish `waveshare/esp32_p4_wifi6_touch_lcd_4_3` version `1.0.1` to the ESP
   Component Registry;
3. replace all seven Git/path mappings in a separate product commit with the
   exact Registry version `==1.0.1` and enforce that mapping in repository tests;
4. resolve the online component and rebuild every applicable ESP-IDF lane at
   the final product commit.

Every future BSP update must follow the same order: publish first, then update
the product in a separate commit. Do not replace the exact Registry release with
a Git/path address or an unpublished semantic version; those overrides must not
enter the product manifests.

Registry resolution and compile validation are not hardware-in-the-loop (HIL)
evidence. On product hardware, boot the board, verify the 480 × 800 display and
GT911 touch, exercise audio and SDIO, and run the applicable USB or video path.
Record that evidence separately from Actions results before treating the
dependency update as hardware-qualified.

Do not replace or redistribute the `esp_extractor` archives under a new license
assumption. Any provenance or licensing change needs source-origin and rights
confirmation from the maintainer. This document records technical boundaries;
it is not a third-party license grant.
