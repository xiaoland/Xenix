from xenix.ui.markdown_renderer import render_chat_markdown


def test_markdown_renderer_links_artifact_images_only_in_inline_mode() -> None:
    html = render_chat_markdown(
        "![Amount distribution](artifact://artifact-1?view=image)",
        inline_artifact_images=True,
    )

    assert '<a href="artifact://artifact-1"><img src="artifact://artifact-1"' in html
    assert "view=image" not in html


def test_markdown_renderer_downgrades_tool_detail_images_to_links() -> None:
    html = render_chat_markdown(
        "![Amount distribution](artifact://artifact-1?view=image)",
        inline_artifact_images=False,
    )

    assert "<img" not in html
    assert '<a href="artifact://artifact-1">Amount distribution</a>' in html
    assert "view=image" not in html


def test_markdown_renderer_escapes_raw_html() -> None:
    html = render_chat_markdown(
        "<script>alert(1)</script>\n\nSafe text",
        inline_artifact_images=True,
    )

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
