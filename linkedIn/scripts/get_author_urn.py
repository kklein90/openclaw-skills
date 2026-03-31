#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch LinkedIn userinfo and build author URN from sub."
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("LINKEDIN_ACCESS_TOKEN"),
        help="OAuth access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--print-export",
        action="store_true",
        help="Also print an export line for LINKEDIN_AUTHOR_URN.",
    )
    return parser


def _fetch_userinfo(access_token: str) -> dict:
    request = urllib.request.Request(
        USERINFO_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def main() -> int:
    args = _arg_parser().parse_args()

    if not args.access_token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing access token. Set --access-token or LINKEDIN_ACCESS_TOKEN.",
                },
                indent=2,
            )
        )
        return 2

    try:
        userinfo = _fetch_userinfo(args.access_token)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        print(json.dumps({"ok": False, "status": exc.code, "error": parsed}, indent=2))
        return 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    sub = userinfo.get("sub")
    if not sub:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "userinfo response did not include 'sub'.",
                    "userinfo": userinfo,
                },
                indent=2,
            )
        )
        return 1

    author_urn = f"urn:li:person:{sub}"
    result = {
        "ok": True,
        "sub": sub,
        "author_urn": author_urn,
    }

    if args.print_export:
        result["export"] = f"export LINKEDIN_AUTHOR_URN='{author_urn}'"

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
