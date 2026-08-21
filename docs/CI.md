# Continuous integration

[中文](CI_ZH.md)

The [`ESP-IDF examples`](../.github/workflows/esp-idf-examples.yml) workflow is
the repository's compile gate. It runs for every pull request, every push to
`main`, and manual dispatches. It does not flash hardware or publish firmware.

## Change routing

| Change | Actions behavior |
| --- | --- |
| Direct example source under `examples/esp-idf/<project>/` | Build that project and its applicable conditional lanes |
| Workflow, CI helper, CI test, or `config/ci/` change | Build the complete matrix |
| Markdown or the two reviewed documentation assets only | Run preflight checks with a docs-only assertion; create no ESP-IDF build jobs |
| Governance templates, license, or ignore rules only | Run preflight checks without claiming a docs-only diff; create no ESP-IDF build jobs |
| Markdown-audit policy or another unclassified non-document path | Report the path and run the complete matrix conservatively |
| Checked-in factory firmware | Run preflight checks and flag release-owner review; do not treat the binary as an example |
| Other unclassified path | Report the path and run the complete matrix conservatively |
| Initial/recreated push with an all-zero base SHA | Run the complete matrix instead of inspecting only the tip commit |
| Empty or unreadable Git diff | Fail the routing job instead of guessing |

Renames are classified from both the old and new path. Pull requests compare
the base commit to the pull-request head commit, not to GitHub's synthetic merge
commit. Direct project discovery intentionally stops at one level, so vendored
component test applications are not promoted to product examples.

## Build matrix

The default matrix compiles all 12 product examples with ESP-IDF `v5.5.5` and
`v6.0.2`, producing 24 jobs. A full source-impact run also contains 17 focused
jobs:

Every product `sdkconfig.defaults` is Rev3.x by default, and every default lane
also appends `config/ci/rev3_x.defaults` as an explicit CI assertion. The
explicit `config/ci/rev1_3.defaults` overlay remains runnable for Rev1.3:
from an example directory run
`idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;../../../config/ci/rev1_3.defaults" build`.
It selects the older P4 revision and 200 MHz PSRAM. BSP Registry release `1.0.1`,
published from PR #191, lets ESP-IDF choose the matching MIPI PHY reference
clock for each profile. All seven BSP manifests use the exact online version
`==1.0.1`; a full source-impact run therefore validates the current managed
dependency. These builds remain compile evidence rather than physical-board
timing or touch validation.

- 2 ES7210-to-ES8311 echo jobs for example 06, one on each ESP-IDF version;
- 12 RGB888 jobs for examples 07 through 12 on both ESP-IDF versions;
- 1 AI-enabled Brookesia job for example 11 on ESP-IDF `v5.5.5` only;
- 2 USB-minimal jobs with HID touch and UAC audio disabled for example 12.

That makes 41 ESP-IDF build jobs in a complete matrix. The audio echo overlay
compiles the board's ES7210 microphone and ES8311 speaker path on both supported
ESP-IDF lines. The Brookesia AI overlay compiles the optional AI dependency path
only on `v5.5.5`: the GMF 0.6.x AI components call `idf_build_set_property` at
the top level of their CMake files, which ESP-IDF v6.0 rejects during its early
`component_get_requirements` pass, so the lane stays v5-only until the coherent
GMF set is upgraded (see [components](COMPONENTS.md)). The product default keeps
AI disabled to bound runtime resources. The overlays in
[`config/ci/`](../config/ci/) are appended after each project's
`sdkconfig.defaults`; they exist only to compile conditional paths and are not
factory firmware configurations. The USB-minimal lane keeps UAC audio disabled;
`usb_device_uac` is downloaded but linked only when UAC audio is enabled. Older
IDF build graphs can still compile its unlinked target. After top-level
`project()` creates managed component targets, a `TARGET` guard gives only that
UAC target a private TinyUSB audio definition. It does not enable product
descriptors or app audio.

All product defaults keep bootloader logging at `WARN`. This preserves the
existing partition layout while keeping the Rev3.x QIO bootloader inside the
`0x6000` region before the partition table at `0x8000`; application logging is
unchanged.

## CI firmware artifacts

After each successful build lane, Actions packages the build's generated
`flasher_args.json` and uploads one ZIP named for its project, ESP-IDF version,
and variant. The package is a diagnostic example-CI artifact, not a release.
It is tied to the pull-request head SHA (or push SHA), contains checksums and
manifest-derived offsets, and is retained only for a limited period. See
[CI firmware artifacts](CI_FIRMWARE.md) for the guarded local test flow.

## Evidence boundary

A green workflow proves that the selected source and configuration resolved its
dependencies and compiled in the official ESP-IDF CI container for target
`esp32p4`. It does not prove:

- that the checked-in factory binary was rebuilt from this source;
- successful flashing, boot, peripheral timing, radio behavior, or long-run
  stability;
- camera, display, audio, USB, storage, or touch behavior on physical hardware;
- factory release packaging, offsets, or upgrade compatibility.

Those claims require separate hardware or release evidence tied to the exact
commit and board revision.

## Arduino examples

The separate Arduino workflow uses Arduino-ESP32 `3.3.11` with the valid P4
`ChipVariant=postv3` FQBN and discovers one canonical sketch in each directory
below `examples/arduino/examples/`. Its bundled P4 libraries are
`REV_MIN_301`/200 MHz PSRAM, so this workflow requires Rev3.1 or newer and does
not claim Rev3.0 or the ESP-IDF 250 MHz profile. On pull requests and pushes a
sketch-local source change selects that sketch, while the shared display
library or Arduino workflow/discovery contract selects all ten. Documentation-
only and ESP-IDF-only changes keep the preflight job but create no Arduino
compile jobs; an unclassified Arduino path conservatively selects all ten.
Manual dispatch can select one sketch or all ten. Arduino-only source paths do
not select the ESP-IDF matrix. The repository makes no CAN or RS485 hardware
claim.

The workflow installs only the pinned Arduino-ESP32 core. Arduino_GFX `1.6.0`,
LVGL `9.3.0`, the full LVGL configuration, and the board display/touch adapter
are retained under `examples/arduino/libraries/` and are passed to every compile
with `--libraries`; CI does not replace them with Library Manager downloads.
