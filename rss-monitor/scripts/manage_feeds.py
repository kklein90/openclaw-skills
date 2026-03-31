#!/usr/bin/env python3
"""Manage a persistent list of RSS/Atom feeds for monitoring workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


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
