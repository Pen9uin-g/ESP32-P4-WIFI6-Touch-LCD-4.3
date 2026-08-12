from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class CiFirmwareContractTests(unittest.TestCase):
    def test_workflow_uploads_the_exact_matrix_package(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "esp-idf-examples.yml").read_text(encoding="utf-8")
        for required in (
            "actions/upload-artifact@v4",
            "PACKAGE_GIT_SHA: ${{ github.event.pull_request.head.sha || github.sha }}",
            '--variant "${{ matrix.variant }}"',
            "name: ${{ matrix.artifact_name }}",
            "path: ci-firmware/${{ matrix.artifact_name }}.zip",
            "if-no-files-found: error",
        ):
            self.assertIn(required, workflow)
        self.assertEqual(
            workflow.count("ref: ${{ github.event.pull_request.head.sha || github.sha }}"),
            2,
            "discover and build must check out the SHA embedded in the package manifest",
        )

    def test_launcher_and_flasher_keep_p4_safety_contract(self) -> None:
        launcher = (ROOT / "Flash-CI-Firmware.cmd").read_text(encoding="utf-8")
        flasher = (ROOT / "scripts" / "Flash-CI-Firmware.ps1").read_text(encoding="utf-8")
        self.assertIn("-NoProfile -ExecutionPolicy Bypass", launcher)
        self.assertIn("ci_firmware.py", flasher)
        core = (ROOT / "scripts" / "ci_firmware.py").read_text(encoding="utf-8")
        for required in ("esp32p4", "MAX_FLASH_BYTES", "Hash of data verified", "manual-confirmation", "lanes=39", "extract_zip_safely", "source_project", "validate_args", "run_sha"):
            self.assertIn(required, core)


if __name__ == "__main__":
    unittest.main()
