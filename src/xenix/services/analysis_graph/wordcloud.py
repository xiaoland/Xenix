from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd
import wordcloud as wordcloud_module
from wordcloud import WordCloud

from ...config import AppPaths
from ...exceptions import ValidationError
from .contracts import (
    MAX_COLUMNS_IN_ERROR,
    MAX_HEIGHT,
    MAX_OUTPUT_BYTES,
    MAX_SPEC_BYTES,
    MAX_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    GraphDatasetResult,
    _PreparedWordcloud,
    spec_json,
)
from .svg import SVG_NS, SVG_STYLE_TAGS, serialize_svg, write_svg_output

_WORDCLOUD_DEFAULT_WIDTH = 720
_WORDCLOUD_DEFAULT_HEIGHT = 420
_WORDCLOUD_DEFAULT_TOP_N = 80
_WORDCLOUD_MIN_TOP_N = 20
_WORDCLOUD_MAX_TOP_N = 80
_WORDCLOUD_MIN_RECOMMENDED_TERMS = 20
_WORDCLOUD_DENSE_TERM_THRESHOLD = 40
_WORDCLOUD_DEFAULT_FONT_SIZE_RANGE = (12, 56)
_WORDCLOUD_DENSE_FONT_SIZE_RANGE = (10, 42)
_WORDCLOUD_DEFAULT_PREFER_HORIZONTAL = 0.85
_WORDCLOUD_MIN_PREFER_HORIZONTAL = 0.8
_WORDCLOUD_MAX_PREFER_HORIZONTAL = 1.0
_WORDCLOUD_DEFAULT_RANK_TIER_PALETTE = ["#1f4e79", "#4f7cac", "#b8c5d6"]
_WORDCLOUD_DEFAULT_SEMANTIC_PALETTE = ["#1f4e79", "#c06c4e", "#6e8b3d", "#2f7d65", "#8f5f3f", "#5078a0"]
_WORDCLOUD_MAX_PALETTE_SIZE = 8
_WORDCLOUD_RANDOM_STATE = 42
_WORDCLOUD_BACKGROUND_COLOR = "white"
_WORDCLOUD_MAX_FAILED_TERM_RATIO = 0.2
_WORDCLOUD_MAX_FAILED_TERM_COUNT = 8
_WORDCLOUD_MARGIN = 1
_WORDCLOUD_TITLE_HEIGHT = 40
_WORDCLOUD_TITLE_Y = 26
_WORDCLOUD_TITLE_FONT_SIZE = 18
_WORDCLOUD_WORD_FIELD = "word"
_WORDCLOUD_COUNT_FIELD = "count"
_WORDCLOUD_COLOR_MODES = {"rank_tier", "field"}
_WORDCLOUD_UNSPECIFIED_GROUP = "unspecified"
_WORDCLOUD_REPAIR_HINTS = [
    "Use data.query or data.transform first to produce a chart-ready frequency table, usually with exact columns `word` and `count`.",
    "For Chinese raw text, segment upstream first. Do not pass raw sentences or rely on countpattern-like tokenization here.",
    "Keep the cloud focused on roughly the Top 20-80 terms and remove blank or meaningless tokens upstream.",
]
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


