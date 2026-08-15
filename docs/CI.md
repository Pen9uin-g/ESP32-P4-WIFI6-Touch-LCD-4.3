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
| Empty or unreadable Git diff | Fail the routing job instead of guessing |

Renames are classified from both the old and new path. Pull requests compare
the base commit to the pull-request head commit, not to GitHub's synthetic merge
commit. Direct project discovery intentionally stops at one level, so vendored
component test applications are not promoted to product examples.

## Build matrix

The default matrix compiles all 12 product examples with ESP-IDF `v5.5.5` and
`v6.0.2`, producing 24 jobs. A full source-impact run also contains 17 focused
jobs:

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
