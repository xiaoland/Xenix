from __future__ import annotations

import argparse
import json
import math
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rapidocr import EngineType, RapidOCR


MODEL_NAME = "rapidocr-ppocrv6"
MODEL_VERSION = "rapidocr-3.9.2-rocm721"
INPUT_NAME = "image"
OUTPUT_NAME = "page_xml"
PAGE_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2024-07-15"
PAGE_SCHEMA_VERSION = "2024-07-15"
PROFILE_VERSION = "page-xml-text-regions-v1"
MAX_JSON_HEADER_BYTES = 64 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class RequestError(ValueError):
    pass


class RapidOcrBackend:
    def __init__(self, model_root: Path):
        self.model_root = model_root
        self.engine = RapidOCR(
            params={
                "Global.model_root_dir": str(model_root),
                "Global.font_path": str(model_root / "FZYTK.TTF"),
                "EngineConfig.torch.use_cuda": True,
                "EngineConfig.torch.cuda_ep_cfg.device_id": 0,
                "Det.engine_type": EngineType.TORCH,
                "Det.model_path": str(model_root / "PP-OCRv6_det_small.pth"),
                "Cls.engine_type": EngineType.TORCH,
                "Cls.model_path": str(
                    model_root / "ch_ptocr_mobile_v2.0_cls_mobile.pth"
                ),
                "Rec.engine_type": EngineType.TORCH,
                "Rec.model_path": str(model_root / "PP-OCRv6_rec_small.pth"),
                "Rec.rec_keys_path": str(model_root / "ppocrv6_dict.txt"),
            }
        )
        sessions = (
            self.engine.text_det.session,
            self.engine.text_cls.session,
            self.engine.text_rec.session,
        )
        if any(session.device.type != "cuda" for session in sessions):
            raise RuntimeError("RapidOCR stage did not bind to the ROCm device")

    def infer(self, image: bytes) -> bytes:
        width, height = _png_dimensions(image)
        result = self.engine(image)
        if result.boxes is None or result.txts is None or result.scores is None:
            raise RequestError("OCR produced no structured regions")
        regions = []
        for box, text, confidence in zip(
            result.boxes,
            result.txts,
            result.scores,
            strict=True,
        ):
            normalized_text = str(text).strip()
            if not normalized_text:
                continue
            polygon = tuple(
                (
                    min(width, max(0, _round_pixel(float(point[0])))),
                    min(height, max(0, _round_pixel(float(point[1])))),
                )
                for point in box
            )
            if len(set(polygon)) < 3:
                raise RequestError("OCR produced a degenerate polygon")
            normalized_confidence = float(confidence)
            if not math.isfinite(normalized_confidence) or not (
                0.0 <= normalized_confidence <= 1.0
            ):
                raise RequestError("OCR produced an invalid confidence")
            regions.append((polygon, normalized_text, normalized_confidence))
        if not regions:
            raise RequestError("OCR produced no non-empty text regions")
        return _render_page(width, height, regions)


class OcrHttpServer(HTTPServer):
    def __init__(self, address: tuple[str, int], backend: RapidOcrBackend):
        super().__init__(address, OcrHandler)
        self.backend = backend


class OcrHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "XenixRapidOcrKServeSpike/1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/v2":
            self._send_json(
                HTTPStatus.OK,
                {
                    "name": "xenix-rapidocr-rocm-spike",
                    "version": MODEL_VERSION,
                    "extensions": ["binary_tensor_data"],
                },
            )
            return
        if path in {"/v2/health/live", "/v2/health/ready"}:
            self._send_empty(HTTPStatus.OK)
            return
        if path == f"/v2/models/{MODEL_NAME}":
            self._send_json(
                HTTPStatus.OK,
                {
                    "name": MODEL_NAME,
                    "versions": [MODEL_VERSION],
                    "platform": "pytorch_rocm",
                    "inputs": [
                        {"name": INPUT_NAME, "datatype": "BYTES", "shape": [1]}
                    ],
                    "outputs": [
                        {"name": OUTPUT_NAME, "datatype": "BYTES", "shape": [1]}
                    ],
                },
            )
            return
        if path == f"/v2/models/{MODEL_NAME}/ready":
            self._send_empty(HTTPStatus.OK)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "unknown V2 endpoint")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        if path != f"/v2/models/{MODEL_NAME}/infer":
            self._send_error(HTTPStatus.NOT_FOUND, "unknown inference endpoint")
            return
        try:
            header, image = self._read_request()
            request_id = header.get("id")
            if request_id is not None and not isinstance(request_id, str):
                raise RequestError("request id must be a string")
            self._validate_outputs(header)
            server = self.server
            assert isinstance(server, OcrHttpServer)
            page_xml = server.backend.infer(image)
            binary = struct.pack("<I", len(page_xml)) + page_xml
            response: dict[str, Any] = {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "outputs": [
                    {
                        "name": OUTPUT_NAME,
                        "shape": [1],
                        "datatype": "BYTES",
                        "parameters": {
                            "binary_data_size": len(binary),
                            "content_type": "application/xml",
                            "schema_version": PAGE_SCHEMA_VERSION,
                            "profile": PROFILE_VERSION,
                            "coordinate_quantization": "round-half-up-clamped",
                        },
                    }
                ],
            }
            if request_id is not None:
                response["id"] = request_id
            json_header = _json_bytes(response)
            body = json_header + binary
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Inference-Header-Content-Length", str(len(json_header)))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except RequestError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _read_request(self) -> tuple[dict[str, Any], bytes]:
        if self.headers.get_content_type() != "application/octet-stream":
            raise RequestError("Binary Tensor Data Extension is required")
        total_length = self._integer_header("Content-Length")
        header_length = self._integer_header("Inference-Header-Content-Length")
        if header_length <= 0 or header_length > MAX_JSON_HEADER_BYTES:
            raise RequestError("invalid inference JSON header length")
        if total_length <= header_length:
            raise RequestError("request is missing binary tensor data")
        if total_length > MAX_JSON_HEADER_BYTES + MAX_IMAGE_BYTES + 4:
            raise RequestError("request body exceeds the profile limit")
        body = self.rfile.read(total_length)
        if len(body) != total_length:
            raise RequestError("request body ended before Content-Length")
        try:
            header = json.loads(body[:header_length].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError("invalid UTF-8 JSON inference header") from exc
        if not isinstance(header, dict):
            raise RequestError("inference header must be an object")
        binary = body[header_length:]
        inputs = header.get("inputs")
        if not isinstance(inputs, list) or len(inputs) != 1:
            raise RequestError("profile requires exactly one input tensor")
        tensor = inputs[0]
        if not isinstance(tensor, dict):
            raise RequestError("input tensor must be an object")
        if (
            tensor.get("name") != INPUT_NAME
            or tensor.get("datatype") != "BYTES"
            or tensor.get("shape") != [1]
        ):
            raise RequestError("image input must be BYTES[1]")
        if "data" in tensor:
            raise RequestError("binary input must not contain JSON data")
        parameters = tensor.get("parameters")
        if not isinstance(parameters, dict):
            raise RequestError("input tensor parameters are required")
        if parameters.get("content_type") != "image/png":
            raise RequestError("image content_type must be image/png")
        if parameters.get("binary_data_size") != len(binary):
            raise RequestError("binary_data_size does not match request body")
        if len(binary) < 4:
            raise RequestError("BYTES tensor is missing its length prefix")
        image_size = struct.unpack("<I", binary[:4])[0]
        image = binary[4:]
        if image_size != len(image):
            raise RequestError("BYTES length prefix does not match image size")
        if len(image) > MAX_IMAGE_BYTES:
            raise RequestError("image exceeds the profile limit")
        _png_dimensions(image)
        return header, image

    @staticmethod
    def _validate_outputs(header: dict[str, Any]) -> None:
        outputs = header.get("outputs")
        if not isinstance(outputs, list) or len(outputs) != 1:
            raise RequestError("profile requires exactly one output")
        output = outputs[0]
        if not isinstance(output, dict) or output.get("name") != OUTPUT_NAME:
            raise RequestError(f"output must be {OUTPUT_NAME!r}")
        parameters = output.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("binary_data") is not True:
            raise RequestError("PAGE output must request binary_data=true")

    def _integer_header(self, name: str) -> int:
        raw = self.headers.get(name)
        try:
            value = int(raw) if raw is not None else -1
        except ValueError as exc:
            raise RequestError(f"{name} must be an integer") from exc
        return value

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_json(self, status: HTTPStatus, value: object) -> None:
        body = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def log_message(self, format: str, *args: object) -> None:
        print(
            f"{self.log_date_time_string()} {self.client_address[0]} "
            f"{format % args}",
            flush=True,
        )


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _round_pixel(value: float) -> int:
    if not math.isfinite(value):
        raise RequestError("OCR produced a non-finite coordinate")
    return math.floor(value + 0.5)


def _png_dimensions(image: bytes) -> tuple[int, int]:
    if len(image) < 24 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RequestError("input is not a PNG")
    if image[12:16] != b"IHDR":
        raise RequestError("PNG does not start with IHDR")
    width, height = struct.unpack(">II", image[16:24])
    if not 10 <= width <= 20_000 or not 10 <= height <= 20_000:
        raise RequestError("PNG dimensions are outside the profile bounds")
    return width, height


def _render_page(
    width: int,
    height: int,
    regions: list[tuple[tuple[tuple[int, int], ...], str, float]],
) -> bytes:
    ET.register_namespace("", PAGE_NAMESPACE)
    q = lambda name: f"{{{PAGE_NAMESPACE}}}{name}"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    root = ET.Element(q("PcGts"), {"pcGtsId": "pcgts_1"})
    metadata = ET.SubElement(root, q("Metadata"))
    ET.SubElement(metadata, q("Creator")).text = "Xenix RapidOCR ROCm spike"
    ET.SubElement(metadata, q("Created")).text = now
    ET.SubElement(metadata, q("LastChange")).text = now
    page = ET.SubElement(
        root,
        q("Page"),
        {
            "imageFilename": "request.png",
            "imageWidth": str(width),
            "imageHeight": str(height),
        },
    )
    reading_order = ET.SubElement(page, q("ReadingOrder"))
    group = ET.SubElement(reading_order, q("OrderedGroup"), {"id": "reading_order_1"})
    for index, (polygon, text, confidence) in enumerate(regions):
        region_id = f"region_{index + 1}"
        ET.SubElement(
            group,
            q("RegionRefIndexed"),
            {"index": str(index), "regionRef": region_id},
        )
        text_region = ET.SubElement(
            page,
            q("TextRegion"),
            {"id": region_id, "type": "other"},
        )
        ET.SubElement(
            text_region,
            q("Coords"),
            {"points": " ".join(f"{x},{y}" for x, y in polygon)},
        )
        text_equiv = ET.SubElement(
            text_region,
            q("TextEquiv"),
            {"index": "1", "conf": f"{confidence:.6f}".rstrip("0").rstrip(".")},
        )
        ET.SubElement(text_equiv, q("Unicode")).text = text
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8103)
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("/opt/xenix-rocm-lab/models/rapidocr-3.9.2"),
    )
    args = parser.parse_args()
    backend = RapidOcrBackend(args.model_root)
    server = OcrHttpServer((args.host, args.port), backend)
    print(f"READY http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
