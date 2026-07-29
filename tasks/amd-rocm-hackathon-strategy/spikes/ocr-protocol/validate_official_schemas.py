"""Networked validation against the pinned official ALTO and PAGE XSDs.

This auxiliary check intentionally is not part of the stdlib-only black-box suite:
it needs network access and an already-available lxml installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from ocr_profile import PAGE_NAMESPACE


ALTO_SCHEMA_URL = "https://www.loc.gov/standards/alto/v4/alto-4-4.xsd"
PAGE_SCHEMA_URL = (
    "https://www.primaresearch.org/schema/PAGE/gts/pagecontent/"
    "2024-07-15/pagecontent.xsd"
)
# ALTO 4.4 imports a now-unavailable /standards/xlink/xlink.xsd URL. This is the
# LOC-hosted METS copy of the same W3C XLink namespace schema.
XLINK_SCHEMA_URL = "https://www.loc.gov/standards/mets/xlink.xsd"

OBSERVED_SHA256 = {
    ALTO_SCHEMA_URL: "5564fd29d2dd090d8102b8a0aa081906afd677cd5ecc632312e56f21ea14702b",
    PAGE_SCHEMA_URL: "2c245d38e365fdf71b495750eba76a5055e421e6d7cc1f90a4651b41db01ff2d",
    XLINK_SCHEMA_URL: "f1f5bb6003165cdd8f6c1fcc32f8fd1f965e1681010f3b9806d9460bcffa8a3c",
}
ROOT = Path(__file__).resolve().parent


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Xenix-OCR-protocol-spike/1"})
    with urlopen(request, timeout=20) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--additional-page",
        action="append",
        default=[],
        type=Path,
        help="Additional PAGE XML document to validate against the pinned XSD.",
    )
    parser.add_argument(
        "--page-only",
        action="store_true",
        help="Validate only PAGE documents; do not fetch the unrelated ALTO/XLink schemas.",
    )
    args = parser.parse_args()

    try:
        from lxml import etree
    except ImportError:
        print(
            "error: this optional network check requires the already-available lxml",
            file=sys.stderr,
        )
        return 2

    schema_urls = (
        (PAGE_SCHEMA_URL,)
        if args.page_only
        else (ALTO_SCHEMA_URL, PAGE_SCHEMA_URL, XLINK_SCHEMA_URL)
    )
    downloaded = {url: _download(url) for url in schema_urls}
    observed = {
        url: hashlib.sha256(payload).hexdigest()
        for url, payload in downloaded.items()
    }
    changed = {
        url: {"expected": OBSERVED_SHA256[url], "actual": digest}
        for url, digest in observed.items()
        if digest != OBSERVED_SHA256[url]
    }
    if changed:
        print(json.dumps({"schema_hash_mismatch": changed}, indent=2), file=sys.stderr)
        return 1

    page_schema = etree.XMLSchema(etree.fromstring(downloaded[PAGE_SCHEMA_URL]))

    page_payload = (ROOT / "fixtures" / "page-2024-07-15.xml").read_bytes()
    page_document = etree.fromstring(page_payload)
    page_schema.assertValid(page_document)
    if not args.page_only:
        class XlinkResolver(etree.Resolver):
            def resolve(
                self,
                system_url: str,
                public_id: str,
                context: object,
            ) -> object:
                if system_url.endswith("/xlink/xlink.xsd"):
                    return self.resolve_string(
                        downloaded[XLINK_SCHEMA_URL],
                        context,
                        base_url=XLINK_SCHEMA_URL,
                    )
                return None

        alto_parser = etree.XMLParser(no_network=True)
        alto_parser.resolvers.add(XlinkResolver())
        alto_schema_document = etree.fromstring(
            downloaded[ALTO_SCHEMA_URL],
            parser=alto_parser,
            base_url=ALTO_SCHEMA_URL,
        )
        alto_schema = etree.XMLSchema(alto_schema_document)
        alto_payload = (ROOT / "fixtures" / "alto-4.4.xml").read_bytes()
        alto_document = etree.fromstring(alto_payload)
        alto_schema.assertValid(alto_document)
    validated_additional_pages = []
    for additional_page in args.additional_page:
        additional_document = etree.fromstring(additional_page.read_bytes())
        page_schema.assertValid(additional_document)
        validated_additional_pages.append(str(additional_page))

    fractional_document = etree.fromstring(page_payload)
    coords = fractional_document.find(f".//{{{PAGE_NAMESPACE}}}Coords")
    if coords is None:
        raise RuntimeError("generated PAGE fixture has no Coords")
    points = coords.get("points")
    if points is None:
        raise RuntimeError("generated PAGE fixture has no points")
    coords.set("points", points.replace(points.split()[0], "12.5,20", 1))
    fractional_valid = page_schema.validate(fractional_document)
    if fractional_valid:
        raise RuntimeError("PAGE XSD unexpectedly accepted a fractional polygon")
    fractional_error = str(page_schema.error_log.last_error)

    print(
        json.dumps(
            {
                "networked": True,
                "schemas": [
                    {
                        "url": url,
                        "sha256": observed[url],
                        "bytes": len(downloaded[url]),
                    }
                    for url in downloaded
                ],
                "alto_4_4_valid": None if args.page_only else True,
                "page_2024_07_15_valid": True,
                "additional_page_documents_valid": validated_additional_pages,
                "fractional_page_polygon_valid": False,
                "fractional_page_polygon_error": fractional_error,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
