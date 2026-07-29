"""Shared, dependency-free artifacts for the isolated OCR protocol spike."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
import xml.etree.ElementTree as ET
import zlib


MODEL_NAME = "ocr-structured"
MODEL_VERSION = "1"
INPUT_NAME = "image"
OUTPUT_NAMES = ("alto_xml", "page_xml")

ALTO_NAMESPACE = "http://www.loc.gov/standards/alto/ns-v4#"
ALTO_VERSION = "4.4"
PAGE_NAMESPACE = (
    "http://schema.primaresearch.org/PAGE/gts/pagecontent/2024-07-15"
)
PAGE_VERSION = "2024-07-15"

FIXTURE_TEXT = "雨季库存增加20%"
FIXTURE_CONFIDENCE = 0.97
DEMO_WIDTH = 1000
DEMO_HEIGHT = 1400


class ProfileError(ValueError):
    """The payload does not satisfy the spike's fixed OCR profile."""


@dataclass(frozen=True)
class NormalizedRegion:
    text: str
    confidence: float
    polygon: tuple[tuple[int, int], ...]
    page_width: int
    page_height: int
    reading_order: int

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["polygon"] = [list(point) for point in self.polygon]
        return value


def fixture_region(width: int = DEMO_WIDTH, height: int = DEMO_HEIGHT) -> NormalizedRegion:
    if width < 10 or height < 10:
        raise ProfileError("image dimensions must both be at least 10 pixels")
    left = width // 10
    top = height // 7
    right = width * 7 // 10
    bottom = height * 2 // 7
    return NormalizedRegion(
        text=FIXTURE_TEXT,
        confidence=FIXTURE_CONFIDENCE,
        polygon=(
            (left, top + 8),
            (right - 5, top),
            (right, bottom - 7),
            (left - 4, bottom),
        ),
        page_width=width,
        page_height=height,
        reading_order=0,
    )


