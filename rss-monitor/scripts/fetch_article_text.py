#!/usr/bin/env python3
"""Fetch article pages and extract readable text for on-demand summarization."""

from __future__ import annotations

import argparse
import json
import re
import ssl
from html import unescape
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 15


class TextExtractor(HTMLParser):
    """Very lightweight HTML text extractor with script/style suppression."""

    def __init__(self) -> None:
        super().__init__()
        self.in_ignored = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag.lower() in {"script", "style", "noscript"}:
            self.in_ignored = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.in_ignored = False

    def handle_data(self, data: str) -> None:
        if self.in_ignored:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def clean_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_html(url: str, timeout: int) -> str:
    req = Request(
        url=url,
        headers={
            "User-Agent": "rss-monitor-skill/1.0 (+https://openai.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    context = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch article text for manual/on-demand summary.")
    parser.add_argument("url", help="Article URL to fetch.")
    parser.add_argument("--max-chars", type=int, default=8000, help="Maximum characters in extracted text.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Network timeout in seconds.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https"):
        print("Error: URL must use http or https.")
        return 1

    try:
        html = fetch_html(args.url, timeout=args.timeout)
    except (URLError, TimeoutError, UnicodeDecodeError) as exc:
        print(f"Error: {exc}")
        return 1

    title = extract_title(html)
    extractor = TextExtractor()
    extractor.feed(html)
    text = clean_text(" ".join(extractor.parts))
    if args.max_chars > 0:
        text = text[: args.max_chars]

    payload = {
        "url": args.url,
        "title": title,
        "text": text,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        if title:
            print(f"Title: {title}\n")
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
