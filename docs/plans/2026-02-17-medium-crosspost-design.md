# Design: Medium Cross-Poster

**Date:** 2026-02-17
**Status:** Approved

## Overview

A standalone Python script (`scripts/post_to_medium.py`) that takes a Jekyll post
file as its argument and creates a draft on Medium. Mermaid diagrams and markdown
tables — both unsupported by Medium — are rendered to PNG via Playwright and
uploaded to Medium's image API, then substituted back into the markdown as image
references before posting.

## Pipeline

```
Parse Jekyll post (python-frontmatter)
    → Extract <pre class="mermaid"> blocks & markdown table blocks
    → Render each to PNG via Playwright (headless Chromium)
    → Upload PNGs to Medium image API
    → Substitute ![alt](medium-url) back into markdown body
    → POST { contentFormat: "markdown", content: body } to Medium API (draft)
```

## Script Invocation

```
uv run scripts/post_to_medium.py _posts/2026-02-16-agents-and-spaces.md
```

Dependencies are declared inline via PEP 723 metadata so `uv` handles the
virtualenv automatically. No separate `requirements.txt` or install step.

## Dependencies

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright",
#   "python-frontmatter",
#   "httpx",
#   "python-dotenv",
# ]
# ///
```

`playwright install chromium` must be run once after first `uv run`.

## Configuration

Read from environment variables (or a `.env` file in the repo root, git-ignored):

| Variable | Description |
|---|---|
| `MEDIUM_TOKEN` | Medium integration token (from medium.com/me/settings) |

No other configuration required. The Medium author ID is fetched at runtime via
`GET /v1/me` using the token.

## Components

### 1. Jekyll Post Parser

Uses `python-frontmatter` to split the file into:
- YAML frontmatter: `title`, `tags`, `date`
- Markdown body

### 2. Block Extractor

Scans the markdown body with regex to locate and extract:
- **Mermaid blocks**: `<pre class="mermaid">...</pre>` (raw HTML passthrough in kramdown)
- **Table blocks**: contiguous lines matching the GFM table pattern (header row, separator row with `|---|`, data rows)

Each extracted block is replaced with a unique placeholder token
(`__BLOCK_0__`, `__BLOCK_1__`, …) so the positions are preserved for later
substitution.

### 3. Playwright Renderer

For each extracted block, opens a headless Chromium page with a minimal HTML
template and screenshots the rendered element to a temporary PNG.

**Mermaid template:** loads Mermaid JS from CDN, injects the diagram source,
waits for `mermaid.run()` to complete, screenshots the resulting `<svg>`.

**Table template:** renders the GFM table as an HTML `<table>` with minimal CSS
(white background, clean sans-serif font, bordered cells, comfortable padding).
Screenshots the `<table>` element.

Both templates share the same base CSS for visual consistency:
- White background
- System sans-serif font (matches Medium's reading environment)
- 2× pixel ratio (retina-quality output)

### 4. Medium Image Uploader

POSTs each PNG to `https://api.medium.com/v1/images` with the token, receives
back the hosted URL. Uses `httpx` for all HTTP calls.

### 5. Markdown Assembler

Replaces each placeholder token with `![{block_type} {index}]({medium_url})`
and returns the final markdown body.

### 6. Medium Post Creator

1. `GET /v1/me` → author ID
2. `POST /v1/users/{authorId}/posts` with:
   - `title` from frontmatter
   - `contentFormat: "markdown"`
   - `content`: assembled markdown body
   - `tags`: from frontmatter (max 5, Medium's limit)
   - `publishStatus: "draft"`

Prints the returned draft URL on success.

## Error Handling

- Missing `MEDIUM_TOKEN`: exit with a clear message before doing any work
- Playwright install missing: catch the import error and print `playwright install chromium`
- HTTP errors from Medium API: print status + response body and exit non-zero
- Partial failure (one diagram fails to render): log the error, leave the
  placeholder in the markdown so the user can see what was skipped

## Out of Scope

- Deduplication / tracking which posts have been posted
- Automatic publishing (always creates drafts)
- Cross-posting to publications (only personal drafts)
- Handling posts with no diagrams or tables (works fine, just no image uploads)
