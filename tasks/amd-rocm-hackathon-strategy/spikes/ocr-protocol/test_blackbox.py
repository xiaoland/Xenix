"""Black-box wire and CLI verification for the isolated OCR profile spike."""

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ocr_profile import (
    FIXTURE_CONFIDENCE,
    FIXTURE_TEXT,
    INPUT_NAME,
    MODEL_NAME,
    NormalizedRegion,
    OUTPUT_NAMES,
    ProfileError,
    make_demo_png,
    parse_alto,
    parse_page,
    render_alto,
    render_page,
    fixture_region,
)


ROOT = Path(__file__).resolve().parent


def _json_get(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:
        if response.status != HTTPStatus.OK:
            raise AssertionError(f"unexpected HTTP status: {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _binary_request(
    base_url: str,
    image: bytes,
    *,
    prefix_length: int | None = None,
) -> tuple[dict[str, object], dict[str, bytes], str]:
    packed = struct.pack("<I", len(image) if prefix_length is None else prefix_length) + image
    request_header = {
        "id": "black-box-1",
        "inputs": [
            {
                "name": INPUT_NAME,
                "shape": [1],
                "datatype": "BYTES",
                "parameters": {
                    "binary_data_size": len(packed),
                    "content_type": "image/png",
                },
            }
        ],
        "outputs": [
            {"name": name, "parameters": {"binary_data": True}}
            for name in OUTPUT_NAMES
        ],
    }
    json_header = json.dumps(request_header, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{base_url}/v2/models/{MODEL_NAME}/infer",
        data=json_header + packed,
        headers={
            "Content-Type": "application/octet-stream",
            "Inference-Header-Content-Length": str(len(json_header)),
        },
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
        header_length = int(response.headers["Inference-Header-Content-Length"])
    response_header = json.loads(body[:header_length].decode("utf-8"))
    binary = body[header_length:]
    documents: dict[str, bytes] = {}
    offset = 0
    for output in response_header["outputs"]:
        assert isinstance(output, dict)
        assert "data" not in output
        size = output["parameters"]["binary_data_size"]
        chunk = binary[offset : offset + size]
        element_size = struct.unpack("<I", chunk[:4])[0]
        documents[output["name"]] = chunk[4:]
        if element_size != len(documents[output["name"]]):
            raise AssertionError("invalid BYTES output length prefix")
        offset += size
    if offset != len(binary):
        raise AssertionError("trailing binary response data")
    return response_header, documents, content_type


class OcrProfileBlackBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = subprocess.Popen(
            [sys.executable, str(ROOT / "server.py"), "--host", "127.0.0.1", "--port", "0"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert cls.server.stdout is not None
        ready_line = cls.server.stdout.readline()
        if not ready_line:
            assert cls.server.stderr is not None
            raise RuntimeError(f"server did not start: {cls.server.stderr.read()}")
        cls.base_url = json.loads(ready_line)["base_url"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)
        if cls.server.stdout is not None:
            cls.server.stdout.close()
        if cls.server.stderr is not None:
            cls.server.stderr.close()

    def test_v2_health_and_fixed_model_metadata(self) -> None:
        server = _json_get(f"{self.base_url}/v2")
        self.assertEqual(server["extensions"], ["binary_tensor_data"])
        self.assertEqual(
            _json_get(f"{self.base_url}/v2/health/live"), {"live": True}
        )
        self.assertEqual(
            _json_get(f"{self.base_url}/v2/health/ready"), {"ready": True}
        )
        self.assertEqual(
            _json_get(f"{self.base_url}/v2/models/{MODEL_NAME}/ready"),
            {"name": MODEL_NAME, "ready": True},
        )
        metadata = _json_get(f"{self.base_url}/v2/models/{MODEL_NAME}")
        self.assertEqual(
            metadata["inputs"],
            [{"name": INPUT_NAME, "datatype": "BYTES", "shape": [1]}],
        )
        self.assertEqual(
            metadata["outputs"],
            [
                {"name": name, "datatype": "BYTES", "shape": [1]}
                for name in OUTPUT_NAMES
            ],
        )

    def test_binary_bytes_round_trip_normalizes_alto_and_page_equally(self) -> None:
        response, documents, content_type = _binary_request(
            self.base_url, make_demo_png()
        )
        self.assertEqual(content_type, "application/octet-stream")
        self.assertEqual(response["id"], "black-box-1")
        self.assertEqual(response["model_name"], MODEL_NAME)
        self.assertEqual(
            [output["name"] for output in response["outputs"]], list(OUTPUT_NAMES)
        )
        self.assertIn(FIXTURE_TEXT.encode("utf-8"), documents["alto_xml"])
        self.assertIn(FIXTURE_TEXT.encode("utf-8"), documents["page_xml"])
        alto_region = parse_alto(documents["alto_xml"])
        page_region = parse_page(documents["page_xml"])
        self.assertEqual(alto_region, page_region)
        self.assertEqual(alto_region.text, FIXTURE_TEXT)
        self.assertEqual(alto_region.confidence, FIXTURE_CONFIDENCE)
        self.assertEqual(alto_region.page_width, 1000)
        self.assertEqual(alto_region.page_height, 1400)
        self.assertEqual(alto_region.reading_order, 0)
        self.assertEqual(len(alto_region.polygon), 4)

    def test_cli_client_runs_as_a_separate_process(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "client.py"),
                "--base-url",
                self.base_url,
                "--request-id",
                "cli-1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["request_id"], "cli-1")
        self.assertEqual(result["normalized_region"]["text"], FIXTURE_TEXT)
        self.assertTrue(result["round_trip_equal"])

    def test_pinned_xml_fixtures_parse_to_the_same_region(self) -> None:
        alto_payload = (ROOT / "fixtures" / "alto-4.4.xml").read_bytes()
        page_payload = (ROOT / "fixtures" / "page-2024-07-15.xml").read_bytes()
        self.assertEqual(parse_alto(alto_payload), parse_page(page_payload))
        self.assertEqual(alto_payload, render_alto(fixture_region()))
        self.assertEqual(page_payload, render_page(fixture_region()))

    def test_json_string_base64_is_not_accepted_as_standard_image_bytes(self) -> None:
        body = json.dumps(
            {
                "inputs": [
                    {
                        "name": INPUT_NAME,
                        "shape": [1],
                        "datatype": "BYTES",
                        "data": ["iVBORw0KGgo="],
                    }
                ]
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/v2/models/{MODEL_NAME}/infer",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, HTTPStatus.BAD_REQUEST)
        error = json.loads(raised.exception.read().decode("utf-8"))
        raised.exception.close()
        self.assertIn("Binary Tensor Data Extension", error["error"])

    def test_malformed_bytes_length_prefix_is_rejected(self) -> None:
        with self.assertRaises(HTTPError) as raised:
            _binary_request(self.base_url, make_demo_png(), prefix_length=7)
        self.assertEqual(raised.exception.code, HTTPStatus.BAD_REQUEST)
        error = json.loads(raised.exception.read().decode("utf-8"))
        raised.exception.close()
        self.assertIn("length prefix", error["error"])

    def test_fractional_polygon_requires_explicit_quantization(self) -> None:
        fractional = NormalizedRegion(
            text=FIXTURE_TEXT,
            confidence=FIXTURE_CONFIDENCE,
            polygon=((12.5, 20), (100, 20), (100, 80), (10, 80)),  # type: ignore[arg-type]
            page_width=1000,
            page_height=1400,
            reading_order=0,
        )
        with self.assertRaisesRegex(ProfileError, "explicitly quantized"):
            render_page(fractional)


if __name__ == "__main__":
    unittest.main(verbosity=2)
