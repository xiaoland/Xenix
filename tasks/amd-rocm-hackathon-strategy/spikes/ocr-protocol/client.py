"""Minimal stdlib client for the fixed KServe V2 OCR profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from ocr_profile import (
    INPUT_NAME,
    MODEL_NAME,
    OUTPUT_NAMES,
    ProfileError,
    make_demo_png,
    parse_alto,
    parse_page,
)


class ClientError(RuntimeError):
    pass


def infer(base_url: str, image: bytes, request_id: str) -> dict[str, object]:
    packed_image = struct.pack("<I", len(image)) + image
    request_header = {
        "id": request_id,
        "inputs": [
            {
                "name": INPUT_NAME,
                "shape": [1],
                "datatype": "BYTES",
                "parameters": {
                    "binary_data_size": len(packed_image),
                    "content_type": "image/png",
                },
            }
        ],
        "outputs": [
            {"name": name, "parameters": {"binary_data": True}}
            for name in OUTPUT_NAMES
        ],
    }
    json_header = json.dumps(
        request_header, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    body = json_header + packed_image
    request = Request(
        f"{base_url.rstrip('/')}/v2/models/{MODEL_NAME}/infer",
        data=body,
        headers={
            "Content-Type": "application/octet-stream",
            "Inference-Header-Content-Length": str(len(json_header)),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            response_body = response.read()
            content_type = response.headers.get_content_type()
            raw_header_length = response.headers.get(
                "Inference-Header-Content-Length"
            )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ClientError(f"server returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ClientError(f"request failed: {exc.reason}") from exc

    if content_type != "application/octet-stream" or raw_header_length is None:
        raise ClientError("server did not return a binary tensor response")
    try:
        header_length = int(raw_header_length)
        response_header = json.loads(response_body[:header_length].decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientError("invalid binary response JSON header") from exc
    documents = _unpack_outputs(response_header, response_body[header_length:])

    try:
        alto_region = parse_alto(documents["alto_xml"])
        page_region = parse_page(documents["page_xml"])
    except (KeyError, ProfileError) as exc:
        raise ClientError(f"invalid OCR document output: {exc}") from exc
    if alto_region != page_region:
        raise ClientError("ALTO and PAGE outputs do not normalize to the same region")

    return {
        "request_id": response_header.get("id"),
        "model_name": response_header.get("model_name"),
        "model_version": response_header.get("model_version"),
        "formats": ["ALTO 4.4", "PAGE XML 2024-07-15"],
        "normalized_region": alto_region.to_dict(),
        "round_trip_equal": True,
    }


def _unpack_outputs(
    response_header: dict[str, Any], binary: bytes
) -> dict[str, bytes]:
    outputs = response_header.get("outputs")
    if not isinstance(outputs, list):
        raise ClientError("response outputs must be an array")
    documents: dict[str, bytes] = {}
    offset = 0
    for output in outputs:
        if not isinstance(output, dict):
            raise ClientError("response output must be an object")
        name = output.get("name")
        parameters = output.get("parameters")
        if name not in OUTPUT_NAMES or not isinstance(parameters, dict):
            raise ClientError("response output is outside the fixed profile")
        size = parameters.get("binary_data_size")
        if not isinstance(size, int) or size < 4:
            raise ClientError("invalid response binary_data_size")
        chunk = binary[offset : offset + size]
        if len(chunk) != size:
            raise ClientError("binary response ended before the declared output size")
        element_size = struct.unpack("<I", chunk[:4])[0]
        element = chunk[4:]
        if element_size != len(element):
            raise ClientError("BYTES output length prefix does not match its payload")
        documents[name] = element
        offset += size
    if offset != len(binary):
        raise ClientError("binary response contains trailing bytes")
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--image",
        type=Path,
        help="PNG input; when omitted, generate a valid 1000x1400 demo PNG",
    )
    parser.add_argument("--request-id", default=f"spike-{uuid4()}")
    args = parser.parse_args()

    try:
        image = args.image.read_bytes() if args.image else make_demo_png()
        result = infer(args.base_url, image, args.request_id)
    except (OSError, ClientError, ProfileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
