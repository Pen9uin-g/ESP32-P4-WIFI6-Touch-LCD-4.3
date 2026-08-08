from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_repository.py"
SPEC = importlib.util.spec_from_file_location("check_repository", SCRIPT)
assert SPEC and SPEC.loader
checks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checks
SPEC.loader.exec_module(checks)


class RepositoryCheckTests(unittest.TestCase):
    def test_markdown_targets_ignore_fenced_examples(self) -> None:
        text = "[real](docs/CI.md)\n```md\n[example](missing.md)\n```\n"
        self.assertEqual(checks.markdown_targets(text), ["docs/CI.md"])

    def test_local_link_check_reports_only_missing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "exists.md").write_text("ok", encoding="utf-8")
            (root / "README.md").write_text(
                "[ok](docs/exists.md) [web](https://example.com) [bad](missing.md)",
                encoding="utf-8",
            )
            errors = checks.local_link_errors(root)
            self.assertEqual(errors, ["README.md: missing local link target 'missing.md'"])

    def test_markdown_inventory_ignores_generated_trees(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "managed_components" / "vendor").mkdir(parents=True)
            (root / "docs" / "README.md").touch()
            (root / "managed_components" / "vendor" / "README.md").touch()
            self.assertEqual(
                [path.relative_to(root).as_posix() for path in checks.markdown_files(root)],
                ["docs/README.md"],
            )


if __name__ == "__main__":
    unittest.main()
