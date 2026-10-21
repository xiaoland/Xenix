from html.parser import HTMLParser

import pytest
from PySide6.QtCore import QUrl

from xenix.ui.markdown_renderer import render_chat_markdown


@pytest.mark.parametrize("artifact_id", [69, 2**55 + 3])
def test_result_links_keep_their_identity_through_qt(artifact_id: int) -> None:
    from urllib.parse import urlsplit

    targets = []

    class Targets(HTMLParser):
        def handle_starttag(self, tag, attrs):
            targets.extend(value for key, value in attrs if key in {"href", "src"})

    Targets().feed(render_chat_markdown(
        f"![Chart](artifact://{artifact_id}?view=image) [Download](artifact://{artifact_id})",
        inline_artifact_images=True,
    ))

    assert len(targets) == 3
    for target in targets:
        parsed = urlsplit(QUrl(target).toString())
        assert parsed.scheme == "artifact"
        assert int(parsed.netloc or parsed.path.lstrip("/")) == artifact_id
        assert not parsed.query


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
