#!/usr/bin/env python3
"""Discover first-party Arduino sketches and emit an Arduino build matrix."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path, PurePosixPath


ROOT = PurePosixPath("examples/arduino/examples")
ARDUINO_ROOT = PurePosixPath("examples/arduino")
LIBRARIES_ROOT = ARDUINO_ROOT / "libraries"
EXPECTED_EXAMPLE_NAMES = (
    "01_HelloWorld",
    "02_AsciiTable",
    "03_Drawing_board",
    "04_LVGLV9_Arduino",
    "05_GFX_ESPWiFiAnalyzer",
    "06_Camera_Preview",
    "07_Camera_ISP_Tuning",
    "08_SD_Card",
    "09_Audio_Playback",
    "10_Mic_Record",
)
GLOBAL_BUILD_PATTERNS = (
    ".github/workflows/arduino-examples.yml",
    ".github/scripts/discover_arduino_examples.py",
    ".github/tests/test_discover_arduino_examples.py",
)
ZERO_GIT_SHA = "0" * 40


def normalize_path(value: str) -> str:
    return PurePosixPath(value.strip().replace("\\", "/").strip("/")).as_posix()


def paths_from_name_status(lines: list[str]) -> list[str]:
    """Expand git name-status records, retaining both sides of renames."""
    paths: list[str] = []
    for line in lines:
        fields = line.split("\t")
        if len(fields) < 2:
            raise ValueError(f"malformed git diff record: {line!r}")
        status = fields[0]
        record_paths = fields[1:]
        if status.startswith(("R", "C")):
            if len(record_paths) != 2:
                raise ValueError(f"malformed rename/copy record: {line!r}")
        elif len(record_paths) != 1:
            raise ValueError(f"malformed git diff record: {line!r}")
        paths.extend(normalize_path(path) for path in record_paths)
    return sorted(dict.fromkeys(paths))


def changed_paths(base_ref: str | None, head_ref: str) -> list[str]:
    if base_ref:
        args = ["diff", "--name-status", "--find-renames", f"{base_ref}...{head_ref}"]
    else:
        args = [
            "diff-tree", "--root", "--no-commit-id", "--name-status",
            "--find-renames", "-r", head_ref,
        ]
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    paths = paths_from_name_status(result.stdout.splitlines())
    if not paths:
        raise ValueError("git diff produced no changed paths; refusing to guess Arduino scope")
    return paths


def select_for_paths(paths: list[str], examples: list[str]) -> list[str]:
    """Select changed sketches; shared or unknown Arduino code builds all."""
    known = set(examples)
    selected: set[str] = set()
    build_all = False
    for raw_path in paths:
        path = normalize_path(raw_path)
        if path.lower().endswith((".md", ".markdown")):
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in GLOBAL_BUILD_PATTERNS):
            build_all = True
            continue
        if path == LIBRARIES_ROOT.as_posix() or path.startswith(LIBRARIES_ROOT.as_posix() + "/"):
            build_all = True
            continue
        if path == ROOT.as_posix():
            build_all = True
            continue
        if path.startswith(ROOT.as_posix() + "/"):
            parts = PurePosixPath(path).relative_to(ROOT).parts
            candidate = (ROOT / parts[0]).as_posix()
            if candidate in known:
                selected.add(candidate)
            else:
                build_all = True
            continue
        if path == ARDUINO_ROOT.as_posix() or path.startswith(ARDUINO_ROOT.as_posix() + "/"):
            build_all = True
    return examples if build_all else [example for example in examples if example in selected]


def select_for_refs(base_ref: str | None, head_ref: str, examples: list[str]) -> list[str]:
    """Route a normal range; an absent/all-zero push base builds everything."""
    if not base_ref or base_ref == ZERO_GIT_SHA:
        return examples
    return select_for_paths(changed_paths(base_ref, head_ref), examples)


def list_examples(repo: Path = Path(".")) -> list[str]:
    root = repo / ROOT
    if not root.is_dir():
        raise ValueError(f"missing Arduino examples directory: {ROOT}")

    directory_names = tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))
    if directory_names != EXPECTED_EXAMPLE_NAMES:
        raise ValueError(
            "Arduino example directories must match the reviewed ten-example inventory: "
            + ", ".join(EXPECTED_EXAMPLE_NAMES)
        )

    result: list[str] = []
    for name in EXPECTED_EXAMPLE_NAMES:
        directory = root / name
        sketches = sorted(directory.glob("*.ino"))
        canonical = directory / f"{name}.ino"
        if sketches != [canonical]:
            raise ValueError(f"{ROOT / name} must contain exactly the canonical {name}.ino")
        result.append((ROOT / name).as_posix())
    return result


def select(value: str, examples: list[str]) -> list[str]:
    if value in ("", "all"):
        return examples
    normalized = value.strip().strip("/").replace("\\", "/")
    matches = [item for item in examples if item == normalized or PurePosixPath(item).name == normalized]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous Arduino example: {value}")
    return matches


def matrix(examples: list[str], core: str, fqbn: str) -> dict[str, list[dict[str, str]]]:
    return {"include": [{
        "path": item,
        "name": PurePosixPath(item).name,
        "core": core,
        "fqbn": fqbn,
    } for item in examples]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selector", default="all")
    parser.add_argument("--core", required=True)
    parser.add_argument("--fqbn", required=True)
    parser.add_argument("--base-ref")
    parser.add_argument("--head-ref")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    inventory = list_examples()
    examples = select(args.selector, inventory)
    if args.head_ref:
        examples = select_for_refs(args.base_ref, args.head_ref, inventory)
    payload = matrix(examples, args.core, args.fqbn)
    values = {"matrix": json.dumps(payload, separators=(",", ":")), "count": str(len(examples))}
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
    print(values["matrix"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
