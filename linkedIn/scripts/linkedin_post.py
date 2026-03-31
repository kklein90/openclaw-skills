#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.error
import urllib.request


LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_IMAGES_INIT_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
DEFAULT_LINKEDIN_VERSION = "202603"


def _arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a LinkedIn text/image post using the LinkedIn Posts API."
    )
    parser.add_argument("--message", required=True, help="Post text (commentary).")
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        help="Path to an image file to upload. Repeat for multiple images.",
    )
    parser.add_argument(
        "--image-alt",
        action="append",
        default=[],
        help="Alt text for each image. Repeat in the same order as --image.",
    )
    parser.add_argument(
        "--visibility",
        default="PUBLIC",
        choices=["PUBLIC", "CONNECTIONS"],
        help="Post visibility (default: PUBLIC).",
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("LINKEDIN_ACCESS_TOKEN"),
        help="OAuth access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--author-urn",
        default=os.getenv("LINKEDIN_AUTHOR_URN"),
        help="Author URN (urn:li:person:* or urn:li:organization:*). Defaults to LINKEDIN_AUTHOR_URN.",
    )
    parser.add_argument(
        "--version",
        default=os.getenv("LINKEDIN_VERSION", DEFAULT_LINKEDIN_VERSION),
        help="LinkedIn-Version header in YYYYMM format (default: LINKEDIN_VERSION or 202603).",
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
        "--auto-refresh",
        action="store_true",
        help="Auto-refresh access token when missing or unauthorized.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request payload without calling LinkedIn.",
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


def _resolve_tokens(args: argparse.Namespace, token_store: dict) -> dict:
    return {
        "access_token": args.access_token or token_store.get("access_token"),
        "refresh_token": args.refresh_token or token_store.get("refresh_token"),
        "client_id": args.client_id or token_store.get("client_id"),
        "client_secret": args.client_secret or token_store.get("client_secret"),
    }


def _validate_args(args: argparse.Namespace) -> None:
    if not args.author_urn:
        raise ValueError("Missing author URN. Set --author-urn or LINKEDIN_AUTHOR_URN.")
    if not args.author_urn.startswith(("urn:li:person:", "urn:li:organization:")):
        raise ValueError("author URN must start with urn:li:person: or urn:li:organization:.")
    if not (len(args.version) == 6 and args.version.isdigit()):
        raise ValueError("LinkedIn version must be in YYYYMM format, for example 202603.")
    if not args.message.strip():
        raise ValueError("message cannot be empty.")
    for image_path in args.image:
        if not Path(image_path).is_file():
            raise ValueError(f"image file not found: {image_path}")
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"file is not recognized as an image: {image_path}")
    if args.image_alt and len(args.image_alt) > len(args.image):
        raise ValueError("You provided more --image-alt values than --image values.")


def _build_default_post_payload(args: argparse.Namespace) -> dict:
    return {
        "author": args.author_urn,
        "commentary": args.message.strip(),
        "visibility": args.visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


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
        raw = response.read().decode("utf-8")
        return json.loads(raw)


def _linkedin_json_request(
    method: str,
    url: str,
    access_token: str,
    version: str,
    payload: dict | None = None,
) -> tuple[int, dict, dict]:
    data = None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": version,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8") if response.length != 0 else ""
        response_data = json.loads(body) if body else {}
        response_headers = dict(response.headers.items())
        return response.status, response_data, response_headers


def _initialize_image_upload(access_token: str, version: str, author_urn: str) -> tuple[str, str]:
    payload = {"initializeUploadRequest": {"owner": author_urn}}
    _, response_data, _ = _linkedin_json_request(
        method="POST",
        url=LINKEDIN_IMAGES_INIT_URL,
        access_token=access_token,
        version=version,
        payload=payload,
    )
    value = response_data.get("value", {})
    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn:
        raise RuntimeError(f"Unexpected initializeUpload response: {response_data}")
    return upload_url, image_urn


