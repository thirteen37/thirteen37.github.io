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
