"""Unit tests for the fork-watch helpers (pure functions only, no network)."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "watch_forks.py"


def _load():
    namespace: dict = {"__name__": "fork_watch", "__file__": str(SCRIPT)}
    exec(compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec"), namespace)
    return namespace


def test_next_link_picks_rel_next():
    fns = _load()
    header = (
        '<https://api.github.com/repositories/1/forks?page=2>; rel="next", '
        '<https://api.github.com/repositories/1/forks?page=5>; rel="last"'
    )
    assert fns["_next_link"](header) == (
        "https://api.github.com/repositories/1/forks?page=2"
    )
    assert fns["_next_link"]("") is None


def test_new_forks_reports_only_unreported():
    fns = _load()
    current = [{"full_name": "a/one"}, {"full_name": "b/two"}]
    assert fns["new_forks"](current, {"a/one"}) == [{"full_name": "b/two"}]
    assert fns["new_forks"](current, {"a/one", "b/two"}) == []
