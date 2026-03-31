# Feed List Format

Store monitored feeds in `assets/feeds.json`.

## Schema

```json
{
  "feeds": [
    {
      "name": "Human-friendly name",
      "url": "https://example.com/feed.xml",
      "category": "competitors",
      "tags": ["launches", "pricing"]
    }
  ]
}
```

## Notes

- `name` must be unique (case-insensitive).
- `url` must be unique.
- `category` should be stable and reusable for filtering.
- `tags` are optional and can be empty.
