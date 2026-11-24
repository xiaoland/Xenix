from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...config import AppPaths
from ...exceptions import ValidationError, report_exception

SVG_NS = "http://www.w3.org/2000/svg"
SVG_STYLE_TAGS = {f"{{{SVG_NS}}}style", f"{{{SVG_NS}}}defs", f"{{{SVG_NS}}}metadata"}

ET.register_namespace("", SVG_NS)


def normalize_svg_for_qt(svg: str) -> str:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValidationError("analysis.graph renderer did not return a valid SVG image.") from exc
    _remove_empty_path_elements(root)
    return serialize_svg(root)


def _remove_empty_path_elements(parent: ET.Element) -> None:
    for child in list(parent):
        _remove_empty_path_elements(child)
        if _is_empty_path_element(child):
            parent.remove(child)


def _is_empty_path_element(element: ET.Element) -> bool:
    tag_name = element.tag.rsplit("}", 1)[-1]
    if tag_name != "path":
        return False
    return not str(element.attrib.get("d") or "").strip()


def serialize_svg(root: ET.Element) -> str:
    # XML libraries loaded by optional document runtimes may replace the
    # process-wide ElementTree prefix for SVG. Reassert the public artifact
    # contract at the serialization boundary instead of relying on import order.
    ET.register_namespace("", SVG_NS)
    return ET.tostring(root, encoding="unicode")


def write_svg_output(paths: AppPaths, *, svg: str, dataset_name: str, suffix: str) -> Path:
    output_dir = paths.artifacts / "analysis" / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug(dataset_name)}-{suffix}-{uuid4().hex[:12]}.svg"
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def allocate_hidden_console_for_packaged_windows() -> Any:
    """Give vl_convert a hidden console on windowed frozen builds.

    A GUI (no-console) frozen process can fail when the native vl_convert
    binary touches the console, so allocate a hidden one and free it after.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return None
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        if kernel32.GetConsoleWindow():
            return None
        if not kernel32.AllocConsole():
            return None
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        return kernel32
    except Exception as exc:
        report_exception(exc)
        return None


def slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return normalized or "graph"
