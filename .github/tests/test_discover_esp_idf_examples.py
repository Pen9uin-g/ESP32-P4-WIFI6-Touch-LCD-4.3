from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "discover_esp_idf_examples.py"
SPEC = importlib.util.spec_from_file_location("discover_esp_idf_examples", SCRIPT)
assert SPEC and SPEC.loader
discover = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = discover
SPEC.loader.exec_module(discover)


class DiscoveryTests(unittest.TestCase):
    def test_only_direct_product_projects_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "examples" / "esp-idf" / "01_demo"
            nested = direct / "components" / "vendored" / "test_apps"
            firmware = root / "firmware" / "not_a_product_example"
            for project in (direct, nested, firmware):
                (project / "main").mkdir(parents=True)
                (project / "CMakeLists.txt").touch()

            self.assertEqual(discover.list_examples(root), ["examples/esp-idf/01_demo"])

    def test_docs_only_route_has_no_builds(self) -> None:
        route = discover.classify_paths(["README.md", "docs/CI_ZH.md"], {"examples/esp-idf/01_demo"})
        self.assertTrue(route.docs_only)
        self.assertEqual(route.kind, "docs")
        self.assertEqual(route.selected, ())

    def test_firmware_is_reported_but_not_built(self) -> None:
        route = discover.classify_paths(
            ["firmware/factory.bin"], {"examples/esp-idf/01_demo"}
        )
        self.assertEqual(route.kind, "firmware")
        self.assertTrue(route.firmware_changes)
        self.assertTrue(route.release_review)
        self.assertEqual(route.selected, ())

    def test_direct_example_selects_only_its_parent(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(
            ["examples/esp-idf/02_demo/main/app.c"], known
        )
        self.assertEqual(route.selected, ("examples/esp-idf/02_demo",))

    def test_global_ci_input_selects_all(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(["config/ci/rgb888.defaults"], known)
        self.assertEqual(route.kind, "global")
        self.assertEqual(route.selected, tuple(sorted(known)))

    def test_unknown_path_selects_all_conservatively(self) -> None:
        known = {"examples/esp-idf/01_demo", "examples/esp-idf/02_demo"}
        route = discover.classify_paths(["tools/new-generator.py"], known)
        self.assertEqual(route.kind, "unknown")
        self.assertEqual(route.unknown_paths, ("tools/new-generator.py",))
        self.assertEqual(route.selected, tuple(sorted(known)))

    def test_empty_diff_fails_closed(self) -> None:
        with self.assertRaises(discover.RoutingError):
            discover.classify_paths([], {"examples/esp-idf/01_demo"})

    def test_rename_routes_both_old_and_new_paths(self) -> None:
        self.assertEqual(
            discover.paths_from_name_status(["R100\told.md\tdocs/new.md"]),
            ["docs/new.md", "old.md"],
        )

    def test_full_matrix_has_default_and_conditional_lanes(self) -> None:
        self.assertEqual(discover.DEFAULT_IDF_VERSIONS, ("v5.5.5", "v6.0.2"))
        examples = [
            f"examples/esp-idf/{name}"
            for name in (
                "01_HowToCreateProject",
                "02_HelloWorld",
                "03_i2c_tools",
                "04_wifistation",
                "05_sdmmc",
                "06_I2SCodec",
                "07_Displaycolorbar",
                "08_lvgl_demo_v9",
                "09_video_lcd_display",
                "10_mp4_player",
                "11_esp_brookesia_phone",
                "12_usb_extend_screen",
            )
        ]
        matrix = discover.build_matrix(examples)["include"]
        self.assertEqual(len(matrix), 39)
        self.assertTrue(all(item["artifact_name"].startswith("firmware-esp-idf-") for item in matrix))
        self.assertEqual(len({item["artifact_name"] for item in matrix}), 39)
        self.assertEqual(sum(item["variant"] == "default" for item in matrix), 24)
        self.assertEqual(sum(item["variant"] == "rgb888" for item in matrix), 12)
        self.assertEqual(sum(item["variant"] == "ai" for item in matrix), 1)
        self.assertEqual(sum(item["variant"] == "minimal" for item in matrix), 2)
        self.assertEqual(
            [item["idf_version"] for item in matrix if item["variant"] == "ai"], ["v5.5.5"]
        )
        self.assertFalse(
            any(
                item["variant"] == "ai" and item["idf_version"] == "v6.0.2"
                for item in matrix
            )
        )


if __name__ == "__main__":
    unittest.main()
