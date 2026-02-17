# Medium Cross-Poster Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A standalone Python script that converts a Jekyll post to a Medium draft, rendering Mermaid diagrams and markdown tables as uploaded PNG images.

**Architecture:** Single script with PEP 723 inline dependencies run via `uv run`. All logic is in importable functions; the CLI entry point is guarded by `if __name__ == "__main__"`. Tests import the script module directly via `conftest.py` path injection.

**Tech Stack:** Python 3.11+, uv, Playwright (headless Chromium), python-frontmatter, httpx, python-dotenv, pytest, pytest-mock

---

## Setup

Before starting, make sure `uv` is installed (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`).

Test runner invocation throughout this plan:
```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/ -v
```

---

### Task 1: Scaffold script and test files

**Files:**
- Create: `scripts/post_to_medium.py`
- Create: `tests/conftest.py`
- Create: `tests/test_post_to_medium.py`
- Create: `tests/fixtures/sample_post.md`

**Step 1: Create the script stub with PEP 723 metadata and shebang**

`scripts/post_to_medium.py`:
```python
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
import sys


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: post_to_medium.py <path-to-post.md>")
        sys.exit(1)
    print("Not yet implemented")
```

**Step 2: Create conftest.py to make the script importable in tests**

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
```

**Step 3: Create the sample fixture post**

`tests/fixtures/sample_post.md`:
```markdown
---
layout: post
title: "Test Post"
date: 2026-01-01 12:00:00 +0800
tags: [ai, test]
---

Intro paragraph.

| Name | Value |
|------|-------|
| Foo  | 1     |
| Bar  | 2     |

Middle paragraph.

<pre class="mermaid">
graph TD
    A["Alpha"] --> B["Beta"]
</pre>

End paragraph.
```

**Step 4: Create the test file stub**

`tests/test_post_to_medium.py`:
```python
import post_to_medium  # imported via conftest sys.path
```

**Step 5: Verify import works**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: 0 tests collected, no import errors.

**Step 6: Commit**

```bash
git add scripts/post_to_medium.py tests/conftest.py tests/test_post_to_medium.py tests/fixtures/sample_post.md
git commit -m "feat: scaffold medium cross-poster script and tests"
```

---

### Task 2: Jekyll post parser

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing test**

Add to `tests/test_post_to_medium.py`:
```python
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_post.md"


def test_parse_post_returns_title():
    meta, body = post_to_medium.parse_post(FIXTURE)
    assert meta["title"] == "Test Post"


def test_parse_post_returns_tags():
    meta, body = post_to_medium.parse_post(FIXTURE)
    assert meta["tags"] == ["ai", "test"]


def test_parse_post_returns_body():
    meta, body = post_to_medium.parse_post(FIXTURE)
    assert "Intro paragraph." in body
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: FAIL — `AttributeError: module 'post_to_medium' has no attribute 'parse_post'`

**Step 3: Implement `parse_post`**

Add to `scripts/post_to_medium.py` (before the `if __name__` block):
```python
from pathlib import Path
import frontmatter


def parse_post(filepath: Path) -> tuple[dict, str]:
    """Parse a Jekyll markdown post into (frontmatter metadata, body string)."""
    post = frontmatter.load(str(filepath))
    return dict(post.metadata), post.content
```

**Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: implement Jekyll post parser"
```

---

### Task 3: Mermaid block extractor

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_extract_mermaid_blocks():
    body = "Before.\n\n<pre class=\"mermaid\">\ngraph TD\n    A --> B\n</pre>\n\nAfter."
    result, blocks = post_to_medium.extract_blocks(body)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "mermaid"
    assert "graph TD" in blocks[0]["source"]
    assert "__BLOCK_0__" in result
    assert "<pre" not in result


def test_extract_mermaid_preserves_surrounding_text():
    body = "Before.\n\n<pre class=\"mermaid\">\ngraph TD\n    A --> B\n</pre>\n\nAfter."
    result, blocks = post_to_medium.extract_blocks(body)
    assert "Before." in result
    assert "After." in result
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_extract_mermaid_blocks tests/test_post_to_medium.py::test_extract_mermaid_preserves_surrounding_text -v
```

Expected: FAIL — `AttributeError: module 'post_to_medium' has no attribute 'extract_blocks'`

**Step 3: Implement `extract_blocks` for Mermaid**

Add to `scripts/post_to_medium.py`:
```python
import re


def extract_blocks(body: str) -> tuple[str, list[dict]]:
    """
    Extract Mermaid diagram blocks and markdown tables from body.
    Returns (body_with_placeholders, blocks) where each block is
    {"type": "mermaid"|"table", "source": str}.
    """
    blocks = []

    # Extract Mermaid blocks: <pre class="mermaid">...</pre>
    mermaid_pattern = re.compile(
        r'<pre class="mermaid">\n(.*?)\n</pre>',
        re.DOTALL,
    )

    def replace_mermaid(m):
        idx = len(blocks)
        blocks.append({"type": "mermaid", "source": m.group(1)})
        return f"__BLOCK_{idx}__"

    body = mermaid_pattern.sub(replace_mermaid, body)
    return body, blocks
```

**Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_extract_mermaid_blocks tests/test_post_to_medium.py::test_extract_mermaid_preserves_surrounding_text -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: extract mermaid diagram blocks from post body"
```

---

### Task 4: Table block extractor

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_extract_table_block():
    body = "Before.\n\n| Name | Value |\n|------|-------|\n| Foo  | 1     |\n\nAfter."
    result, blocks = post_to_medium.extract_blocks(body)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "table"
    assert "| Foo" in blocks[0]["source"]
    assert "__BLOCK_0__" in result
    assert "|---" not in result


def test_extract_multiple_blocks():
    _, blocks = post_to_medium.extract_blocks(
        Path(__file__).parent.joinpath("fixtures/sample_post.md").read_text().split("---\n", 2)[2]
    )
    # fixture has 1 table and 1 mermaid block
    assert len(blocks) == 2
    types = {b["type"] for b in blocks}
    assert types == {"mermaid", "table"}
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_extract_table_block tests/test_post_to_medium.py::test_extract_multiple_blocks -v
```

Expected: FAIL

**Step 3: Extend `extract_blocks` with table extraction**

Replace the `extract_blocks` function body in `scripts/post_to_medium.py`:
```python
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
```

**Step 4: Run all tests**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: all PASSED

**Step 5: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: extract markdown table blocks from post body"
```

---

### Task 5: Playwright renderer

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

The renderer makes real Playwright calls. Tests verify it returns valid PNG bytes without asserting pixel content.

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_render_mermaid_returns_png_bytes():
    source = "graph TD\n    A[\"Alpha\"] --> B[\"Beta\"]"
    png = post_to_medium.render_block({"type": "mermaid", "source": source})
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_render_table_returns_png_bytes():
    source = "| Name | Value |\n|------|-------|\n| Foo  | 1     |"
    png = post_to_medium.render_block({"type": "table", "source": source})
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_render_mermaid_returns_png_bytes tests/test_post_to_medium.py::test_render_table_returns_png_bytes -v
```

Expected: FAIL — `AttributeError: module 'post_to_medium' has no attribute 'render_block'`

**Step 3: Install Playwright browser (one-time)**

```bash
uv run --with playwright python -m playwright install chromium
```

**Step 4: Implement `render_block`**

Add to `scripts/post_to_medium.py`:
```python
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
```

**Step 5: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_render_mermaid_returns_png_bytes tests/test_post_to_medium.py::test_render_table_returns_png_bytes -v
```

Expected: 2 PASSED (these make real browser calls, may take ~5s each)

**Step 6: Run all tests**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: all PASSED

**Step 7: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: render mermaid and table blocks to PNG via Playwright"
```

---

### Task 6: Medium image uploader

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_upload_image_returns_url(mocker):
    fake_response = mocker.MagicMock()
    fake_response.raise_for_status = mocker.MagicMock()
    fake_response.json.return_value = {"data": {"url": "https://cdn-images-1.medium.com/test.png"}}

    mock_post = mocker.patch("httpx.post", return_value=fake_response)

    url = post_to_medium.upload_image(b"\x89PNG fake", token="tok_abc")

    assert url == "https://cdn-images-1.medium.com/test.png"
    call_kwargs = mock_post.call_args
    assert "Authorization" in call_kwargs.kwargs["headers"]
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer tok_abc"


def test_upload_image_raises_on_http_error(mocker):
    import httpx
    fake_response = mocker.MagicMock()
    fake_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400", request=mocker.MagicMock(), response=fake_response
    )
    mocker.patch("httpx.post", return_value=fake_response)

    try:
        post_to_medium.upload_image(b"\x89PNG fake", token="bad")
        assert False, "Should have raised"
    except httpx.HTTPStatusError:
        pass
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_upload_image_returns_url tests/test_post_to_medium.py::test_upload_image_raises_on_http_error -v
```

Expected: FAIL

**Step 3: Implement `upload_image`**

Add to `scripts/post_to_medium.py`:
```python
import httpx


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
```

**Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_upload_image_returns_url tests/test_post_to_medium.py::test_upload_image_raises_on_http_error -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: upload PNG images to Medium image API"
```

---

### Task 7: Markdown assembler

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_reassemble_replaces_placeholders():
    body = "Before.\n\n__BLOCK_0__\n\nMiddle.\n\n__BLOCK_1__\n\nAfter."
    urls = ["https://cdn.medium.com/img0.png", "https://cdn.medium.com/img1.png"]
    blocks = [{"type": "mermaid"}, {"type": "table"}]
    result = post_to_medium.reassemble(body, blocks, urls)
    assert "![mermaid diagram](https://cdn.medium.com/img0.png)" in result
    assert "![table](https://cdn.medium.com/img1.png)" in result
    assert "__BLOCK_" not in result


def test_reassemble_preserves_text():
    body = "Before.\n\n__BLOCK_0__\n\nAfter."
    result = post_to_medium.reassemble(body, [{"type": "mermaid"}], ["https://x.com/a.png"])
    assert "Before." in result
    assert "After." in result
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_reassemble_replaces_placeholders tests/test_post_to_medium.py::test_reassemble_preserves_text -v
```

Expected: FAIL

**Step 3: Implement `reassemble`**

Add to `scripts/post_to_medium.py`:
```python
def reassemble(body: str, blocks: list[dict], urls: list[str]) -> str:
    """Replace placeholder tokens with Medium image markdown."""
    for i, (block, url) in enumerate(zip(blocks, urls)):
        alt = "mermaid diagram" if block["type"] == "mermaid" else "table"
        body = body.replace(f"__BLOCK_{i}__", f"![{alt}]({url})")
    return body
```

**Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_reassemble_replaces_placeholders tests/test_post_to_medium.py::test_reassemble_preserves_text -v
```

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: reassemble post body with Medium image URLs"
```

---

### Task 8: Medium post creator

**Files:**
- Modify: `scripts/post_to_medium.py`
- Modify: `tests/test_post_to_medium.py`

**Step 1: Write the failing tests**

Add to `tests/test_post_to_medium.py`:
```python
def test_create_draft_returns_url(mocker):
    me_resp = mocker.MagicMock()
    me_resp.raise_for_status = mocker.MagicMock()
    me_resp.json.return_value = {"data": {"id": "user123"}}

    post_resp = mocker.MagicMock()
    post_resp.raise_for_status = mocker.MagicMock()
    post_resp.json.return_value = {"data": {"url": "https://medium.com/@user/test-abc123"}}

    mock_get = mocker.patch("httpx.get", return_value=me_resp)
    mock_post = mocker.patch("httpx.post", return_value=post_resp)

    url = post_to_medium.create_draft(
        title="Test Post",
        body="Hello world",
        tags=["ai", "test"],
        token="tok_abc",
    )

    assert url == "https://medium.com/@user/test-abc123"

    post_call = mock_post.call_args
    payload = post_call.kwargs["json"]
    assert payload["title"] == "Test Post"
    assert payload["contentFormat"] == "markdown"
    assert payload["publishStatus"] == "draft"
    assert payload["tags"] == ["ai", "test"]


def test_create_draft_truncates_tags_to_five(mocker):
    me_resp = mocker.MagicMock()
    me_resp.raise_for_status = mocker.MagicMock()
    me_resp.json.return_value = {"data": {"id": "user123"}}

    post_resp = mocker.MagicMock()
    post_resp.raise_for_status = mocker.MagicMock()
    post_resp.json.return_value = {"data": {"url": "https://medium.com/@user/test"}}

    mocker.patch("httpx.get", return_value=me_resp)
    mock_post = mocker.patch("httpx.post", return_value=post_resp)

    post_to_medium.create_draft(
        title="T", body="B", tags=["a", "b", "c", "d", "e", "f"], token="tok"
    )

    payload = mock_post.call_args.kwargs["json"]
    assert len(payload["tags"]) == 5
```

**Step 2: Run tests to verify they fail**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_create_draft_returns_url tests/test_post_to_medium.py::test_create_draft_truncates_tags_to_five -v
```

Expected: FAIL

**Step 3: Implement `create_draft`**

Add to `scripts/post_to_medium.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py::test_create_draft_returns_url tests/test_post_to_medium.py::test_create_draft_truncates_tags_to_five -v
```

Expected: 2 PASSED

**Step 5: Run all tests**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: all PASSED

**Step 6: Commit**

```bash
git add scripts/post_to_medium.py tests/test_post_to_medium.py
git commit -m "feat: post draft to Medium API"
```

---

### Task 9: Wire up the CLI entry point

**Files:**
- Modify: `scripts/post_to_medium.py`

No new tests needed — this is glue code that calls already-tested functions.

**Step 1: Replace the stub `if __name__` block**

Replace the existing `if __name__ == "__main__":` block at the bottom of `scripts/post_to_medium.py` with:

```python
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
```

**Step 2: Run all tests to confirm nothing broke**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: all PASSED

**Step 3: Commit**

```bash
git add scripts/post_to_medium.py
git commit -m "feat: wire up CLI entry point for medium cross-poster"
```

---

### Task 10: Add .env.example and update .gitignore

**Files:**
- Create: `.env.example`
- Modify: `.gitignore`

**Step 1: Create `.env.example`**

`.env.example`:
```
# Medium integration token
# Get yours at: https://medium.com/me/settings (Integration tokens section)
MEDIUM_TOKEN=your_token_here
```

**Step 2: Ensure `.gitignore` covers `.env`**

Check if `.gitignore` already ignores `.env`:
```bash
grep -n "\.env" .gitignore
```

If not present, add it:
```
.env
```

**Step 3: Run all tests one final time**

```bash
uv run --with pytest --with pytest-mock --with python-frontmatter --with httpx python -m pytest tests/test_post_to_medium.py -v
```

Expected: all PASSED

**Step 4: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example and gitignore for Medium token"
```

---

## Usage

After completing all tasks:

```bash
# One-time setup
cp .env.example .env
# Edit .env and add your MEDIUM_TOKEN
uv run --with playwright python -m playwright install chromium

# Cross-post a specific article
uv run scripts/post_to_medium.py _posts/2026-02-16-agents-and-spaces.md
```
