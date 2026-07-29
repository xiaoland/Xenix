# TP-02 — OCR PAGE and Failure Profile

## Outcome

Turn the verified KServe/PAGE candidate into an implementable OCR-domain contract
without changing ADR 0009's Paddle compatibility decision. The protocol and
failure choices are resolved; measured resource ceilings remain manifest admission
facts rather than user decisions.

## Owned Mutation

- extend `docs/20-product-tdd/knowledge-base-boundary.md`;
- add `docs/20-product-tdd/adr/0011-kserve-page-ocr-provider-boundary.md`;
- update `docs/20-product-tdd/adr/README.md`.

No OCR code is changed.

## Contract to Lock

- PAGE 2024-07-15, PNG-only, exactly one decoded logical image per request, and one
  `PcGts/Page` response;
- Xenix owns PDF/TIFF splitting, document/page identity, order, and assembly;
- text line is the normalized unit; region/line hierarchy, preferred
  `TextEquiv index=1`, reading order, inverse transform, coordinate quantization,
  and bounds are exact;
- coordinates use inverse mapping followed by round-half-up and image-bound clamp;
- v1 server concurrency is one request per OCR generation;
- compressed bytes, dimensions, channels/frames, decoded pixels/bytes, tensor/XML
  bytes, XML depth/nodes/regions/points/references, deadline, concurrency, and
  in-flight memory are bounded;
- legal no-text is an empty success;
- transport, authentication, timeout, malformed/hostile XML, schema/profile,
  generation, and binding loss are typed failures;
- v1 fails the whole import attempt on provider/protocol failure and atomically
  publishes no silent partial canonical document;
- client cancellation means stop waiting; remote work remains bounded by the
  server deadline because KServe has no standard hard-cancel endpoint.
- numeric compressed/decode/XML/node/point/memory/deadline ceilings are mandatory
  manifest fields populated by a real cold resource probe; an unmeasured cell is
  not admitted and the UI never asks the user to guess values.

## Acceptance

- PAGE-only is normative; ALTO stays comparison evidence;
- every spike-open resource/failure question has a value or explicit admission
  blocker;
- TP-06 and TP-07 can derive types/tests without AMD knowledge;
- ADR 0009 remains accurate and unsuperseded.

## Verification

- official PAGE XSD fixture validation;
- hostile/oversized fixture design review;
- durable-document links and terminology checks.