def validate_wordcloud_spec_object(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("analysis.graph wordcloud_spec must be an object.")
    return value


def graph_wordcloud_dataset(
    paths: AppPaths,
    *,
    user_spec: dict[str, Any],
    frame: pd.DataFrame,
    dataset_name: str,
) -> GraphDatasetResult:
    serialized = spec_json(user_spec, field_name="wordcloud_spec")
    if len(serialized.encode("utf-8")) > MAX_SPEC_BYTES:
        raise ValidationError(f"analysis.graph wordcloud_spec cannot exceed {MAX_SPEC_BYTES} bytes.")

    prepared = _prepare_wordcloud_request(user_spec, frame, dataset_name)
    svg = _render_wordcloud_svg(prepared)
    output_bytes = len(svg.encode("utf-8"))
    if output_bytes > MAX_OUTPUT_BYTES:
        raise ValidationError(
            "analysis.graph rendered SVG is too large. Reduce the canvas size, top_n, or font_size_range."
        )

    font_path = _resolve_wordcloud_font_path(prepared.contains_cjk)
    output_path = write_svg_output(paths, svg=svg, dataset_name=dataset_name, suffix="wordcloud")
    return GraphDatasetResult(
        effective_parameters={
            "width": prepared.width,
            "height": prepared.height,
            "top_n": prepared.top_n,
            "prefer_horizontal": prepared.prefer_horizontal,
            "font_size_range": [prepared.min_font_size, prepared.max_font_size],
            "color_mode": prepared.color_mode,
            "color_field": prepared.color_field,
            "referenced_fields": prepared.referenced_fields,
            "random_state": _WORDCLOUD_RANDOM_STATE,
            "margin": _WORDCLOUD_MARGIN,
            "background_color": _WORDCLOUD_BACKGROUND_COLOR,
            "collocations": False,
            "normalize_plurals": False,
            "font": font_path.name if font_path is not None else None,
            "colors": prepared.color_by_word,
        },
        output_path=str(output_path.resolve()),
        graph_metadata={
            "renderer": "wordcloud",
            "renderer_version": getattr(wordcloud_module, "__version__", None),
            "spec_format": "wordcloud",
            "dataset_name": dataset_name,
            "title": prepared.title,
            "row_count": int(len(frame.index)),
            "rendered_row_count": prepared.rendered_row_count,
            "truncated": prepared.truncated,
            "referenced_fields": prepared.referenced_fields,
            "generated_fields": [],
            "warnings": prepared.warnings,
            "output_bytes": output_bytes,
            "wordcloud_options": {
                "top_n": prepared.top_n,
                "prefer_horizontal": prepared.prefer_horizontal,
                "font_size_range": [prepared.min_font_size, prepared.max_font_size],
                "color_mode": prepared.color_mode,
                "color_field": prepared.color_field,
            },
        },
    )


def _prepare_wordcloud_request(
    user_spec: dict[str, Any],
    frame: pd.DataFrame,
    dataset_name: str,
) -> _PreparedWordcloud:
    unsupported_keys = sorted(
        set(user_spec)
        - {
            "title",
            "word_field",
            "count_field",
            "top_n",
            "width",
            "height",
            "prefer_horizontal",
            "font_size_range",
            "color_mode",
            "color_field",
            "palette",
        }
    )
    if unsupported_keys:
        raise ValidationError(
            "analysis.graph wordcloud_spec does not accept: " + ", ".join(unsupported_keys)
        )
    title = _optional_title(user_spec.get("title"), dataset_name)
    word_field = _field_name_option(
        user_spec.get("word_field"),
        field_name="analysis.graph wordcloud_spec.word_field",
        default=_WORDCLOUD_WORD_FIELD,
    )
    count_field = _field_name_option(
        user_spec.get("count_field"),
        field_name="analysis.graph wordcloud_spec.count_field",
        default=_WORDCLOUD_COUNT_FIELD,
    )
    top_n = _integer_option(
        user_spec.get("top_n"),
        field_name="analysis.graph wordcloud_spec.top_n",
        minimum=_WORDCLOUD_MIN_TOP_N,
        maximum=_WORDCLOUD_MAX_TOP_N,
        default=_WORDCLOUD_DEFAULT_TOP_N,
    )
    width = _integer_option(
        user_spec.get("width"),
        field_name="analysis.graph wordcloud_spec.width",
        minimum=MIN_WIDTH,
        maximum=MAX_WIDTH,
        default=_WORDCLOUD_DEFAULT_WIDTH,
    )
    height = _integer_option(
        user_spec.get("height"),
        field_name="analysis.graph wordcloud_spec.height",
        minimum=MIN_HEIGHT,
        maximum=MAX_HEIGHT,
        default=_WORDCLOUD_DEFAULT_HEIGHT,
    )
    prefer_horizontal = _float_option(
        user_spec.get("prefer_horizontal"),
        field_name="analysis.graph wordcloud_spec.prefer_horizontal",
        minimum=_WORDCLOUD_MIN_PREFER_HORIZONTAL,
        maximum=_WORDCLOUD_MAX_PREFER_HORIZONTAL,
        default=_WORDCLOUD_DEFAULT_PREFER_HORIZONTAL,
    )
    color_mode = _wordcloud_color_mode(user_spec.get("color_mode"))
    color_field = _optional_field_name(
        user_spec.get("color_field"),
        field_name="analysis.graph wordcloud_spec.color_field",
    )
    if color_mode == "field" and color_field is None:
        _raise_wordcloud_error(
            "analysis.graph wordcloud_spec.color_mode='field' requires color_field.",
            error_code="wordcloud_color_field_required",
            error_details={"color_mode": color_mode},
        )
    if color_mode != "field" and color_field is not None:
        raise ValidationError(
            "analysis.graph wordcloud_spec.color_field is only allowed when color_mode is 'field'."
        )

    columns = [str(column) for column in frame.columns]
    required_fields = [
        ("word", word_field),
        ("count", count_field),
    ]
    if color_field is not None:
        required_fields.append(("color", color_field))
    _validate_wordcloud_required_fields(required_fields, columns)

    prepared_frame, warnings, truncated = _prepare_wordcloud_frame(
        frame=frame,
        word_field=word_field,
        count_field=count_field,
        color_field=color_field,
        top_n=top_n,
    )
    words = prepared_frame[word_field].tolist()
    contains_cjk = any(_contains_cjk(word) for word in words)
    font_size_range = _font_size_range_option(
        user_spec.get("font_size_range"),
        words=words,
    )
    palette, palette_warnings = _wordcloud_palette(
        raw_palette=user_spec.get("palette"),
        color_mode=color_mode,
        category_count=int(prepared_frame[color_field].nunique()) if color_field is not None else 0,
    )
    warnings.extend(palette_warnings)
    frequencies = {
        str(word): float(count)
        for word, count in zip(prepared_frame[word_field].tolist(), prepared_frame[count_field].tolist(), strict=False)
    }
    color_by_word, tooltip_by_word = _wordcloud_annotations(
        frame=prepared_frame,
        word_field=word_field,
        count_field=count_field,
        color_mode=color_mode,
        color_field=color_field,
        palette=palette,
    )
    return _PreparedWordcloud(
        title=title,
        width=width,
        height=height,
        referenced_fields=sorted(field for _role, field in required_fields),
        rendered_row_count=int(len(prepared_frame.index)),
        truncated=truncated,
        warnings=warnings,
        frequencies=frequencies,
        tooltip_by_word=tooltip_by_word,
        color_by_word=color_by_word,
        min_font_size=font_size_range[0],
        max_font_size=font_size_range[1],
        prefer_horizontal=prefer_horizontal,
        contains_cjk=contains_cjk,
        color_mode=color_mode,
        color_field=color_field,
        top_n=top_n,
    )


def _render_wordcloud_svg(prepared: _PreparedWordcloud) -> str:
    font_path = _resolve_wordcloud_font_path(prepared.contains_cjk)
    color_func = lambda word, *args, **kwargs: prepared.color_by_word.get(str(word), _WORDCLOUD_DEFAULT_RANK_TIER_PALETTE[-1])
    try:
        cloud = WordCloud(
            width=prepared.width,
            height=prepared.height,
            background_color=_WORDCLOUD_BACKGROUND_COLOR,
            prefer_horizontal=prepared.prefer_horizontal,
            min_font_size=prepared.min_font_size,
            max_font_size=prepared.max_font_size,
            font_path=str(font_path) if font_path is not None else None,
            color_func=color_func,
            random_state=_WORDCLOUD_RANDOM_STATE,
            margin=_WORDCLOUD_MARGIN,
            collocations=False,
            normalize_plurals=False,
        )
        cloud.generate_from_frequencies(prepared.frequencies)
    except Exception as exc:
        _raise_wordcloud_error(
            "analysis.graph could not render the wordcloud.",
            error_code="wordcloud_render_failed",
            error_details={
                "width": prepared.width,
                "height": prepared.height,
                "top_n": prepared.top_n,
            },
            repair_hints=[
                "Reduce top_n or long labels when the cloud is too dense.",
                "Use the denser font_size_range [10, 42] when terms are many or labels are long.",
            ],
        )
        raise AssertionError("unreachable") from exc

    layout = getattr(cloud, "layout_", []) or []
    visible_terms = len(layout)
    total_terms = len(prepared.frequencies)
    if visible_terms == 0:
        _raise_wordcloud_error(
            "analysis.graph wordcloud rendered no visible terms.",
            error_code="wordcloud_rendered_no_terms",
            error_details={"visible_terms": 0, "total_terms": total_terms},
        )
    failed_terms = max(0, total_terms - visible_terms)
    minimum_readable_terms = min(total_terms, _WORDCLOUD_MIN_RECOMMENDED_TERMS)
    if (
        visible_terms < minimum_readable_terms
        and failed_terms > _WORDCLOUD_MAX_FAILED_TERM_COUNT
        and failed_terms / max(total_terms, 1) > _WORDCLOUD_MAX_FAILED_TERM_RATIO
    ):
        _raise_wordcloud_error(
            "analysis.graph wordcloud could not place enough terms.",
            error_code="wordcloud_term_placement_failed",
            error_details={
                "visible_terms": visible_terms,
                "failed_terms": failed_terms,
                "total_terms": total_terms,
            },
            repair_hints=[
                "Reduce top_n or enlarge width and height before retrying.",
                "Use shorter labels or pre-aggregate similar variants upstream.",
            ],
        )

    try:
        svg = cloud.to_svg(embed_font=False)
        svg = _inject_wordcloud_tooltips(svg, prepared.tooltip_by_word)
        svg = _add_wordcloud_title(
            svg=svg,
            title=prepared.title,
            width=prepared.width,
            height=prepared.height,
        )
    except Exception as exc:
        _raise_wordcloud_error(
            "analysis.graph rendered the wordcloud layout but could not finalize the SVG.",
            error_code="wordcloud_svg_finalize_failed",
            retryable=False,
        )
        raise AssertionError("unreachable") from exc

    if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
        raise ValidationError("analysis.graph renderer did not return a valid SVG image.")
    return svg


def _inject_wordcloud_tooltips(svg: str, tooltip_by_word: dict[str, str]) -> str:
    root = ET.fromstring(svg)
    for element in root.iter(f"{{{SVG_NS}}}text"):
        word = (element.text or "").strip()
        if not word or word not in tooltip_by_word:
            continue
        element.text = None
        title = ET.Element(f"{{{SVG_NS}}}title")
        title.text = tooltip_by_word[word]
        title.tail = word
        element.insert(0, title)
    return serialize_svg(root)


def _add_wordcloud_title(*, svg: str, title: str, width: int, height: int) -> str:
    root = ET.fromstring(svg)
    content_group = ET.Element(f"{{{SVG_NS}}}g", {"transform": f"translate(0,{_WORDCLOUD_TITLE_HEIGHT})"})
    content_children = [child for child in list(root) if child.tag not in SVG_STYLE_TAGS]
    for child in content_children:
        root.remove(child)
        if _is_wordcloud_background_rect(child):
            continue
        content_group.append(child)

    total_height = height + _WORDCLOUD_TITLE_HEIGHT
    root.set("height", str(total_height))
    root.set("viewBox", f"0 0 {width} {total_height}")

    insertion_index = len(list(root))
    for index, child in enumerate(list(root)):
        if child.tag not in SVG_STYLE_TAGS:
            insertion_index = index
            break

    background = ET.Element(
        f"{{{SVG_NS}}}rect",
        {
            "width": "100%",
            "height": "100%",
            "style": f"fill:{_WORDCLOUD_BACKGROUND_COLOR}",
        },
    )
    title_element = ET.Element(
        f"{{{SVG_NS}}}text",
        {
            "x": str(width // 2),
            "y": str(_WORDCLOUD_TITLE_Y),
            "text-anchor": "middle",
            "font-size": str(_WORDCLOUD_TITLE_FONT_SIZE),
            "font-weight": "600",
            "style": "fill:#172033",
        },
    )
    title_element.text = title
    root.insert(insertion_index, background)
    root.insert(insertion_index + 1, title_element)
    root.append(content_group)
    return serialize_svg(root)


def _is_wordcloud_background_rect(element: ET.Element) -> bool:
    if element.tag != f"{{{SVG_NS}}}rect":
        return False
    width = str(element.attrib.get("width") or "").strip()
    height = str(element.attrib.get("height") or "").strip()
    if width != "100%" or height != "100%":
        return False
    style = str(element.attrib.get("style") or "").replace(" ", "").lower()
    if f"fill:{_WORDCLOUD_BACKGROUND_COLOR}".lower() in style:
        return True
    fill = str(element.attrib.get("fill") or "").strip().lower()
    return fill == _WORDCLOUD_BACKGROUND_COLOR.lower()


def _validate_wordcloud_required_fields(
    required_fields: list[tuple[str, str]],
    available_columns: list[str],
) -> None:
    missing_fields = [(role, field) for role, field in required_fields if field not in available_columns]
    if not missing_fields:
        return
    role, missing_field = missing_fields[0]
    _raise_wordcloud_error(
        f"analysis.graph wordcloud_spec {role} field '{missing_field}' was not found in the dataset.",
        error_code=f"wordcloud_{role}_field_missing",
        error_details={
            "requested_field": missing_field,
            "available_columns": available_columns[:MAX_COLUMNS_IN_ERROR],
        },
    )


def _prepare_wordcloud_frame(
    *,
    frame: pd.DataFrame,
    word_field: str,
    count_field: str,
    color_field: str | None,
    top_n: int,
) -> tuple[pd.DataFrame, list[str], bool]:
    warnings: list[str] = []
    prepared = pd.DataFrame()
    prepared[word_field] = frame[word_field].where(pd.notna(frame[word_field]), "").astype(str).str.strip()
    prepared[count_field] = pd.to_numeric(frame[count_field], errors="coerce")
    if color_field is not None:
        prepared[color_field] = frame[color_field].where(pd.notna(frame[color_field]), "").astype(str).str.strip()
        blank_groups = int(prepared[color_field].eq("").sum())
        if blank_groups:
            prepared.loc[prepared[color_field].eq(""), color_field] = _WORDCLOUD_UNSPECIFIED_GROUP
            warnings.append(
                f"Wordcloud filled {blank_groups} blank `{color_field}` values as `{_WORDCLOUD_UNSPECIFIED_GROUP}`."
            )

    valid_mask = prepared[word_field].ne("") & prepared[count_field].notna() & prepared[count_field].gt(0)
    removed_rows = int((~valid_mask).sum())
    if removed_rows:
        warnings.append(f"Wordcloud ignored {removed_rows} rows with blank words or non-positive counts.")

    prepared = prepared.loc[valid_mask].copy()
    if prepared.empty:
        _raise_wordcloud_error(
            "analysis.graph wordcloud requires at least one non-empty word with a positive count.",
            error_code="wordcloud_no_valid_terms",
            error_details={"word_field": word_field, "count_field": count_field},
        )

    initial_rows = int(len(prepared.index))
    if color_field is None:
        prepared = prepared.groupby(word_field, as_index=False, sort=False)[count_field].sum()
        if len(prepared.index) < initial_rows:
            warnings.append("Wordcloud aggregated duplicate words by summed counts.")
    else:
        prepared = prepared.groupby([word_field, color_field], as_index=False, sort=False)[count_field].sum()
        if len(prepared.index) < initial_rows:
            warnings.append("Wordcloud aggregated duplicate word/group rows by summed counts.")
        repeated_words = int(prepared[word_field].duplicated(keep=False).sum())
        if repeated_words:
            warnings.append(
                "Wordcloud kept the highest-count semantic group when the same word appeared in multiple groups."
            )
        prepared.sort_values(
            by=[count_field, word_field, color_field],
            ascending=[False, True, True],
            kind="mergesort",
            inplace=True,
        )
        prepared = prepared.drop_duplicates(subset=[word_field], keep="first").copy()

    prepared.sort_values(
        by=[count_field, word_field],
        ascending=[False, True],
        kind="mergesort",
        inplace=True,
    )
    total_terms = int(len(prepared.index))
    truncated = total_terms > top_n
    if truncated:
        warnings.append(f"Wordcloud rendered the top {top_n} terms by `{count_field}` for readability.")
        prepared = prepared.head(top_n).copy()
    elif total_terms < _WORDCLOUD_MIN_RECOMMENDED_TERMS:
        warnings.append(
            f"Wordcloud dataset contains only {total_terms} terms. "
            f"Top {_WORDCLOUD_MIN_RECOMMENDED_TERMS}+ usually reads better when the source supports it."
        )
    return prepared, warnings, truncated


def _wordcloud_annotations(
    *,
    frame: pd.DataFrame,
    word_field: str,
    count_field: str,
    color_mode: str,
    color_field: str | None,
    palette: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    records = frame.to_dict(orient="records")
    color_by_word: dict[str, str] = {}
    tooltip_by_word: dict[str, str] = {}
    if color_mode == "rank_tier":
        tier_palette = _wordcloud_rank_tier_palette(palette)
        for index, record in enumerate(records):
            word = str(record[word_field])
            count_text = _format_wordcloud_count(record[count_field])
            tier = _wordcloud_color_tier(index=index, term_count=len(records))
            color_by_word[word] = tier_palette[tier]
            tooltip_by_word[word] = f"{word}: {count_text}"
        return color_by_word, tooltip_by_word

    assert color_field is not None
    category_order: list[str] = []
    for record in records:
        category = str(record[color_field])
        if category not in category_order:
            category_order.append(category)
    category_colors = {category: palette[index] for index, category in enumerate(category_order)}
    for record in records:
        word = str(record[word_field])
        category = str(record[color_field])
        count_text = _format_wordcloud_count(record[count_field])
        color_by_word[word] = category_colors[category]
        tooltip_by_word[word] = f"{word}: {count_text} | {color_field}: {category}"
    return color_by_word, tooltip_by_word


def _wordcloud_rank_tier_palette(palette: list[str]) -> dict[str, str]:
    if len(palette) == 2:
        return {"top": palette[0], "mid": palette[1], "tail": palette[1]}
    return {"top": palette[0], "mid": palette[1], "tail": palette[2]}


def _wordcloud_color_tier(*, index: int, term_count: int) -> str:
    top_cut = max(1, math.ceil(term_count * 0.2))
    mid_cut = max(top_cut, math.ceil(term_count * 0.5))
    if index < top_cut:
        return "top"
    if index < mid_cut:
        return "mid"
    return "tail"


def _wordcloud_palette(
    *,
    raw_palette: Any,
    color_mode: str,
    category_count: int,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if raw_palette is None:
        palette = (
            list(_WORDCLOUD_DEFAULT_RANK_TIER_PALETTE)
            if color_mode == "rank_tier"
            else list(_WORDCLOUD_DEFAULT_SEMANTIC_PALETTE)
        )
    else:
        if not isinstance(raw_palette, list) or not raw_palette:
            raise ValidationError("analysis.graph wordcloud_spec.palette must be a non-empty color list.")
        palette = [str(value).strip() for value in raw_palette if str(value).strip()]
        if not palette:
            raise ValidationError("analysis.graph wordcloud_spec.palette must contain non-empty color strings.")
        if len(palette) > _WORDCLOUD_MAX_PALETTE_SIZE:
            raise ValidationError(
                f"analysis.graph wordcloud_spec.palette cannot exceed {_WORDCLOUD_MAX_PALETTE_SIZE} colors."
            )

    if color_mode == "rank_tier":
        if len(palette) < 2:
            _raise_wordcloud_error(
                "analysis.graph wordcloud_spec rank-tier palette needs at least 2 colors.",
                error_code="wordcloud_palette_too_small",
                error_details={"palette_size": len(palette)},
            )
        if len(palette) > 3:
            warnings.append("Wordcloud rank-tier coloring used only the first 3 palette colors.")
            palette = palette[:3]
        return palette, warnings

    if category_count > len(palette):
        _raise_wordcloud_error(
            "analysis.graph wordcloud_spec palette is too small for the semantic color groups.",
            error_code="wordcloud_palette_too_small",
            error_details={"palette_size": len(palette), "category_count": category_count},
            repair_hints=["Reduce category, sentiment, or source groups upstream, or provide a longer palette."],
        )
    return palette, warnings


def _resolve_wordcloud_font_path(contains_cjk: bool) -> Path | None:
    candidates: list[Path] = []
    env_value = str(os.environ.get("XENIX_WORDCLOUD_FONT_PATH") or "").strip()
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            Path(r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\simhei.ttf"),
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/PingFang.ttc"),
            Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    if contains_cjk:
        _raise_wordcloud_error(
            "analysis.graph could not find a usable CJK font for the wordcloud renderer.",
            error_code="wordcloud_font_unavailable",
            retryable=False,
        )
    return None


def _contains_cjk(value: str) -> bool:
    return bool(_CJK_RE.search(value))


def _optional_title(value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValidationError("analysis.graph wordcloud_spec.title must be a string.")
    return value.strip() or default


def _field_name_option(value: Any, *, field_name: str, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_field_name(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string when provided.")
    return value.strip()


def _integer_option(
    value: Any,
    *,
    field_name: str,
    minimum: int,
    maximum: int,
    default: int,
) -> int:
    if value is None:
        return default
    if not isinstance(value, (int, float)) or isinstance(value, bool) or int(value) != value:
        raise ValidationError(f"{field_name} must be an integer between {minimum} and {maximum}.")
    integer = int(value)
    if integer < minimum or integer > maximum:
        raise ValidationError(f"{field_name} must be between {minimum} and {maximum}.")
    return integer


def _float_option(
    value: Any,
    *,
    field_name: str,
    minimum: float,
    maximum: float,
    default: float,
) -> float:
    if value is None:
        return default
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a number between {minimum} and {maximum}.")
    numeric = float(value)
    if numeric < minimum or numeric > maximum:
        raise ValidationError(f"{field_name} must be between {minimum} and {maximum}.")
    return numeric


def _font_size_range_option(value: Any, *, words: list[str]) -> tuple[int, int]:
    if value is None:
        return _default_wordcloud_font_size_range(words)
    if not isinstance(value, list) or len(value) != 2:
        raise ValidationError("analysis.graph wordcloud_spec.font_size_range must be [min, max].")
    low, high = value
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        raise ValidationError("analysis.graph wordcloud_spec.font_size_range must contain two numbers.")
    if isinstance(low, bool) or isinstance(high, bool):
        raise ValidationError("analysis.graph wordcloud_spec.font_size_range must contain two numbers.")
    low_int = int(low)
    high_int = int(high)
    if not (1 <= low_int < high_int <= 200):
        raise ValidationError("analysis.graph wordcloud_spec.font_size_range must satisfy 1 <= min < max <= 200.")
    return low_int, high_int


def _wordcloud_color_mode(value: Any) -> str:
    if value is None:
        return "rank_tier"
    if not isinstance(value, str):
        raise ValidationError("analysis.graph wordcloud_spec.color_mode must be 'rank_tier' or 'field'.")
    normalized = value.strip()
    if normalized not in _WORDCLOUD_COLOR_MODES:
        raise ValidationError("analysis.graph wordcloud_spec.color_mode must be 'rank_tier' or 'field'.")
    return normalized


def _default_wordcloud_font_size_range(words: list[str]) -> tuple[int, int]:
    longest_word = max((len(word) for word in words), default=0)
    if len(words) >= _WORDCLOUD_DENSE_TERM_THRESHOLD or longest_word >= 8:
        return _WORDCLOUD_DENSE_FONT_SIZE_RANGE
    return _WORDCLOUD_DEFAULT_FONT_SIZE_RANGE


def _format_wordcloud_count(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.4g}"


def _raise_wordcloud_error(
    message: str,
    *,
    error_code: str,
    error_details: dict[str, Any] | None = None,
    repair_hints: list[str] | None = None,
    retryable: bool = True,
) -> None:
    hints = list(_WORDCLOUD_REPAIR_HINTS)
    if repair_hints:
        hints.extend(repair_hints)
    raise ValidationError(
        message,
        error_code=error_code,
        error_details=error_details,
        repair_hints=hints,
        retryable=retryable,
    )
