"""One-shot ops tool: register RENDER_DEPLOY_HOOK as a GitHub Actions secret.

Reads the hook URL from ~/.gramshiksha/secrets.env (never printed), encrypts
it with the repository's libsodium public key (sealed box), and PUTs it to
the GitHub API. pynacl is installed ad hoc into the dev venv — it is an ops
dependency, deliberately NOT added to the backend requirements so the Docker
image stays lean.

Usage: .venv/Scripts/python scripts/register_render_hook_secret.py
"""
import base64
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import nacl.public

REPO = "demolished-lab/gramshiksha"
SECRET_NAME = "RENDER_DEPLOY_HOOK"


def read_hook() -> str:
    secrets_file = Path.home() / ".gramshiksha" / "secrets.env"
    for line in secrets_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("RENDER_DEPLOY_HOOK="):
            hook = line.split("=", 1)[1].strip()
            if hook.startswith("https://api.render.com/"):
                return hook
    sys.exit("RENDER_DEPLOY_HOOK missing or malformed in secrets.env")


def github_token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=True,
    )
    for line in out.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    sys.exit("no github credential found")


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gramshiksha-ops",
        },
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def main() -> None:
    hook = read_hook()
    token = github_token()

    pub = api("GET", f"/repos/{REPO}/actions/secrets/public-key", token)
    public_key = base64.b64decode(pub["key"])
    sealed = nacl.public.SealedBox(nacl.public.PublicKey(public_key)).encrypt(
        hook.encode("utf-8")
    )
    api("PUT", f"/repos/{REPO}/actions/secrets/{SECRET_NAME}", token, {
        "encrypted_value": base64.b64encode(sealed).decode("ascii"),
        "key_id": pub["key_id"],
    })
    # The name and key id are not credentials; the hook value never prints.
    print(f"secret {SECRET_NAME} set (key_id={pub['key_id']}, {len(hook)} chars)")


if __name__ == "__main__":
    main()
