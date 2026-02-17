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