def _upload_image_bytes(upload_url: str, image_path: str) -> None:
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(str(path))
    content_type = mime_type or "application/octet-stream"
    data = path.read_bytes()
    request = urllib.request.Request(
        upload_url,
        data=data,
        method="PUT",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(request, timeout=120):
        return


def _build_post_payload(args: argparse.Namespace, image_urns: list[str]) -> dict:
    payload = _build_default_post_payload(args)
    if not image_urns:
        return payload
    if len(image_urns) == 1:
        payload["content"] = {
            "media": {
                "id": image_urns[0],
                "title": Path(args.image[0]).name,
            }
        }
        return payload

    images = []
    for i, image_urn in enumerate(image_urns):
        image_item = {"id": image_urn}
        if i < len(args.image_alt) and args.image_alt[i].strip():
            image_item["altText"] = args.image_alt[i].strip()
        images.append(image_item)
    payload["content"] = {"multiImage": {"images": images}}
    return payload


def _create_post(access_token: str, version: str, payload: dict) -> dict:
    status, response_data, response_headers = _linkedin_json_request(
        method="POST",
        url=LINKEDIN_POSTS_URL,
        access_token=access_token,
        version=version,
        payload=payload,
    )
    return {
        "ok": True,
        "status": status,
        "post_urn": response_headers.get("x-restli-id"),
        "response": response_data,
    }


def _normalize_http_error(exc: urllib.error.HTTPError) -> dict:
    error_text = exc.read().decode("utf-8", errors="replace")
    try:
        error_json = json.loads(error_text)
    except json.JSONDecodeError:
        error_json = {"raw": error_text}

    hint = None
    raw_error = json.dumps(error_json).lower()
    if "not active" in raw_error or "upgrade required" in raw_error:
        hint = (
            "LinkedIn-Version is inactive. Try a currently supported value, "
            "for example 202603 (as of 2026-03-31)."
        )
    elif "oauth" in raw_error or "token" in raw_error or exc.code == 401:
        hint = "Access token may be expired/invalid. Try --auto-refresh with refresh credentials."

    return {
        "ok": False,
        "status": exc.code,
        "error": error_json,
        "hint": hint,
    }


def _normalize_url_error(exc: urllib.error.URLError) -> dict:
    return {
        "ok": False,
        "error": f"Network error while calling LinkedIn: {exc.reason}",
        "hint": "Check internet access/DNS and retry.",
    }


def _redact_token(token: str | None) -> str | None:
    if not token:
        return None
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def main() -> int:
    parser = _arg_parser()
    args = parser.parse_args()

    try:
        _validate_args(args)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    token_store = _load_token_store(args.token_store)
    tokens = _resolve_tokens(args, token_store)

    if not tokens["access_token"] and not args.auto_refresh:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing access token. Set LINKEDIN_ACCESS_TOKEN or pass --auto-refresh with refresh credentials.",
                },
                indent=2,
            )
        )
        return 2

    if (not tokens["access_token"] and args.auto_refresh) or (
        args.auto_refresh and token_store.get("force_refresh")
    ):
        if not (tokens["refresh_token"] and tokens["client_id"] and tokens["client_secret"]):
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "Auto-refresh requested but refresh credentials are incomplete.",
                    },
                    indent=2,
                )
            )
            return 2
        try:
            refreshed = _refresh_access_token(
                tokens["refresh_token"], tokens["client_id"], tokens["client_secret"]
            )
            tokens["access_token"] = refreshed.get("access_token")
            if refreshed.get("refresh_token"):
                tokens["refresh_token"] = refreshed["refresh_token"]
            token_store.update(
                {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "client_id": tokens["client_id"],
                    "client_secret": tokens["client_secret"],
                    "expires_in": refreshed.get("expires_in"),
                    "refresh_token_expires_in": refreshed.get("refresh_token_expires_in"),
                }
            )
            _save_token_store(args.token_store, token_store)
        except urllib.error.HTTPError as exc:
            print(json.dumps(_normalize_http_error(exc), indent=2))
            return 1
        except urllib.error.URLError as exc:
            print(json.dumps(_normalize_url_error(exc), indent=2))
            return 1

    image_urns: list[str] = []
    upload_results = []
    if args.image and not args.dry_run:
        for image_path in args.image:
            try:
                upload_url, image_urn = _initialize_image_upload(
                    tokens["access_token"], args.version, args.author_urn
                )
                _upload_image_bytes(upload_url, image_path)
            except urllib.error.HTTPError as exc:
                print(json.dumps(_normalize_http_error(exc), indent=2))
                return 1
            except urllib.error.URLError as exc:
                print(json.dumps(_normalize_url_error(exc), indent=2))
                return 1
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
                return 1
            image_urns.append(image_urn)
            upload_results.append({"path": image_path, "image_urn": image_urn})

    payload = _build_post_payload(args, image_urns)
    if args.dry_run:
        dry_run = {"ok": True, "dry_run": True, "payload": payload}
        if args.image:
            dry_run["pending_images"] = args.image
        print(json.dumps(dry_run, indent=2))
        return 0

    retried_with_refresh = False
    try:
        result = _create_post(tokens["access_token"], args.version, payload)
    except urllib.error.HTTPError as exc:
        should_retry = (
            args.auto_refresh
            and exc.code == 401
            and tokens["refresh_token"]
            and tokens["client_id"]
            and tokens["client_secret"]
        )
        if not should_retry:
            print(json.dumps(_normalize_http_error(exc), indent=2))
            return 1
        try:
            refreshed = _refresh_access_token(
                tokens["refresh_token"], tokens["client_id"], tokens["client_secret"]
            )
            tokens["access_token"] = refreshed.get("access_token")
            if refreshed.get("refresh_token"):
                tokens["refresh_token"] = refreshed["refresh_token"]
            token_store.update(
                {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "client_id": tokens["client_id"],
                    "client_secret": tokens["client_secret"],
                    "expires_in": refreshed.get("expires_in"),
                    "refresh_token_expires_in": refreshed.get("refresh_token_expires_in"),
                }
            )
            _save_token_store(args.token_store, token_store)
            result = _create_post(tokens["access_token"], args.version, payload)
            retried_with_refresh = True
        except urllib.error.HTTPError as refresh_exc:
            print(json.dumps(_normalize_http_error(refresh_exc), indent=2))
            return 1
        except urllib.error.URLError as refresh_exc:
            print(json.dumps(_normalize_url_error(refresh_exc), indent=2))
            return 1
    except urllib.error.URLError as exc:
        print(json.dumps(_normalize_url_error(exc), indent=2))
        return 1

    if upload_results:
        result["uploaded_images"] = upload_results
    result["token"] = {
        "auto_refresh": bool(args.auto_refresh),
        "retried_with_refresh": retried_with_refresh,
        "token_store": args.token_store,
        "access_token_preview": _redact_token(tokens["access_token"]),
    }
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
