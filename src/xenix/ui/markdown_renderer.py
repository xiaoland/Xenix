from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from marko import HTMLRenderer, Markdown
from marko.ext.gfm import GFM
from marko.ext.gfm.renderer import GFMRendererMixin
from marko.helpers import MarkoExtension


def render_chat_markdown(markdown: str, *, inline_artifact_images: bool) -> str:
    """Render a Chatbot markdown string into display HTML.

    Returns HTML with a fixed pre-wrap code-block style. Raw HTML in the input is
    escaped (never rendered) because the input is untrusted model output. When
    inline_artifact_images is true, artifact:// image links render inline;
    otherwise they degrade to link text.
    """
    renderer = _InlineArtifactRenderer if inline_artifact_images else _LinkOnlyArtifactRenderer
    normalized = _separate_gfm_tables(markdown)
    html = Markdown(renderer=renderer, extensions=[_SAFE_GFM_EXTENSION]).convert(normalized).rstrip()
    return _wrap_code_blocks(html)


_FENCE_OPENING = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_TABLE_ROW_SPLITTER = re.compile(r"\s*(?<!\\)\|\s*")
_TABLE_DELIMITER_CELL = re.compile(r":?-+:?")


def _separate_gfm_tables(markdown: str) -> str:
    """Let a GFM table start after model prose without requiring a blank line.

    Marko keeps a pipe table inside the preceding paragraph when an LLM emits
    only one newline before its header. Insert the missing block boundary for
    unambiguous header/delimiter pairs, while leaving fenced code unchanged.
    """
    lines = markdown.splitlines(keepends=True)
    output: list[str] = []
    fence: tuple[str, int] | None = None

    for index, line in enumerate(lines):
        stripped_line = line.rstrip("\r\n")
        if fence is not None:
            marker, minimum_length = fence
            if re.fullmatch(rf" {{0,3}}{re.escape(marker)}{{{minimum_length},}}[ \t]*", stripped_line):
                fence = None
            output.append(line)
            continue

        opening = _FENCE_OPENING.match(stripped_line)
        if opening is not None:
            marker_run = opening.group(1)
            fence = (marker_run[0], len(marker_run))
            output.append(line)
            continue

        if (
            output
            and output[-1].strip()
            and index + 1 < len(lines)
            and _is_gfm_table_pair(stripped_line, lines[index + 1].rstrip("\r\n"))
        ):
            output.append("\r\n" if output[-1].endswith("\r\n") else "\n")
        output.append(line)

    return "".join(output)


def _is_gfm_table_pair(header: str, delimiter: str) -> bool:
    header_cells = _table_cells(header)
    delimiter_cells = _table_cells(delimiter)
    return (
        "|" in header
        and bool(header_cells)
        and len(header_cells) == len(delimiter_cells)
        and all(_TABLE_DELIMITER_CELL.fullmatch(cell.strip()) for cell in delimiter_cells)
    )


def _table_cells(line: str) -> list[str]:
    if re.match(r" {0,3}\S", line) is None:
        return []
    cells = _TABLE_ROW_SPLITTER.split(line.strip())
    if cells and not cells[0]:
        cells.pop(0)
    if cells and not cells[-1]:
        cells.pop()
    return cells


def normalize_artifact_uri(uri: str) -> str:
    parts = urlsplit(uri)
    if parts.scheme != "artifact":
        return uri

    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "view"
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _wrap_code_blocks(html: str) -> str:
    pre_style = ' style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere;"'
    code_style = ' style="white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere;"'
    return html.replace("<pre><code", f"<pre{pre_style}><code{code_style}")


class _BaseChatRenderer(HTMLRenderer):
    inline_artifact_images = False

    # Chat Markdown comes from untrusted model output: escape raw HTML so the
    # model can only inject text/styling, never HTML structure, into the surface.
    def render_html_block(self, element) -> str:  # type: ignore[override]
        return self.escape_html(element.body)

    def render_inline_html(self, element) -> str:  # type: ignore[override]
        return self.escape_html(str(element.children))

    def render_link(self, element) -> str:  # type: ignore[override]
        dest = normalize_artifact_uri(element.dest)
        title = f' title="{self.escape_html(element.title)}"' if element.title else ""
        return '<a href="{}"{}>{}</a>'.format(
            self.escape_url(dest),
            title,
            self.render_children(element),
        )

    def render_image(self, element) -> str:  # type: ignore[override]
        dest = normalize_artifact_uri(element.dest)
        alt = self._plain_text(element)
        title = f' title="{self.escape_html(element.title)}"' if element.title else ""
        if self.inline_artifact_images and urlsplit(dest).scheme == "artifact":
            escaped_dest = self.escape_url(dest)
            return '<a href="{0}"><img src="{0}" alt="{1}"{2} /></a>'.format(
                escaped_dest,
                self.escape_html(alt),
                title,
            )
        link_text = self.escape_html(alt or "Image")
        return '<a href="{}"{}>{}</a>'.format(self.escape_url(dest), title, link_text)

    def _plain_text(self, element) -> str:
        render_func = self.render
        self.render = self.render_plain_text  # type: ignore[method-assign]
        try:
            return str(self.render_children(element))
        finally:
            self.render = render_func  # type: ignore[method-assign]


class _InlineArtifactRenderer(_BaseChatRenderer):
    inline_artifact_images = True


class _LinkOnlyArtifactRenderer(_BaseChatRenderer):
    inline_artifact_images = False


class _SafeGFMRendererMixin(GFMRendererMixin):
    def render_html_block(self, element) -> str:  # type: ignore[override]
        return self.escape_html(element.body)

    def render_inline_html(self, element) -> str:  # type: ignore[override]
        return self.escape_html(str(element.children))

    def render_table(self, element) -> str:  # type: ignore[override]
        head, *body = element.children
        theader = f"<thead>\n{self.render(head)}</thead>"
        tbody = ""
        if body:
            tbody = "\n<tbody>\n{}</tbody>".format(
                "".join(self.render(row) for row in body)
            )
        return (
            '<table border="1" cellspacing="0" cellpadding="4" '
            'style="border-collapse: collapse; border: 1px solid #c7cdd4;">\n'
            f"{theader}{tbody}</table>"
        )

    def render_table_cell(self, element) -> str:  # type: ignore[override]
        tag = "th" if element.header else "td"
        declarations = ["border: 1px solid #c7cdd4", "padding: 4px 6px"]
        if element.header:
            declarations.append("font-weight: bold")
        if element.align:
            declarations.append(f"text-align: {self.escape_html(element.align)}")
        style = "; ".join(declarations)
        return '<{tag} style="{style}">{children}</{tag}>\n'.format(
            tag=tag,
            style=style,
            children=self.render_children(element),
        )


_SAFE_GFM_EXTENSION = MarkoExtension(
    parser_mixins=list(GFM.parser_mixins),
    renderer_mixins=[_SafeGFMRendererMixin],
    elements=list(GFM.elements),
)
