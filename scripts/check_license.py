"""License guard: the commercial-rights protection must never be silently dropped.

The repo is public so the author can show it as work, but every money-making
right belongs exclusively to Pravesh Kumar (see LICENSE). This script fails
if the LICENSE file goes missing, is swapped for a permissive license, or
loses the exclusivity grant -- no matter who makes that change, including the
repo owner. Run in CI (.github/workflows/ci.yml, job `license`) and locally:

    python scripts/check_license.py

Stdlib only, so the CI job needs no dependencies installed.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Phrases that must survive in LICENSE (case-insensitive). Deliberately
# semantic, not a hash: strengthening the text is allowed, weakening fails.
REQUIRED_PHRASES = (
    "pravesh kumar",
    "exclusively",
    "commercial",
    "all rights reserved",
)

# Markers of permissive licenses that would hand commercial rights to everyone.
# If any of these appear in LICENSE, the exclusivity grant is void.
FORBIDDEN_MARKERS = (
    "mit license",
    "apache license",
    "gnu general public license",
    "gnu lesser general public license",
    "mozilla public license",
    "permission is hereby granted",
)

# README must keep pointing readers at the license.
README_REQUIRED = ("LICENSE", "Pravesh Kumar")


def check() -> list[str]:
    problems: list[str] = []
    lic = REPO_ROOT / "LICENSE"
    if not lic.is_file():
        return ["LICENSE file is missing at the repo root"]
    text = lic.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    for phrase in REQUIRED_PHRASES:
        if phrase not in lowered:
            problems.append(f"LICENSE no longer contains required phrase: {phrase!r}")
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            problems.append(
                f"LICENSE contains permissive-license marker {marker!r} "
                "which would grant commercial rights to everyone"
            )
    readme = REPO_ROOT / "README.md"
    if not readme.is_file():
        problems.append("README.md is missing")
    else:
        readme_text = readme.read_text(encoding="utf-8", errors="replace")
        for phrase in README_REQUIRED:
            if phrase not in readme_text:
                problems.append(f"README.md no longer mentions {phrase!r}")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("LICENSE GUARD FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("license guard: commercial rights reserved to Pravesh Kumar (OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
