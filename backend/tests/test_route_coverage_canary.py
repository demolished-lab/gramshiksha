"""Two guards against the failure mode the production audit actually found.

1. Mount parity. Every router is included twice — bare (for the dev proxy) and
   under /api (what production serves). Nothing enforces that a route added to
   one registration also exists on the other, which would quietly 404 in
   production while every local test stayed green.

2. Endpoint coverage. The audit found 21 of 63 endpoints had no test at all and
   the gap was invisible because nothing counted. These tests parse the test
   suite with `ast` (so f-string templates like f"/courses/{cid}" become
   "/courses/{}") and assert that every registered method+path is called
   somewhere. Adding a route without adding a test now fails CI.

The parser deliberately counts *mentions*, not executions: it is a cheap
tripwire, not a coverage tool. It cannot prove an assertion exists behind the
call — but it does prove nobody shipped an endpoint that no test ever names.
"""
import ast
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app

TESTS_DIR = Path(__file__).parent
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
IGNORED_METHODS = {"HEAD", "OPTIONS"}


def registered_routes():
    """[(methods, bare_path), ...] for app-level and router routes."""
    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue  # docs/openapi/mounts are not part of the API surface
        methods = {m for m in (route.methods or set()) if m not in IGNORED_METHODS}
        path = route.path
        if path.startswith("/api/"):
            continue  # twin of the bare route; checked by mount parity instead
        if methods:
            out.append((methods, path))
    return out


def _string_template(node) -> str | None:
    """Source shape of a string expression: f"/a/{x}/b" -> "/a/{}/b"."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def _calls_in(path: Path) -> set[tuple[str, str]]:
    """(HTTP_METHOD, "/path/{}") for every client.<verb>(...) literal call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        verb = node.func.attr
        if verb.upper() not in HTTP_METHODS or not node.args:
            continue
        template = _string_template(node.args[0])
        if template and template.startswith("/"):
            found.add((verb.upper(), template))
    return found


def _matches(template: str, path: str) -> bool:
    """Does the source template "/courses/{}" satisfy the route "/courses/{id}"?"""
    if template == path:
        return True
    pattern = "".join(
        r"[^/]+" if part.startswith("{") and part.endswith("}") else re.escape(part)
        for part in re.split(r"(\{[^}]+\})", path)
    )
    return re.fullmatch(pattern, template) is not None


@pytest.fixture(scope="module")
def called_endpoints() -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for test_file in sorted(TESTS_DIR.glob("test_*.py")):
        seen |= _calls_in(test_file)
    return seen


def test_api_twin_mount_parity():
    """Every bare route must also exist under /api, with the same methods."""
    by_path = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = {m for m in (route.methods or set()) if m not in IGNORED_METHODS}
        by_path.setdefault(route.path, set()).update(methods)

    bare = {p: m for p, m in by_path.items() if not p.startswith("/api/")}
    twins = {p[4:]: m for p, m in by_path.items() if p.startswith("/api/")}

    assert bare and twins, "expected both bare and /api registrations"
    only_bare = sorted(p for p in bare if p not in twins)
    only_api = sorted(p for p in twins if p not in bare)
    mismatched = sorted(p for p in bare if p in twins and bare[p] != twins[p])
    assert not only_bare, f"registered bare but missing from /api: {only_bare}"
    assert not only_api, f"registered under /api but missing bare: {only_api}"
    assert not mismatched, f"method sets differ between mounts: {mismatched}"


def test_every_endpoint_is_called_by_a_test(called_endpoints):
    """No registered method+path may be absent from the test suite."""
    missing = []
    for methods, path in sorted(registered_routes()):
        for verb in sorted(methods):
            if not any(method == verb and _matches(template, path)
                       for method, template in called_endpoints):
                missing.append(f"{verb} {path}")
    assert not missing, (
        "endpoints with no test calling them "
        f"({len(missing)} of {sum(len(m) for _, m in registered_routes())}): "
        + ", ".join(missing)
    )
