from xenix.ui.markdown_renderer import render_chat_markdown


def test_markdown_table_can_follow_model_prose_without_a_blank_line() -> None:
    html = render_chat_markdown(
        "**Top 5:**\n"
        "| Product | Score |\n"
        "| --- | ---: |\n"
        "| Alpha | 6.92 |",
        inline_artifact_images=True,
    )

    assert "<p><strong>Top 5:</strong></p>" in html
    assert '<table border="1" cellspacing="0" cellpadding="4"' in html
    assert "<th" in html and ">Product</th>" in html
    assert "<td" in html and ">Alpha</td>" in html


def test_markdown_table_normalization_leaves_fenced_code_unchanged() -> None:
    html = render_chat_markdown(
        "```text\n"
        "Top 5:\n"
        "| Product | Score |\n"
        "| --- | ---: |\n"
        "| Alpha | 6.92 |\n"
        "```",
        inline_artifact_images=True,
    )

    assert "<table" not in html
    assert "| Product | Score |" in html
