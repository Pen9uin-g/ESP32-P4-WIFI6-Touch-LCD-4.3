#!/usr/bin/env python3
"""Run repository tests from the non-package .github directory."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def main() -> int:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        module_name = f"repository_tests_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if not spec or not spec.loader:
            raise RuntimeError(f"Unable to load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        suite.addTests(loader.loadTestsFromModule(module))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
