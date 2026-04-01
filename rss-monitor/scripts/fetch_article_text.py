#!/usr/bin/env python3
"""Fetch article pages and extract readable text for on-demand summarization."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import ssl
from html import unescape
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000


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


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https.")
    if not parsed.netloc:
        raise ValueError("URL must include a host.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must include a valid hostname.")

    lowered = hostname.lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        raise ValueError("Refusing localhost URL.")

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
                raise ValueError("Refusing URL that resolves to a non-public IP address.")
        return

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("Refusing non-public IP address.")


def fetch_html(url: str, timeout: int, max_bytes: int) -> str:
    req = Request(
        url=url,
        headers={
            "User-Agent": "rss-monitor-skill/1.0 (+https://openai.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    context = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=context) as response:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise ValueError(
                        f"Response too large ({content_length} bytes). Limit is {max_bytes} bytes."
                    )
            except ValueError as exc:
                if "Response too large" in str(exc):
                    raise
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"Response exceeded limit of {max_bytes} bytes.")
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch article text for manual/on-demand summary.")
    parser.add_argument("url", help="Article URL to fetch.")
    parser.add_argument("--max-chars", type=int, default=8000, help="Maximum characters in extracted text.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_RESPONSE_BYTES, help="Maximum response size in bytes.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Network timeout in seconds.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    args = parser.parse_args()

    try:
        validate_public_url(args.url)
        html = fetch_html(args.url, timeout=args.timeout, max_bytes=args.max_bytes)
    except (URLError, TimeoutError, UnicodeDecodeError, ValueError) as exc:
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
