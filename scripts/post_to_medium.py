#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright",
#   "python-frontmatter",
#   "httpx",
#   "python-dotenv",
# ]
# ///

"""Cross-post a Jekyll markdown post to Medium as a draft."""

import os
import re
import sys
from pathlib import Path

import frontmatter
import httpx


def parse_post(filepath: Path) -> tuple[dict, str]:
    """Parse a Jekyll markdown post into (frontmatter metadata, body string)."""
    post = frontmatter.load(str(filepath))
    return dict(post.metadata), post.content


def extract_blocks(body: str) -> tuple[str, list[dict]]:
    """
    Extract Mermaid diagram blocks and markdown tables from body.
    Returns (body_with_placeholders, blocks) where each block is
    {"type": "mermaid"|"table", "source": str}.
    """
    blocks = []

    # Extract Mermaid blocks first (raw HTML, must come before table scan)
    mermaid_pattern = re.compile(
        r'<pre class="mermaid">\n(.*?)\n</pre>',
        re.DOTALL,
    )

    def replace_mermaid(m):
        idx = len(blocks)
        blocks.append({"type": "mermaid", "source": m.group(1)})
        return f"__BLOCK_{idx}__"

    body = mermaid_pattern.sub(replace_mermaid, body)

    # Extract GFM tables: header row | separator row (|---|) | one or more data rows
    table_pattern = re.compile(
        r'((?:\|[^\n]+\|\n)+\|[-| :]+\|\n(?:\|[^\n]+\|\n)*)',
        re.MULTILINE,
    )

    def replace_table(m):
        idx = len(blocks)
        blocks.append({"type": "table", "source": m.group(1).rstrip("\n")})
        return f"__BLOCK_{idx}__"

    body = table_pattern.sub(replace_table, body)
    return body, blocks


_BASE_CSS = """
    body {
        margin: 0;
        padding: 16px;
        background: white;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 15px;
        color: #222;
    }
    table {
        border-collapse: collapse;
        width: 100%;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px 12px;
        text-align: left;
    }
    th {
        background: #f5f5f5;
        font-weight: 600;
    }
"""

_MERMAID_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>{css}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
</head><body>
<div class="mermaid">{source}</div>
<script>mermaid.initialize({{startOnLoad: true}});</script>
</body></html>"""

_TABLE_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>{css}</style>
</head><body>{table_html}</body></html>"""


def _md_table_to_html(source: str) -> str:
    """Convert a GFM markdown table to an HTML table string."""
    lines = [l.strip() for l in source.strip().splitlines()]
    # lines[0] = header, lines[1] = separator, lines[2:] = data rows
    def cells(line):
        return [c.strip() for c in line.strip("|").split("|")]

    headers = cells(lines[0])
    rows = [cells(l) for l in lines[2:]]

    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def render_block(block: dict) -> bytes:
    """Render a mermaid or table block to PNG bytes using a headless browser."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2)

        if block["type"] == "mermaid":
            html = _MERMAID_HTML.format(css=_BASE_CSS, source=block["source"])
            page.set_content(html, wait_until="networkidle")
            element = page.locator(".mermaid svg").first
        else:
            table_html = _md_table_to_html(block["source"])
            html = _TABLE_HTML.format(css=_BASE_CSS, table_html=table_html)
            page.set_content(html, wait_until="load")
            element = page.locator("table").first

        png = element.screenshot(type="png")
        browser.close()
        return png


def upload_image(png_bytes: bytes, token: str) -> str:
    """Upload a PNG to Medium's image API and return the hosted URL."""
    resp = httpx.post(
        "https://api.medium.com/v1/images",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        files={"image": ("diagram.png", png_bytes, "image/png")},
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]


def reassemble(body: str, blocks: list[dict], urls: list[str]) -> str:
    """Replace placeholder tokens with Medium image markdown."""
    for i, (block, url) in enumerate(zip(blocks, urls)):
        alt = "mermaid diagram" if block["type"] == "mermaid" else "table"
        body = body.replace(f"__BLOCK_{i}__", f"![{alt}]({url})")
    return body


def create_draft(title: str, body: str, tags: list[str], token: str) -> str:
    """Create a Medium draft post and return its URL."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    me = httpx.get("https://api.medium.com/v1/me", headers=headers)
    me.raise_for_status()
    author_id = me.json()["data"]["id"]

    resp = httpx.post(
        f"https://api.medium.com/v1/users/{author_id}/posts",
        headers=headers,
        json={
            "title": title,
            "contentFormat": "markdown",
            "content": body,
            "tags": tags[:5],  # Medium limit
            "publishStatus": "draft",
        },
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]


def main(post_path: Path) -> None:
    from dotenv import load_dotenv

    load_dotenv()
    token = os.environ.get("MEDIUM_TOKEN")
    if not token:
        print("Error: MEDIUM_TOKEN environment variable not set.", file=sys.stderr)
        print("Get a token at: https://medium.com/me/settings (Integration tokens)", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {post_path}...")
    meta, body = parse_post(post_path)

    print("Extracting diagram and table blocks...")
    body, blocks = extract_blocks(body)

    if blocks:
        print(f"Rendering and uploading {len(blocks)} block(s)...")
    urls = []
    for i, block in enumerate(blocks):
        print(f"  [{i+1}/{len(blocks)}] Rendering {block['type']}...")
        try:
            png = render_block(block)
            url = upload_image(png, token=token)
            urls.append(url)
            print(f"  [{i+1}/{len(blocks)}] Uploaded: {url}")
        except Exception as e:
            print(f"  [{i+1}/{len(blocks)}] WARNING: failed to render/upload ({e}), leaving placeholder")
            urls.append(f"__RENDER_FAILED_{i}__")

    body = reassemble(body, blocks, urls)

    print("Creating Medium draft...")
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    draft_url = create_draft(
        title=meta["title"],
        body=body,
        tags=tags,
        token=token,
    )

    print(f"\nDraft created: {draft_url}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: post_to_medium.py <path-to-post.md>")
        sys.exit(1)
    main(Path(sys.argv[1]))
