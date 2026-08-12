# Contributing

[中文](CONTRIBUTING_ZH.md)

Thanks for improving the ESP32-P4-WIFI6-Touch-LCD-4.3 repository. Keep changes
scoped to this product and preserve the distinction between product examples,
local components, managed dependencies, and the checked-in factory image.

## Before opening a pull request

1. Start from the current `main` branch and keep unrelated work out of the
   change.
2. Identify the affected example, hardware revision, ESP-IDF version, and any
   required accessory.
3. Update first-party English and Simplified-Chinese documentation together.
4. Run the dependency-free checks when Python is available:

   ```console
   python .github/tests/run_tests.py
   python .github/scripts/check_repository.py
   ```

5. Let GitHub Actions provide the authoritative ESP-IDF compile result for the
   committed pull-request head.

## Repository boundaries

- Direct children of `examples/esp-idf/` are product examples. Nested projects
  inside vendored components are not separate product deliverables.
- Do not commit generated `build/`, `managed_components/`, `sdkconfig`, or
  dependency-resolution output.
- The base BSP manifests intentionally pin the upstream review commit in
  [PR #191](https://github.com/waveshareteam/Waveshare-ESP32-components/pull/191).
  Do not substitute a registry release or recreate a local base BSP copy. Keep
  the two product-local `bsp_extra` extensions and follow the review and HIL
  sequence in [Component and dependency boundaries](docs/COMPONENTS.md).
- Do not replace, repackage, or relabel the factory binary without reproducible
  source provenance, flash layout and offset documentation, a checksum, and
  release-owner approval.
- Never include credentials, private URLs, local filesystem paths, device
  identifiers, or private serial logs in commits or issue reports.

## Pull-request evidence

Describe what changed, why it is appropriate for this exact product, which
Actions run validates the final commit, and what still requires physical-board
testing. A green compile matrix must not be presented as proof of flashing or
runtime hardware behavior.

For a base BSP pin update, include the reviewed upstream commit and pull request,
then record the post-HIL evidence separately after the affected hardware paths
have been exercised. Do not claim a Component Registry release until one exists.

Use the repository pull-request template and keep fixes minimal when an Actions
job exposes a version-specific API or dependency problem.
