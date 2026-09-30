"""CI tripwire for the commercial-rights license (see LICENSE).

If anyone -- a contributor, a bad merge, or even the repo owner -- deletes,
replaces, or weakens the license that reserves all money-making rights to
Pravesh Kumar, this test fails and the push goes red. Strengthening the text
is fine; only weakening it breaks the build.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_license.py"


def _load_check():
    namespace: dict = {"__name__": "license_guard", "__file__": str(SCRIPT)}
    exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), namespace)
    return namespace["check"]


def test_commercial_rights_license_intact():
    problems = _load_check()()
    assert not problems, (
        "LICENSE guard failed -- commercial rights must stay reserved "
        "exclusively to Pravesh Kumar: " + "; ".join(problems)
    )


def test_license_script_has_no_third_party_imports():
    """The CI `license` job runs with system Python and zero installs."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "import sys" in text and "from pathlib import Path" in text
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("import ", "from ")):
            assert line.split()[1].split(".")[0] in {"sys", "pathlib"}, (
                f"license script must stay stdlib-only, found: {line}"
            )
