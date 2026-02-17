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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: post_to_medium.py <path-to-post.md>")
        sys.exit(1)
    print("Not yet implemented")
