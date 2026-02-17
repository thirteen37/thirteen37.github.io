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
