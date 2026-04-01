#!/usr/bin/env python3
"""Manage a persistent list of RSS/Atom feeds for monitoring workflows."""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_FEEDS_FILE = Path(__file__).resolve().parent.parent / "assets" / "feeds.json"


def load_feeds(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"feeds": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    feeds = data.get("feeds")
    if not isinstance(feeds, list):
        raise ValueError("Invalid feeds file: 'feeds' must be a list.")
    return {"feeds": feeds}


def save_feeds(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def validate_feed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Feed URL must use http or https.")
    if not parsed.netloc:
        raise ValueError("Feed URL must include a host.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Feed URL must include a valid hostname.")

    lowered = hostname.lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        raise ValueError("Refusing localhost feed URL.")

    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return
        for info in infos:
            candidate = info[4][0]
            try:
                resolved_ip = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_link_local
                or resolved_ip.is_multicast
                or resolved_ip.is_reserved
                or resolved_ip.is_unspecified
            ):
                raise ValueError("Refusing feed URL that resolves to a non-public IP address.")
        return

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("Refusing non-public feed IP address.")


def normalize_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def command_init(args: argparse.Namespace) -> int:
    path = Path(args.feeds_file).resolve()
    if path.exists() and not args.force:
        print(f"Feeds file already exists: {path}")
        print("Use --force to overwrite.")
        return 1
    save_feeds(path, {"feeds": []})
    print(f"Initialized feeds file: {path}")
    return 0


def command_add(args: argparse.Namespace) -> int:
    path = Path(args.feeds_file).resolve()
    data = load_feeds(path)

    name = args.name.strip()
    url = args.url.strip()
    category = args.category.strip()
    tags = normalize_csv_list(args.tags)

    if not name:
        raise ValueError("Feed name cannot be empty.")
    if not category:
        raise ValueError("Category cannot be empty.")
    validate_feed_url(url)

    for item in data["feeds"]:
        if item.get("name", "").lower() == name.lower():
            print(f"Feed name already exists: {name}")
            return 1
        if item.get("url", "").strip() == url:
            print(f"Feed URL already exists: {url}")
            return 1

    data["feeds"].append(
        {
            "name": name,
            "url": url,
            "category": category,
            "tags": tags,
        }
    )
    save_feeds(path, data)
    print(f"Added feed '{name}' ({category})")
    return 0


def command_remove(args: argparse.Namespace) -> int:
    path = Path(args.feeds_file).resolve()
    data = load_feeds(path)

    before = len(data["feeds"])
    target = args.name_or_url.strip().lower()
    data["feeds"] = [
        item
        for item in data["feeds"]
        if item.get("name", "").strip().lower() != target
        and item.get("url", "").strip().lower() != target
    ]
    after = len(data["feeds"])

    if before == after:
        print(f"No feed found for: {args.name_or_url}")
        return 1

    save_feeds(path, data)
    print(f"Removed {before - after} feed(s).")
    return 0


def command_list(args: argparse.Namespace) -> int:
    path = Path(args.feeds_file).resolve()
    data = load_feeds(path)

    category_filter = args.category.strip().lower() if args.category else ""
    items = data["feeds"]
    if category_filter:
        items = [
            item for item in items if item.get("category", "").strip().lower() == category_filter
        ]

    if args.format == "json":
        print(json.dumps({"feeds": items}, indent=2, ensure_ascii=True))
        return 0

    if not items:
        print("No feeds configured.")
        return 0

    for idx, item in enumerate(items, start=1):
        tags = ", ".join(item.get("tags", [])) or "-"
        print(f"{idx}. {item.get('name', '')}")
        print(f"   category: {item.get('category', '')}")
        print(f"   tags: {tags}")
        print(f"   url: {item.get('url', '')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage RSS/Atom feeds for monitoring.")
    parser.add_argument(
        "--feeds-file",
        default=str(DEFAULT_FEEDS_FILE),
        help="Path to feeds JSON file.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help="Initialize an empty feeds file.")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite existing feeds file.")
    init_cmd.set_defaults(func=command_init)

    add_cmd = sub.add_parser("add", help="Add a feed.")
    add_cmd.add_argument("--name", required=True, help="Feed display name.")
    add_cmd.add_argument("--url", required=True, help="Feed URL (RSS or Atom).")
    add_cmd.add_argument("--category", required=True, help="Category label (e.g., competitors).")
    add_cmd.add_argument("--tags", default="", help="Comma-separated tags.")
    add_cmd.set_defaults(func=command_add)

    remove_cmd = sub.add_parser("remove", help="Remove a feed by name or URL.")
    remove_cmd.add_argument("name_or_url", help="Feed name or URL.")
    remove_cmd.set_defaults(func=command_remove)

    list_cmd = sub.add_parser("list", help="List configured feeds.")
    list_cmd.add_argument("--category", default="", help="Optional exact category filter.")
    list_cmd.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    list_cmd.set_defaults(func=command_list)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
