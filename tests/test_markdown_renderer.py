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


def test_markdown_renderer_supports_gfm_tables() -> None:
    html = render_chat_markdown(
        "| A | B |\n|---|:---:|\n| 1 | 2 |",
        inline_artifact_images=True,
    )

    assert '<table border="1" cellspacing="0" cellpadding="4"' in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert 'style="border-collapse: collapse; border: 1px solid #c7cdd4;"' in html
    assert '<th style="border: 1px solid #c7cdd4; padding: 4px 6px; font-weight: bold">A</th>' in html
    assert '<th style="border: 1px solid #c7cdd4; padding: 4px 6px; font-weight: bold; text-align: center">B</th>' in html
    assert '<td style="border: 1px solid #c7cdd4; padding: 4px 6px">1</td>' in html


def test_markdown_renderer_wraps_fenced_code_blocks() -> None:
    html = render_chat_markdown(
        '```json\n{"very_long_key_without_breaks": "very_long_value_without_breaks"}\n```',
        inline_artifact_images=False,
    )

    assert '<pre style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere;">' in html
    assert '<code style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere;" class="language-json">' in html
