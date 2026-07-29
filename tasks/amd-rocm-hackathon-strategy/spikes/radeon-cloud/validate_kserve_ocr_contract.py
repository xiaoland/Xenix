from __future__ import annotations

import argparse
import json
import struct
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


MODEL_NAME = "rapidocr-ppocrv6"
MODEL_VERSION = "rapidocr-3.9.2-rocm721"
PAGE_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2024-07-15"


def _get(url: str, *, timeout: float) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def _infer(
    base_url: str,
    image: bytes,
    *,
    request_id: str,
    timeout: float,
) -> tuple[dict[str, Any], bytes]:
    packed_image = struct.pack("<I", len(image)) + image
    header = {
        "id": request_id,
        "inputs": [
            {
                "name": "image",
                "datatype": "BYTES",
                "shape": [1],
                "parameters": {
                    "binary_data_size": len(packed_image),
                    "content_type": "image/png",
                },
            }
        ],
        "outputs": [{"name": "page_xml", "parameters": {"binary_data": True}}],
    }
    json_header = json.dumps(header, separators=(",", ":")).encode("utf-8")
    body = json_header + packed_image
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v2/models/{MODEL_NAME}/infer",
        data=body,
        headers={
            "Content-Type": "application/octet-stream",
            "Inference-Header-Content-Length": str(len(json_header)),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "application/octet-stream"
        raw = response.read()
        response_header_length = int(
            response.headers["Inference-Header-Content-Length"]
        )
    response_header = json.loads(raw[:response_header_length].decode("utf-8"))
    assert isinstance(response_header, dict)
    binary = raw[response_header_length:]
    outputs = response_header.get("outputs")
    assert isinstance(outputs, list) and len(outputs) == 1
    output = outputs[0]
    assert isinstance(output, dict)
    assert output.get("name") == "page_xml"
    assert output.get("datatype") == "BYTES"
    assert output.get("shape") == [1]
    parameters = output.get("parameters")
    assert isinstance(parameters, dict)
    assert parameters.get("binary_data_size") == len(binary)
    assert parameters.get("content_type") == "application/xml"
    assert parameters.get("schema_version") == "2024-07-15"
    assert parameters.get("profile") == "page-xml-text-regions-v1"
    assert parameters.get("coordinate_quantization") == "round-half-up-clamped"
    assert len(binary) >= 4
    element_size = struct.unpack("<I", binary[:4])[0]
    page_xml = binary[4:]
    assert element_size == len(page_xml)
    return response_header, page_xml


def _parse_page(page_xml: bytes) -> dict[str, Any]:
    root = ET.fromstring(page_xml)
    q = lambda name: f"{{{PAGE_NAMESPACE}}}{name}"
    assert root.tag == q("PcGts")
    page = root.find(f"./{q('Page')}")
    assert page is not None
    width = int(page.attrib["imageWidth"])
    height = int(page.attrib["imageHeight"])
    regions = page.findall(f"./{q('TextRegion')}")
    refs = page.findall(
        f"./{q('ReadingOrder')}/{q('OrderedGroup')}/{q('RegionRefIndexed')}"
    )
    assert regions
    assert len(regions) == len(refs)
    assert [int(ref.attrib["index"]) for ref in refs] == list(range(len(refs)))
    region_ids = [region.attrib["id"] for region in regions]
    assert [ref.attrib["regionRef"] for ref in refs] == region_ids
    normalized = []
    for region in regions:
        assert region.attrib["type"] == "other"
        coords = region.find(f"./{q('Coords')}")
        text_equiv = region.find(f"./{q('TextEquiv')}")
        assert coords is not None and text_equiv is not None
        assert text_equiv.attrib["index"] == "1"
        confidence = float(text_equiv.attrib["conf"])
        assert 0.0 <= confidence <= 1.0
        unicode_text = text_equiv.find(f"./{q('Unicode')}")
        assert unicode_text is not None and unicode_text.text
        points = []
        for token in coords.attrib["points"].split():
            x_text, y_text = token.split(",", maxsplit=1)
            x, y = int(x_text), int(y_text)
            assert 0 <= x <= width and 0 <= y <= height
            points.append([x, y])
        assert len(set(map(tuple, points))) >= 3
        normalized.append(
            {
                "id": region.attrib["id"],
                "text": unicode_text.text,
                "confidence": confidence,
                "polygon": points,
            }
        )
    return {
        "page_width": width,
        "page_height": height,
        "regions": normalized,
    }


def _expect_error(
    request: urllib.request.Request,
    *,
    expected_status: int,
    timeout: float,
) -> dict[str, Any]:
    try:
        urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        assert exc.code == expected_status
        parsed = json.loads(exc.read().decode("utf-8"))
        assert isinstance(parsed, dict) and isinstance(parsed.get("error"), str)
        return parsed
    raise AssertionError(f"Expected HTTP {expected_status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8103")
    parser.add_argument(
        "--image",
        type=Path,
        default=Path("/workspace/xenix-rocm-lab/evidence/rapidocr-fixture.png"),
    )
    parser.add_argument("--page-output", type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    server_status, server_raw = _get(f"{base_url}/v2", timeout=args.timeout)
    assert server_status == 200
    server_metadata = json.loads(server_raw.decode("utf-8"))
    assert server_metadata["extensions"] == ["binary_tensor_data"]
    assert _get(f"{base_url}/v2/health/live", timeout=args.timeout)[0] == 200
    assert _get(f"{base_url}/v2/health/ready", timeout=args.timeout)[0] == 200
    assert (
        _get(
            f"{base_url}/v2/models/{MODEL_NAME}/ready",
            timeout=args.timeout,
        )[0]
        == 200
    )
    _, model_raw = _get(f"{base_url}/v2/models/{MODEL_NAME}", timeout=args.timeout)
    model_metadata = json.loads(model_raw.decode("utf-8"))
    assert model_metadata["name"] == MODEL_NAME
    assert model_metadata["versions"] == [MODEL_VERSION]
    assert model_metadata["platform"] == "pytorch_rocm"

    response_header, page_xml = _infer(
        base_url,
        args.image.read_bytes(),
        request_id="xenix-rocm-ocr-contract",
        timeout=args.timeout,
    )
    if args.page_output is not None:
        args.page_output.parent.mkdir(parents=True, exist_ok=True)
        args.page_output.write_bytes(page_xml)
    assert response_header["id"] == "xenix-rocm-ocr-contract"
    assert response_header["model_name"] == MODEL_NAME
    assert response_header["model_version"] == MODEL_VERSION
    normalized = _parse_page(page_xml)
    recognized = "\n".join(region["text"] for region in normalized["regions"])
    for expected in (
        "AMD Radeon GPU 文档识别",
        "ROCm 7.2.1 私有部署",
        "Invoice No. XENIX-2026",
    ):
        assert expected in recognized, (expected, recognized)

    wrong_content_type = _expect_error(
        urllib.request.Request(
            f"{base_url}/v2/models/{MODEL_NAME}/infer",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        expected_status=400,
        timeout=args.timeout,
    )
    unknown_model = _expect_error(
        urllib.request.Request(
            f"{base_url}/v2/models/unknown/infer",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        expected_status=404,
        timeout=args.timeout,
    )

    evidence = {
        "server_metadata": server_metadata,
        "model_metadata": model_metadata,
        "response_header": response_header,
        "normalized_page": normalized,
        "wrong_content_type": wrong_content_type,
        "unknown_model": unknown_model,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
