---
name: rss-monitor
description: Monitor and research RSS/Atom sources with a persistent feed list and category-based filtering. Use when tracking competitor blogs, industry news, newsletters, content trends, or building a personal news aggregator. Supports creating and updating feed lists, pulling recent headlines from multiple feeds, filtering by category/feed/keywords, and generating article summaries only on request (no pre-summarizing).
---

# RSS Monitor

## Overview

Use this skill to maintain a reusable watchlist of RSS/Atom feeds, fetch current headlines, and produce summaries only when explicitly requested.

## Workflow

1. Ensure a feed list exists.
2. Add or update feeds with categories and tags.
3. Pull headlines using category/feed/keyword filters.
4. Summarize selected articles on demand only.

## Commands

Use these scripts from the skill directory.

```bash
# 1) Initialize (or reset) feed list
python scripts/manage_feeds.py init

# 2) Add feeds
python scripts/manage_feeds.py add \
  --name "OpenAI News" \
  --url "https://openai.com/news/rss.xml" \
  --category "industry-news" \
  --tags "ai,model-updates"

python scripts/manage_feeds.py add \
  --name "Competitor Blog" \
  --url "https://example.com/feed.xml" \
  --category "competitors" \
  --tags "pricing,launches"

# 3) List feeds
python scripts/manage_feeds.py list
python scripts/manage_feeds.py list --category competitors

# 4) Remove feeds
python scripts/manage_feeds.py remove "Competitor Blog"
# or
python scripts/manage_feeds.py remove "https://example.com/feed.xml"
```

```bash
# Pull latest headlines from all feeds
python scripts/fetch_headlines.py

# Filter by category/feed/keywords
python scripts/fetch_headlines.py --category competitors --limit-per-feed 5
python scripts/fetch_headlines.py --feed "OpenAI News" --include release,api --exclude rumor

# Machine-friendly output
python scripts/fetch_headlines.py --format json
```

```bash
# Fetch article text only when user asks for a summary
python scripts/fetch_article_text.py "https://example.com/post"

# JSON output for structured downstream processing
python scripts/fetch_article_text.py "https://example.com/post" --format json --max-chars 12000
```

## Operating Rules

- Keep feed definitions in `assets/feeds.json`.
- Treat `category` as the primary grouping key for monitoring workflows.
- Use `--include` and `--exclude` for quick topical filtering.
- Do not summarize preemptively.
- Summarize only links the user explicitly asks to summarize.
- When summarizing, cite the article URL and clarify if extraction was partial (for example due to paywalls or script-heavy pages).

## Security Notes

- This skill fetches untrusted network content from configured feed URLs and article URLs.
- Feed and article URLs are restricted to `http`/`https` and now reject localhost, private IPs, and other non-public network targets.
- Response sizes are capped to reduce risk from unexpectedly large feeds or pages.
- Feed list writes use a temporary file + rename pattern to reduce corruption risk.
- This skill does not store secrets and should not require credentials for normal RSS/Atom usage.

## Resources

- `scripts/manage_feeds.py`: Initialize/add/list/remove monitored feeds.
- `scripts/fetch_headlines.py`: Pull RSS/Atom headlines with filters.
- `scripts/fetch_article_text.py`: Retrieve page text for on-demand summaries.
- `assets/feeds.json`: Persistent monitored feed list.
- `references/feed-format.md`: Feed list schema and examples.
