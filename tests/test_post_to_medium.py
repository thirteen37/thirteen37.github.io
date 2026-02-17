import post_to_medium  # imported via conftest sys.path
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
