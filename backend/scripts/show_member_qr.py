"""Show a member's live check-in QR on the desktop — local development only.

Testing the scanner needs two devices: one showing a member's code, one reading
it. This script plays the first one, so a single phone is enough. Point the
phone's scanner at the window and the whole chain runs for real — camera, ML
Kit, the HMAC, the replay guard, the response.

Rewrites the same PNG every 20 seconds, so a Preview window left open keeps
showing a code the backend will accept. It holds a real seed in memory and logs
in through the DEBUG-only dev endpoint, which is why this is a script behind
shell access rather than anything reachable over HTTP.

    uv run --with segno python scripts/show_member_qr.py
    uv run --with segno python scripts/show_member_qr.py susanne.bauer@example.com
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.services.attendance_code import build_code, counter_for

DEFAULT_BACKEND = "http://localhost:8013"
REFRESH_SECONDS = 20


def _request(url: str, *, token: str | None = None, payload: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers)) as reply:
        return json.load(reply)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", nargs="?", default="testine@example.com")
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--out", type=Path, default=Path("member_qr.png"))
    args = parser.parse_args()

    try:
        import segno
    except ImportError:
        print("segno is missing. Run with: uv run --with segno python scripts/show_member_qr.py")
        return 1

    try:
        token = _request(
            f"{args.backend}/api/v1/auth/mobile/dev/login", payload={"email": args.email}
        )["data"]["access_token"]
        seed = _request(f"{args.backend}/api/v1/attendance/me/seed", token=token)["data"]
    except urllib.error.HTTPError as error:
        # The two ways this realistically fails: DEBUG is off (the dev login is
        # a 404 then), or the account has no member record to check in.
        print(f"{error.code} from {args.backend}: {error.read().decode()[:200]}")
        return 1

    print(f"Mitglied: {args.email}\nPseudonym: {seed['member_ref']}\nStrg-C beendet.\n")

    opened = False
    while True:
        code = build_code(
            seed["seed"], seed["member_ref"], seed["tenant_id"], counter_for(int(time.time()))
        )
        # scale carries it across a desk; border is the quiet zone every reader
        # needs. Error correction stays low, matching the app.
        segno.make(code, error="l").save(args.out, scale=12, border=4, kind="png")
        print(f"{time.strftime('%H:%M:%S')}  {code}")

        if not opened:
            subprocess.run(["open", str(args.out)], check=False)
            opened = True

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
