# CI firmware artifacts

[中文](CI_FIRMWARE_ZH.md) · [CI guide](CI.md)

The ESP-IDF workflow creates one temporary, flashable diagnostic package for
each of its 39 matrix lanes. It is built from the lane's real
`flasher_args.json`; it is never a replacement for the immutable factory image
under [`firmware/`](../firmware/).

## Prerequisites and selection

Use a clean, non-detached local branch with exactly one open, non-draft pull
request whose head is the complete local SHA. The tool accepts only a successful
`esp-idf-examples.yml` run at that exact SHA and downloads only the exact
artifact name for the selected lane. It verifies that the ZIP has one manifest,
that identity fields, checksums, file sizes, offsets, and non-overlapping flash
ranges match the selected lane, and that all ranges remain within 32 MiB.

On Windows, run:

```text
Flash-CI-Firmware.cmd -Port COMx
```

`-ListOnly` lists all 39 lanes without contacting GitHub or hardware. `-SelfTest`
runs only local safety checks. If `-Port` is omitted, the tool fills it only
when exactly one Plug and Play display name contains both `CH343` and `COM`;
otherwise pass `-Port COMx` yourself.

## Guided hardware test

The tool uses `esp32p4`, 921600 baud, and manifest-derived write arguments. A
lane is considered flashed only when esptool exits successfully and prints
`Hash of data verified`. It then requires an explicit manual PASS confirmation
after you test the board before advancing to the next lane. Progress is saved
under the final SHA, so a new SHA starts a new test sequence.

Do not use this flow to flash, replace, infer offsets for, or validate the
checked-in factory/recovery firmware. Factory firmware has separate ownership,
release evidence, and recovery instructions.
