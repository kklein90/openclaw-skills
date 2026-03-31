#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.error
import urllib.request


LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh LinkedIn OAuth access token and optionally save to token store."
    )
    parser.add_argument(
        "--refresh-token",
        default=os.getenv("LINKEDIN_REFRESH_TOKEN"),
        help="Refresh token. Defaults to LINKEDIN_REFRESH_TOKEN.",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("LINKEDIN_CLIENT_ID"),
        help="OAuth client id. Defaults to LINKEDIN_CLIENT_ID.",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("LINKEDIN_CLIENT_SECRET"),
        help="OAuth client secret. Defaults to LINKEDIN_CLIENT_SECRET.",
    )
    parser.add_argument(
        "--token-store",
        default=os.getenv("LINKEDIN_TOKEN_STORE"),
        help="Optional JSON file path to load/save tokens.",
    )
    parser.add_argument(
        "--print-export",
        action="store_true",
        help="Also print export lines for shell usage.",
    )
    return parser


def _load_token_store(path: str | None) -> dict:
    if not path:
        return {}
    token_file = Path(path)
    if not token_file.exists():
        return {}
    return json.loads(token_file.read_text(encoding="utf-8"))


def _save_token_store(path: str | None, data: dict) -> None:
    if not path:
        return
    token_file = Path(path)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        LINKEDIN_TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _redact_token(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def main() -> int:
    args = _arg_parser().parse_args()
    store = _load_token_store(args.token_store)

    refresh_token = args.refresh_token or store.get("refresh_token")
    client_id = args.client_id or store.get("client_id")
    client_secret = args.client_secret or store.get("client_secret")

    missing = []
    if not refresh_token:
        missing.append("refresh_token")
    if not client_id:
        missing.append("client_id")
    if not client_secret:
        missing.append("client_secret")
    if missing:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Missing required fields: {', '.join(missing)}",
                },
                indent=2,
            )
        )
        return 2

    try:
        refreshed = _refresh_access_token(refresh_token, client_id, client_secret)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        print(json.dumps({"ok": False, "status": exc.code, "error": parsed}, indent=2))
        return 1
    except urllib.error.URLError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Network error while refreshing token: {exc.reason}",
                },
                indent=2,
            )
        )
        return 1

    access_token = refreshed.get("access_token")
    next_refresh_token = refreshed.get("refresh_token", refresh_token)
    store.update(
        {
            "access_token": access_token,
            "refresh_token": next_refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "expires_in": refreshed.get("expires_in"),
            "refresh_token_expires_in": refreshed.get("refresh_token_expires_in"),
        }
    )
    _save_token_store(args.token_store, store)

    result = {
        "ok": True,
        "access_token_preview": _redact_token(access_token),
        "expires_in": refreshed.get("expires_in"),
        "refresh_token_expires_in": refreshed.get("refresh_token_expires_in"),
        "token_store": args.token_store,
    }
    if args.print_export:
        result["exports"] = [
            f"export LINKEDIN_ACCESS_TOKEN='{access_token}'",
            f"export LINKEDIN_REFRESH_TOKEN='{next_refresh_token}'",
        ]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