def _qualified(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def _xml_bytes(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _polygon_text(points: tuple[tuple[int, int], ...]) -> str:
    return " ".join(f"{x},{y}" for x, y in points)


def _bounds(points: tuple[tuple[int, int], ...]) -> tuple[int, int, int, int]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left, top = min(xs), min(ys)
    return left, top, max(xs) - left, max(ys) - top


def render_alto(region: NormalizedRegion) -> bytes:
    """Project one normalized region into ALTO XML 4.4."""

    _validate_region(region)
    ET.register_namespace("", ALTO_NAMESPACE)
    q = lambda name: _qualified(ALTO_NAMESPACE, name)
    left, top, width, height = _bounds(region.polygon)

    root = ET.Element(q("alto"), {"SCHEMAVERSION": ALTO_VERSION})
    description = ET.SubElement(root, q("Description"))
    ET.SubElement(description, q("MeasurementUnit")).text = "pixel"
    reading_order = ET.SubElement(root, q("ReadingOrder"))
    ordered_group = ET.SubElement(reading_order, q("OrderedGroup"), {"ID": "ro_1"})
    ET.SubElement(
        ordered_group,
        q("ElementRef"),
        {"ID": "ro_ref_1", "REF": "region_1"},
    )
    layout = ET.SubElement(root, q("Layout"))
    page = ET.SubElement(
        layout,
        q("Page"),
        {
            "ID": "page_1",
            "PHYSICAL_IMG_NR": "1",
            "WIDTH": str(region.page_width),
            "HEIGHT": str(region.page_height),
            "LANG": "zh-Hans",
        },
    )
    print_space = ET.SubElement(
        page,
        q("PrintSpace"),
        {
            "ID": "print_space_1",
            "HPOS": "0",
            "VPOS": "0",
            "WIDTH": str(region.page_width),
            "HEIGHT": str(region.page_height),
        },
    )
    text_block = ET.SubElement(
        print_space,
        q("TextBlock"),
        {
            "ID": "region_1",
            "HPOS": str(left),
            "VPOS": str(top),
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "LANG": "zh-Hans",
        },
    )
    text_line = ET.SubElement(
        text_block,
        q("TextLine"),
        {
            "ID": "line_1",
            "HPOS": str(left),
            "VPOS": str(top),
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "LANG": "zh-Hans",
        },
    )
    string = ET.SubElement(
        text_line,
        q("String"),
        {
            "ID": "string_1",
            "CONTENT": region.text,
            "WC": _confidence_text(region.confidence),
            "HPOS": str(left),
            "VPOS": str(top),
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "LANG": "zh-Hans",
        },
    )
    shape = ET.SubElement(string, q("Shape"))
    ET.SubElement(shape, q("Polygon"), {"POINTS": _polygon_text(region.polygon)})
    return _xml_bytes(root)


def render_page(region: NormalizedRegion) -> bytes:
    """Project the same normalized region into PRImA PAGE XML 2024-07-15."""

    _validate_region(region)
    ET.register_namespace("", PAGE_NAMESPACE)
    q = lambda name: _qualified(PAGE_NAMESPACE, name)

    root = ET.Element(q("PcGts"), {"pcGtsId": "pcgts_1"})
    metadata = ET.SubElement(root, q("Metadata"))
    ET.SubElement(metadata, q("Creator")).text = "Xenix OCR protocol spike"
    ET.SubElement(metadata, q("Created")).text = "2026-07-26T00:00:00Z"
    ET.SubElement(metadata, q("LastChange")).text = "2026-07-26T00:00:00Z"
    page = ET.SubElement(
        root,
        q("Page"),
        {
            "imageFilename": "request.png",
            "imageWidth": str(region.page_width),
            "imageHeight": str(region.page_height),
        },
    )
    reading_order = ET.SubElement(page, q("ReadingOrder"))
    ordered_group = ET.SubElement(reading_order, q("OrderedGroup"), {"id": "ro_1"})
    ET.SubElement(
        ordered_group,
        q("RegionRefIndexed"),
        {"index": str(region.reading_order), "regionRef": "region_1"},
    )
    text_region = ET.SubElement(
        page,
        q("TextRegion"),
        {"id": "region_1", "type": "paragraph"},
    )
    ET.SubElement(text_region, q("Coords"), {"points": _polygon_text(region.polygon)})
    text_equiv = ET.SubElement(
        text_region,
        q("TextEquiv"),
        {"index": "0", "conf": _confidence_text(region.confidence)},
    )
    ET.SubElement(text_equiv, q("Unicode")).text = region.text
    return _xml_bytes(root)


def parse_alto(payload: bytes) -> NormalizedRegion:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ProfileError(f"invalid ALTO XML: {exc}") from exc
    if root.tag != _qualified(ALTO_NAMESPACE, "alto"):
        raise ProfileError("unexpected ALTO root namespace or element")
    if root.get("SCHEMAVERSION") != ALTO_VERSION:
        raise ProfileError("unexpected ALTO schema version")

    q = lambda name: _qualified(ALTO_NAMESPACE, name)
    page = _required(root.find(f".//{q('Page')}"), "ALTO Page")
    strings = root.findall(f".//{q('String')}")
    if len(strings) != 1:
        raise ProfileError("profile requires exactly one ALTO String")
    string = strings[0]
    text_block = _required(root.find(f".//{q('TextBlock')}"), "ALTO TextBlock")
    region_id = _required_attribute(text_block, "ID")
    references = root.findall(
        f"./{q('ReadingOrder')}/{q('OrderedGroup')}/{q('ElementRef')}"
    )
    matching_indexes = [
        index
        for index, reference in enumerate(references)
        if _required_attribute(reference, "REF") == region_id
    ]
    if len(matching_indexes) != 1:
        raise ProfileError("ALTO reading order must reference the text region once")
    polygon = _required(string.find(f"./{q('Shape')}/{q('Polygon')}"), "ALTO Polygon")
    region = NormalizedRegion(
        text=_required_attribute(string, "CONTENT"),
        confidence=_parse_confidence(_required_attribute(string, "WC")),
        polygon=_parse_points(_required_attribute(polygon, "POINTS")),
        page_width=_parse_positive_int(_required_attribute(page, "WIDTH"), "page width"),
        page_height=_parse_positive_int(_required_attribute(page, "HEIGHT"), "page height"),
        reading_order=matching_indexes[0],
    )
    _validate_region(region)
    return region


def parse_page(payload: bytes) -> NormalizedRegion:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ProfileError(f"invalid PAGE XML: {exc}") from exc
    if root.tag != _qualified(PAGE_NAMESPACE, "PcGts"):
        raise ProfileError("unexpected PAGE root namespace or element")

    q = lambda name: _qualified(PAGE_NAMESPACE, name)
    page = _required(root.find(f"./{q('Page')}"), "PAGE Page")
    regions = page.findall(f"./{q('TextRegion')}")
    if len(regions) != 1:
        raise ProfileError("profile requires exactly one PAGE TextRegion")
    text_region = regions[0]
    region_id = _required_attribute(text_region, "id")
    coords = _required(text_region.find(f"./{q('Coords')}"), "PAGE Coords")
    text_equiv = _required(text_region.find(f"./{q('TextEquiv')}"), "PAGE TextEquiv")
    unicode_text = _required(text_equiv.find(f"./{q('Unicode')}"), "PAGE Unicode")
    ref = _required(
        page.find(
            f"./{q('ReadingOrder')}/{q('OrderedGroup')}/{q('RegionRefIndexed')}"
        ),
        "PAGE RegionRefIndexed",
    )
    if _required_attribute(ref, "regionRef") != region_id:
        raise ProfileError("PAGE reading order does not reference the text region")

    region = NormalizedRegion(
        text=unicode_text.text or "",
        confidence=_parse_confidence(_required_attribute(text_equiv, "conf")),
        polygon=_parse_points(_required_attribute(coords, "points")),
        page_width=_parse_positive_int(
            _required_attribute(page, "imageWidth"), "page width"
        ),
        page_height=_parse_positive_int(
            _required_attribute(page, "imageHeight"), "page height"
        ),
        reading_order=int(_required_attribute(ref, "index")),
    )
    _validate_region(region)
    return region


def make_demo_png(width: int = DEMO_WIDTH, height: int = DEMO_HEIGHT) -> bytes:
    """Create a valid RGB PNG with only standard-library compression."""

    if width < 1 or height < 1:
        raise ProfileError("PNG dimensions must be positive")

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind)
        checksum = zlib.crc32(data, checksum)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    white_row = b"\x00" + (b"\xff\xff\xff" * width)
    pixels = zlib.compress(white_row * height, level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 24 or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProfileError("input BYTES element is not a PNG image")
    if payload[12:16] != b"IHDR":
        raise ProfileError("PNG does not begin with an IHDR chunk")
    width, height = struct.unpack(">II", payload[16:24])
    if width < 10 or height < 10 or width > 20_000 or height > 20_000:
        raise ProfileError("PNG dimensions are outside the profile bounds")
    return width, height


def _parse_points(value: str) -> tuple[tuple[int, int], ...]:
    points: list[tuple[int, int]] = []
    for token in value.split():
        components = token.split(",")
        if len(components) != 2:
            raise ProfileError(f"invalid polygon point: {token!r}")
        try:
            points.append((int(components[0]), int(components[1])))
        except ValueError as exc:
            raise ProfileError(f"invalid polygon point: {token!r}") from exc
    if len(points) < 3:
        raise ProfileError("polygon must contain at least three points")
    return tuple(points)


def _validate_region(region: NormalizedRegion) -> None:
    if not region.text:
        raise ProfileError("region text must not be empty")
    if not 0.0 <= region.confidence <= 1.0:
        raise ProfileError("confidence must be between 0 and 1")
    if region.reading_order < 0:
        raise ProfileError("reading order must not be negative")
    if len(region.polygon) < 3:
        raise ProfileError("polygon must contain at least three points")
    for x, y in region.polygon:
        if (
            not isinstance(x, int)
            or isinstance(x, bool)
            or not isinstance(y, int)
            or isinstance(y, bool)
        ):
            raise ProfileError(
                "profile requires integer pixel coordinates; fractional polygons "
                "must be explicitly quantized before serialization"
            )
        if not 0 <= x <= region.page_width or not 0 <= y <= region.page_height:
            raise ProfileError("polygon point lies outside the page")


def _confidence_text(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _parse_confidence(value: str) -> float:
    try:
        confidence = float(value)
    except ValueError as exc:
        raise ProfileError("confidence is not numeric") from exc
    if not 0.0 <= confidence <= 1.0:
        raise ProfileError("confidence must be between 0 and 1")
    return confidence


def _parse_positive_int(value: str, label: str) -> int:
    try:
        number = int(float(value))
    except ValueError as exc:
        raise ProfileError(f"{label} is not numeric") from exc
    if number <= 0:
        raise ProfileError(f"{label} must be positive")
    return number


def _required(element: ET.Element | None, label: str) -> ET.Element:
    if element is None:
        raise ProfileError(f"missing {label}")
    return element


def _required_attribute(element: ET.Element, name: str) -> str:
    value = element.get(name)
    if value is None:
        raise ProfileError(f"missing {name} attribute")
    return value
