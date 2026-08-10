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
| Documentation, product assets, schematic, or templates only | Run preflight checks; create no ESP-IDF build jobs |
| Checked-in factory firmware | Run preflight checks and flag release-owner review; do not treat the binary as an example |
| Unclassified path | Report the path and run the complete matrix conservatively |
| Empty or unreadable Git diff | Fail the routing job instead of guessing |

Renames are classified from both the old and new path. Pull requests compare
the base commit to the pull-request head commit, not to GitHub's synthetic merge
commit. Direct project discovery intentionally stops at one level, so vendored
component test applications are not promoted to product examples.

## Build matrix

The default matrix compiles all 12 product examples with ESP-IDF `v5.5.5` and
`v6.0.2`, producing 24 jobs. A full source-impact run also contains 15 focused
jobs:

- 12 RGB888 jobs for examples 07 through 12 on both ESP-IDF versions;
- 1 AI-enabled Brookesia job for example 11 on ESP-IDF `v5.5.5`;
- 2 USB-minimal jobs with HID touch and UAC audio disabled for example 12.

That makes 39 ESP-IDF build jobs in a complete matrix. Brookesia AI is not
scheduled on ESP-IDF 6 because its current GMF 0.6 dependency set is not
compatible with the IDF 6 component-requirements pass; the IDF 6 default keeps
AI disabled. The overlays in
[`config/ci/`](../config/ci/) are appended after each project's
`sdkconfig.defaults`; they exist only to compile conditional paths and are not
factory firmware configurations. The USB-minimal lane keeps UAC audio disabled;
`usb_device_uac` is downloaded but linked only when UAC audio is enabled.

## Evidence boundary

A green workflow proves that the selected source and configuration resolved its
dependencies and compiled in the official ESP-IDF CI container for target
`esp32p4`. It does not prove:

- that the checked-in factory binary was rebuilt from this source;
- successful flashing, boot, peripheral timing, radio behavior, or long-run
  stability;
- camera, display, audio, USB, storage, or touch behavior on physical hardware;
- release packaging, offsets, or upgrade compatibility.

Those claims require separate hardware or release evidence tied to the exact
commit and board revision.
