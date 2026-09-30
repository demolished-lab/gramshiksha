"""Weekly fork watch: file one tracking issue per new public fork.

Why: the repo is public but all commercial rights belong exclusively to
Pravesh Kumar (see LICENSE). New forks are the only place an infringing
commercial deployment can start, so each one gets a review issue linking the
enforcement playbook (docs/COMMERCIAL-RIGHTS.md). A human still does the
2-minute review and, if needed, the DMCA filing -- only the rights holder
can sign that.

Stdlib only. Auth via GITHUB_TOKEN env when present (CI provides it);
works unauthenticated at a lower rate limit for a repo of this size.
"""
import json
import os
import re
import urllib.request

REPO = "demolished-lab/gramshiksha"
API = "https://api.github.com"
LABEL = "fork-watch"
TIMEOUT = 30


def _request(url: str, method: str = "GET", payload: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gramshiksha-fork-watch",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode()), resp.headers.get("Link", "")


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"', part)
        if m and m.group(2) == "next":
            return m.group(1)
    return None


def _all_pages(url: str) -> list:
    items: list = []
    while url:
        page, link = _request(url)
        items.extend(page)
        url = _next_link(link)
    return items


def list_forks() -> list[dict]:
    return _all_pages(f"{API}/repos/{REPO}/forks?per_page=100")


def reported_forks() -> set[str]:
    issues = _all_pages(
        f"{API}/repos/{REPO}/issues?state=open&labels={LABEL}&per_page=100"
    )
    names = set()
    for issue in issues:
        title = issue.get("title", "")
        if title.startswith("Fork watch: "):
            names.add(title.removeprefix("Fork watch: ").strip())
    return names


def new_forks(current: list[dict], reported: set[str]) -> list[dict]:
    return [f for f in current if f.get("full_name") not in reported]


def report_fork(fork: dict) -> str:
    full_name = fork["full_name"]
    body = (
        f"A new public fork appeared: **[{full_name}]({fork['html_url']})** "
        f"(created {fork.get('created_at', 'unknown')}).\n\n"
        "Review (2 min): open the fork and look for ads, paywalls, paid tiers, "
        "resale, or any monetised deployment. If it is being monetised without "
        "written permission from Pravesh Kumar, follow "
        "docs/COMMERCIAL-RIGHTS.md to file a DMCA takedown.\n\n"
        "Close this issue once reviewed. This issue is only a pointer -- "
        "commercial rights remain reserved regardless."
    )
    issue, _ = _request(
        f"{API}/repos/{REPO}/issues",
        method="POST",
        payload={"title": f"Fork watch: {full_name}", "body": body, "labels": [LABEL]},
    )
    return issue["html_url"]


def main() -> int:
    current = list_forks()
    fresh = new_forks(current, reported_forks())
    if not fresh:
        print(f"fork watch: {len(current)} fork(s), all already reported (OK)")
        return 0
    for fork in fresh:
        url = report_fork(fork)
        print(f"fork watch: reported {fork['full_name']} -> {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
