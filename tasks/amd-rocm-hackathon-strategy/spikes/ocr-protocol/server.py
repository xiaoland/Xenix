"""Minimal KServe V2 HTTP/REST OCR profile server using only the stdlib."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
from typing import Any
from urllib.parse import urlsplit

from ocr_profile import (
    INPUT_NAME,
    MODEL_NAME,
    MODEL_VERSION,
    OUTPUT_NAMES,
    ProfileError,
    fixture_region,
    png_dimensions,
    render_alto,
    render_page,
)


MAX_JSON_HEADER_BYTES = 64 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
EXTENSION_NAME = "binary_tensor_data"


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")


def _pack_bytes_element(value: bytes) -> bytes:
    return struct.pack("<I", len(value)) + value


class OcrProfileHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "XenixOcrProtocolSpike/1"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/v2":
            self._send_json(
                HTTPStatus.OK,
                {
                    "name": "xenix-ocr-protocol-spike",
                    "version": "1",
                    "extensions": [EXTENSION_NAME],
                },
            )
            return
        if path == "/v2/health/live":
            self._send_json(HTTPStatus.OK, {"live": True})
            return
        if path == "/v2/health/ready":
            self._send_json(HTTPStatus.OK, {"ready": True})
            return
        if self._is_model_path(path, suffix=""):
            self._send_json(
                HTTPStatus.OK,
                {
                    "name": MODEL_NAME,
                    "versions": [MODEL_VERSION],
                    "platform": "xenix_ocr_protocol_spike",
                    "inputs": [
                        {"name": INPUT_NAME, "datatype": "BYTES", "shape": [1]}
                    ],
                    "outputs": [
                        {"name": name, "datatype": "BYTES", "shape": [1]}
                        for name in OUTPUT_NAMES
                    ],
                },
            )
            return
        if self._is_model_path(path, suffix="/ready"):
            self._send_json(HTTPStatus.OK, {"name": MODEL_NAME, "ready": True})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "unknown V2 endpoint")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path.rstrip("/")
        if not self._is_model_path(path, suffix="/infer"):
            self._send_error(HTTPStatus.NOT_FOUND, "unknown inference endpoint")
            return
        try:
            request, image = self._read_inference_request()
            selected_outputs = self._validate_request(request)
            width, height = png_dimensions(image)
            region = fixture_region(width, height)
            documents = {
                "alto_xml": (render_alto(region), "4.4"),
                "page_xml": (render_page(region), "2024-07-15"),
            }
            response_outputs: list[dict[str, Any]] = []
            binary_chunks: list[bytes] = []
            for name in selected_outputs:
                document, schema_version = documents[name]
                packed = _pack_bytes_element(document)
                response_outputs.append(
                    {
                        "name": name,
                        "shape": [1],
                        "datatype": "BYTES",
                        "parameters": {
                            "binary_data_size": len(packed),
                            "content_type": "application/xml",
                            "schema_version": schema_version,
                        },
                    }
                )
                binary_chunks.append(packed)
            response: dict[str, Any] = {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "outputs": response_outputs,
            }
            if "id" in request:
                response["id"] = request["id"]
            self._send_binary_response(response, b"".join(binary_chunks))
        except ProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _read_inference_request(self) -> tuple[dict[str, Any], bytes]:
        if self.headers.get_content_type() != "application/octet-stream":
            raise ProfileError(
                "this OCR profile requires the optional Binary Tensor Data Extension"
            )
        total_length = self._integer_header("Content-Length")
        header_length = self._integer_header("Inference-Header-Content-Length")
        if header_length > MAX_JSON_HEADER_BYTES:
            raise ProfileError("JSON inference header exceeds the profile limit")
        if total_length <= header_length:
            raise ProfileError("request is missing binary tensor data")
        if total_length > MAX_JSON_HEADER_BYTES + MAX_IMAGE_BYTES + 4:
            raise ProfileError("request body exceeds the profile limit")
        body = self.rfile.read(total_length)
        if len(body) != total_length:
            raise ProfileError("request body ended before Content-Length")
        try:
            request = json.loads(body[:header_length].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProfileError("invalid UTF-8 JSON inference header") from exc
        if not isinstance(request, dict):
            raise ProfileError("inference header must be a JSON object")
        binary = body[header_length:]
        return request, self._unpack_image_tensor(request, binary)

    def _unpack_image_tensor(
        self, request: dict[str, Any], binary: bytes
    ) -> bytes:
        inputs = request.get("inputs")
        if not isinstance(inputs, list) or len(inputs) != 1:
            raise ProfileError("profile requires exactly one input tensor")
        input_tensor = inputs[0]
        if not isinstance(input_tensor, dict):
            raise ProfileError("input tensor must be an object")
        if input_tensor.get("name") != INPUT_NAME:
            raise ProfileError(f"input tensor name must be {INPUT_NAME!r}")
        if input_tensor.get("datatype") != "BYTES" or input_tensor.get("shape") != [1]:
            raise ProfileError("image input must have datatype BYTES and shape [1]")
        if "data" in input_tensor:
            raise ProfileError("binary input must not contain JSON data")
        parameters = input_tensor.get("parameters")
        if not isinstance(parameters, dict):
            raise ProfileError("binary input parameters are required")
        if parameters.get("content_type") != "image/png":
            raise ProfileError("image content_type must be image/png")
        binary_size = parameters.get("binary_data_size")
        if not isinstance(binary_size, int) or binary_size != len(binary):
            raise ProfileError("binary_data_size does not match the request body")
        if len(binary) < 4:
            raise ProfileError("BYTES tensor is missing its 4-byte length prefix")
        image_size = struct.unpack("<I", binary[:4])[0]
        image = binary[4:]
        if image_size != len(image):
            raise ProfileError("BYTES length prefix does not match the image size")
        if len(image) > MAX_IMAGE_BYTES:
            raise ProfileError("image exceeds the profile limit")
        return image

    def _validate_request(self, request: dict[str, Any]) -> list[str]:
        request_id = request.get("id")
        if request_id is not None and not isinstance(request_id, str):
            raise ProfileError("request id must be a string")
        requested = request.get("outputs")
        all_binary = (
            isinstance(request.get("parameters"), dict)
            and request["parameters"].get("binary_data_output") is True
        )
        if requested is None:
            if not all_binary:
                raise ProfileError("binary_data_output=true is required for implicit outputs")
            return list(OUTPUT_NAMES)
        if not isinstance(requested, list) or not requested:
            raise ProfileError("outputs must be a non-empty array")
        selected: list[str] = []
        for output in requested:
            if not isinstance(output, dict) or output.get("name") not in OUTPUT_NAMES:
                raise ProfileError("requested output is not part of the fixed profile")
            name = output["name"]
            if name in selected:
                raise ProfileError("requested outputs must not contain duplicates")
            parameters = output.get("parameters")
            if not all_binary and (
                not isinstance(parameters, dict)
                or parameters.get("binary_data") is not True
            ):
                raise ProfileError(
                    f"output {name!r} must request binary_data=true"
                )
            selected.append(name)
        return selected

    def _integer_header(self, name: str) -> int:
        value = self.headers.get(name)
        try:
            parsed = int(value) if value is not None else -1
        except ValueError as exc:
            raise ProfileError(f"{name} must be an integer") from exc
        if parsed < 0:
            raise ProfileError(f"{name} is required")
        return parsed

    def _is_model_path(self, path: str, suffix: str) -> bool:
        return path in {
            f"/v2/models/{MODEL_NAME}{suffix}",
            f"/v2/models/{MODEL_NAME}/versions/{MODEL_VERSION}{suffix}",
        }

    def _send_binary_response(
        self, response_header: dict[str, Any], binary: bytes
    ) -> None:
        header = _json_bytes(response_header)
        body = header + binary
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Inference-Header-Content-Length", str(len(header)))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, value: object) -> None:
        body = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), OcrProfileHandler)
    server.daemon_threads = True
    host, port = server.server_address[:2]
    print(
        json.dumps({"base_url": f"http://{host}:{port}"}, separators=(",", ":")),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
