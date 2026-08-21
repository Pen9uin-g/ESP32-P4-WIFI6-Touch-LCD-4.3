from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "discover_arduino_examples.py"
SPEC = importlib.util.spec_from_file_location("discover_arduino_examples", SCRIPT)
assert SPEC and SPEC.loader
discover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discover)


class ArduinoDiscoveryTests(unittest.TestCase):
    @staticmethod
    def create_inventory(root: Path) -> None:
        for name in discover.EXPECTED_EXAMPLE_NAMES:
            directory = root / "examples/arduino/examples" / name
            directory.mkdir(parents=True)
            (directory / f"{name}.ino").touch()

    def test_discovers_reviewed_ten_example_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inventory(root)
            result = discover.list_examples(root)
            self.assertEqual(len(result), 10)
            self.assertEqual(result[0], "examples/arduino/examples/01_HelloWorld")
            self.assertEqual(result[-1], "examples/arduino/examples/10_Mic_Record")

    def test_missing_or_noncanonical_sketch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inventory(root)
            sketch = root / "examples/arduino/examples/04_LVGLV9_Arduino/04_LVGLV9_Arduino.ino"
            sketch.unlink()
            with self.assertRaisesRegex(ValueError, "canonical"):
                discover.list_examples(root)

    def test_matrix_contains_core_and_p4_fqbn(self) -> None:
        result = discover.matrix(["examples/arduino/examples/01_HelloWorld"], "3.3.11", "esp32:esp32:esp32p4")
        self.assertEqual(result["include"][0]["core"], "3.3.11")
        self.assertEqual(result["include"][0]["fqbn"], "esp32:esp32:esp32p4")

    def test_selector_accepts_name(self) -> None:
        examples = ["examples/arduino/examples/01_HelloWorld"]
        self.assertEqual(discover.select("01_HelloWorld", examples), examples)

    def test_build_routing_selects_one_sketch_and_skips_docs(self) -> None:
        examples = [
            f"examples/arduino/examples/{name}"
            for name in discover.EXPECTED_EXAMPLE_NAMES
        ]
        self.assertEqual(discover.select_for_paths([
            "examples/arduino/examples/03_Drawing_board/03_Drawing_board.ino",
        ], examples), ["examples/arduino/examples/03_Drawing_board"])
        self.assertEqual(discover.select_for_paths([
            "examples/arduino/README.md",
            "examples/arduino/libraries/displays/README.md",
            "examples/esp-idf/02_HelloWorld/main/hello_world_main.c",
        ], examples), [])

    def test_shared_or_unknown_arduino_code_builds_all(self) -> None:
        examples = [
            f"examples/arduino/examples/{name}"
            for name in discover.EXPECTED_EXAMPLE_NAMES
        ]
        for path in (
            "examples/arduino/libraries/displays/gt911.cpp",
            ".github/workflows/arduino-examples.yml",
            "examples/arduino/unclassified.txt",
        ):
            self.assertEqual(discover.select_for_paths([path], examples), examples)

    def test_missing_or_zero_push_base_builds_all(self) -> None:
        examples = [
            f"examples/arduino/examples/{name}"
            for name in discover.EXPECTED_EXAMPLE_NAMES
        ]
        self.assertEqual(discover.select_for_refs(None, "HEAD", examples), examples)
        self.assertEqual(
            discover.select_for_refs("0" * 40, "HEAD", examples),
            examples,
        )

    def test_rename_routing_retains_old_and_new_paths(self) -> None:
        paths = discover.paths_from_name_status([
            "R100\texamples/arduino/examples/01_HelloWorld/01_HelloWorld.ino\tdocs/old-example.ino",
        ])
        examples = [
            f"examples/arduino/examples/{name}"
            for name in discover.EXPECTED_EXAMPLE_NAMES
        ]
        self.assertEqual(
            discover.select_for_paths(paths, examples),
            ["examples/arduino/examples/01_HelloWorld"],
        )


if __name__ == "__main__":
    unittest.main()
