---
name: linkedin-posting
description: Post text updates to a LinkedIn member or organization feed using the LinkedIn Posts API. Use this skill when the user wants the agent to publish or draft a LinkedIn post and send it via API credentials.
---

# LinkedIn Posting Skill

Use this skill when the user wants OpenClaw to publish a LinkedIn post, including image posts.

## What this skill does

- Publishes text or image posts with `POST https://api.linkedin.com/rest/posts`
- Uploads images through LinkedIn Images API (`initializeUpload` + `PUT` upload URL)
- Supports member or organization authors
- Returns the created LinkedIn post URN from `x-restli-id`

## Required setup

Before posting, confirm these are available:

- `LINKEDIN_ACCESS_TOKEN`: OAuth access token with posting permission
- `LINKEDIN_REFRESH_TOKEN`: OAuth refresh token (for auto-refresh)
- `LINKEDIN_CLIENT_ID`: LinkedIn app client id (for auto-refresh)
- `LINKEDIN_CLIENT_SECRET`: LinkedIn app client secret (for auto-refresh)
- `LINKEDIN_AUTHOR_URN`: `urn:li:person:{id}` or `urn:li:organization:{id}`
- `LINKEDIN_VERSION`: LinkedIn API version header in `YYYYMM` format (example: `202603`)
- `LINKEDIN_TOKEN_STORE` (optional): JSON file path where tokens are loaded/saved

## Security notes

- Treat `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_REFRESH_TOKEN`, and especially `LINKEDIN_CLIENT_SECRET` as sensitive secrets.
- Do **not** put `LINKEDIN_TOKEN_STORE` inside a git repo, Dropbox, OneDrive, iCloud, Syncthing, or other synced/shared folders.
- The scripts now write token stores with owner-only permissions (`0600`) and refuse obviously risky storage paths.
- By default, `client_secret` is **not** persisted to disk. To persist it anyway, pass `--persist-client-secret`.
- `--print-export` prints live secrets to stdout. Use it sparingly and never paste the output into chat or shared docs.
- Prefer `--dry-run` before any live post.
- Public posting should require explicit human approval.

Token scopes depend on author type:

- Member posting: `w_member_social`
- Organization posting: `w_organization_social`

## Post a message

Run:

```bash
python3 skills/linkedIn/scripts/linkedin_post.py \
  --message "Your post text here"
```

Optional flags:

- `--visibility` (default `PUBLIC`)
- `--access-token` (overrides env var)
- `--author-urn` (overrides env var)
- `--version` (overrides env var)
- `--dry-run` (print payload only)

For an image post:

```bash
python3 skills/linkedIn/scripts/linkedin_post.py \
  --message "Shipping update + screenshot" \
  --image "/absolute/path/update.png"
```

For auto refresh while posting:

```bash
python3 skills/linkedIn/scripts/linkedin_post.py \
  --message "Token-refresh-enabled post" \
  --auto-refresh
```

If you intentionally want to persist `client_secret` in the token store too:

```bash
python3 skills/linkedIn/scripts/linkedin_post.py \
  --message "Token-refresh-enabled post" \
  --auto-refresh \
  --persist-client-secret
```

## Refresh token manually

```bash
python3 skills/linkedIn/scripts/refresh_linkedin_token.py \
  --print-export
```

If `LINKEDIN_TOKEN_STORE` is set, refreshed tokens are saved there automatically.

## Discover member author URN from userinfo

If your token includes `openid` and `profile`, run:

```bash
python3 skills/linkedIn/scripts/get_author_urn.py --print-export
```

This calls `https://api.linkedin.com/v2/userinfo`, reads `sub`, and builds:

- `urn:li:person:{sub}`

## Notes

- Keep posts under LinkedIn commentary limits.
- If LinkedIn returns auth or permission errors, re-check scopes and whether your app/product is approved for your intended posting flow.
- Scheduling can stay external via cron/OpenClaw orchestration; this skill focuses on publish actions.
