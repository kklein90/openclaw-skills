#!/usr/bin/env python3
"""Fetch and filter headlines from RSS and Atom feeds."""

from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

DEFAULT_FEEDS_FILE = Path(__file__).resolve().parent.parent / "assets" / "feeds.json"
DEFAULT_TIMEOUT_SECONDS = 15


def load_feeds(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Feeds file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    feeds = data.get("feeds")
    if not isinstance(feeds, list):
        raise ValueError("Invalid feeds file: 'feeds' must be a list.")
    return feeds


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def parse_date(value: str | None) -> str:
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            if fmt.endswith("Z"):
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            else:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue

    return raw


def text_from_child(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return clean_text(child.text if child is not None else "")


def parse_rss(root: ET.Element) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        title = text_from_child(item, "title")
        link = text_from_child(item, "link")
        pub_date = parse_date(text_from_child(item, "pubDate"))
        if title or link:
            items.append({"title": title, "url": link, "published": pub_date})
    return items


def parse_atom(root: ET.Element) -> list[dict[str, str]]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries: list[dict[str, str]] = []

    for entry in root.findall("atom:entry", ns):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))

        url = ""
        for link in entry.findall("atom:link", ns):
            rel = clean_text(link.attrib.get("rel"))
            href = clean_text(link.attrib.get("href"))
            if not href:
                continue
            if rel in ("", "alternate"):
                url = href
                break
            if not url:
                url = href

        published = parse_date(
            clean_text(
                entry.findtext("atom:updated", default="", namespaces=ns)
                or entry.findtext("atom:published", default="", namespaces=ns)
            )
        )

        if title or url:
            entries.append({"title": title, "url": url, "published": published})

    return entries


def fetch_feed(url: str, timeout: int) -> list[dict[str, str]]:
    req = Request(
        url=url,
        headers={
            "User-Agent": "rss-monitor-skill/1.0 (+https://openai.com)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )

    context = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=context) as response:
        content = response.read()

    root = ET.fromstring(content)
    tag = root.tag.lower()
    if tag.endswith("rss") or root.find("channel") is not None:
        return parse_rss(root)
    if tag.endswith("feed"):
        return parse_atom(root)

    raise ValueError("Unsupported feed format. Expected RSS or Atom.")


def split_csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    if not values:
        return out
    for raw in values:
        for item in raw.split(","):
            item = item.strip().lower()
            if item and item not in out:
                out.append(item)
    return out


def entry_matches(
    entry: dict[str, Any],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> bool:
    text = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("url", "")),
        ]
    ).lower()

    if include_keywords and not any(keyword in text for keyword in include_keywords):
        return False

    if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
        return False

    return True


def format_text_output(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No headlines matched filters."
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        lines.append(f"{idx}. [{row['source']}] {row['title']}")
        lines.append(f"   category: {row['category']}")
        if row.get("published"):
            lines.append(f"   published: {row['published']}")
        lines.append(f"   url: {row['url']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch headlines from configured RSS/Atom feeds.")
    parser.add_argument("--feeds-file", default=str(DEFAULT_FEEDS_FILE), help="Path to feeds JSON file.")
    parser.add_argument("--category", action="append", default=[], help="Category filter (repeatable or comma-separated).")
    parser.add_argument("--feed", action="append", default=[], help="Feed name filter (repeatable or comma-separated).")
    parser.add_argument("--include", action="append", default=[], help="Include keyword filter (repeatable or comma-separated).")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude keyword filter (repeatable or comma-separated).")
    parser.add_argument("--limit-per-feed", type=int, default=10, help="Max items per feed.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Network timeout in seconds.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    args = parser.parse_args()

    feeds_file = Path(args.feeds_file).resolve()
    categories = split_csv(args.category)
    feed_names = split_csv(args.feed)
    include_keywords = split_csv(args.include)
    exclude_keywords = split_csv(args.exclude)

    try:
        feeds = load_feeds(feeds_file)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    selected_feeds = []
    for feed in feeds:
        name = str(feed.get("name", "")).strip()
        category = str(feed.get("category", "")).strip()
        if categories and category.lower() not in categories:
            continue
        if feed_names and name.lower() not in feed_names:
            continue
        selected_feeds.append(feed)

    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for feed in selected_feeds:
        name = str(feed.get("name", "")).strip() or "unnamed-feed"
        category = str(feed.get("category", "")).strip()
        url = str(feed.get("url", "")).strip()
        if not url:
            errors.append(f"{name}: missing URL")
            continue

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            errors.append(f"{name}: unsupported URL scheme '{parsed.scheme or 'none'}'")
            continue

        try:
            entries = fetch_feed(url, timeout=args.timeout)
        except (URLError, ET.ParseError, ValueError, TimeoutError) as exc:
            errors.append(f"{name}: {exc}")
            continue

        kept = 0
        for entry in entries:
            if kept >= args.limit_per_feed:
                break
            result = {
                "source": name,
                "category": category,
                "title": str(entry.get("title", "")).strip() or "(untitled)",
                "url": str(entry.get("url", "")).strip(),
                "published": str(entry.get("published", "")).strip(),
            }
            if not result["url"]:
                continue
            if not entry_matches(result, include_keywords, exclude_keywords):
                continue
            rows.append(result)
            kept += 1

    if args.format == "json":
        print(json.dumps({"headlines": rows, "errors": errors}, indent=2, ensure_ascii=True))
    else:
        print(format_text_output(rows))
        if errors:
            print("\nWarnings:")
            for err in errors:
                print(f"- {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
