# OCR Protocol Options

This file owns the standards-first protocol review for the remote OCR provider. It
does not select a server implementation or authorize product code. The current
disposition is also summarized in the [scheme review](../scheme-review.md).

## Finding

No single broadly adopted open protocol defines the complete operation “submit one
document image and receive structured OCR text, confidence, geometry, reading order,
runtime identity, cancellation, and errors” in the way OpenAI-compatible APIs
define Chat and Embedding requests.

Mature standards exist at two different layers:

| Candidate | Standardized layer | Fit |
| --- | --- | --- |
| KServe V2 / Open Inference Protocol | Health, readiness, metadata, versioned inference, REST/gRPC, typed tensors and optional binary tensors | Leading transport candidate |
| PRImA PAGE XML | Page/region/line/word/glyph geometry, Unicode text, confidence, reading order | Leading semantic-output candidate |
| ALTO XML 4.4 | OCR text, page/layout structure, shapes, processing metadata, reading order | Compatibility/comparison candidate |
| hOCR 1.2 | Open HTML-based OCR/layout output | Weaker compatibility candidate |
| OpenAI-compatible APIs | Chat/Responses/Embedding operations | Reuse for LLM/Embedding, not structured OCR |
| Vendor OCR APIs | Vendor-specific request/result contracts | Mature products, not an open self-hosted AMD-target protocol |

Primary sources:

- KServe V2 specification:
  <https://kserve.github.io/website/docs/concepts/architecture/data-plane/v2-protocol>
- KServe binary tensor extension:
  <https://kserve.github.io/website/docs/concepts/architecture/data-plane/v2-protocol/binary-tensor-data-extension>
- KServe Python runtime SDK:
  <https://kserve.github.io/website/docs/reference/python-runtime-sdk>
- PRImA PAGE XML 2024-07-15 schema:
  <https://www.primaresearch.org/schema/PAGE/gts/pagecontent/2024-07-15/pagecontent.xsd>
- OCR-D PAGE interoperability profile:
  <https://ocr-d.de/en/spec/page>
- ALTO standards and 4.4 schema:
  <https://www.loc.gov/standards/alto/>
- hOCR 1.2:
  <https://kba.github.io/hocr-spec/1.2/>
- vLLM OpenAI-compatible APIs:
  <https://docs.vllm.ai/en/stable/serving/online_serving>

KServe V2 is independent of OCR semantics. It defines named typed inputs/outputs
but not polygon, confidence, line hierarchy, or reading-order meaning. PAGE, ALTO,
and hOCR describe OCR output but are not inference transports. Combining KServe V2
with a pinned PAGE profile reuses standards at both layers without claiming that
either standard defines the other.

KServe V2 does not define a standard server-side cancellation operation. Client
cancellation can stop Xenix waiting and close the transport, but remote compute may
continue until a server deadline. A hard remote cancellation requirement would
need an explicitly admitted extension; it cannot be inferred from HTTP disconnect.

## Leading Product Profile

The next real-runtime spike should use KServe V2 HTTP/REST without requiring
Kubernetes:

- standard `/v2` server/model health, readiness, metadata, and infer endpoints;
- exactly one decoded logical image per inference request;
- one bounded `BYTES` image input using Binary Tensor Data Extension;
- exactly one version-pinned PAGE `PcGts/Page` `BYTES` output;
- no PDF, TIFF container, multi-page batch, or document-assembly semantics inside
  this inference profile;
- a local engine-neutral provider that parses PAGE into Xenix normalized regions.

Xenix owns PDF/TIFF splitting, stable source page identity/ordinal, page scheduling,
page-level partial/failure policy, and final document assembly. PAGE
`ReadingOrder` describes content within the one rendered page; it does not replace
Xenix page order. A page failure may be represented explicitly during assembly, but
the Knowledge owner must still publish a canonical document generation atomically
rather than expose a half-current document.

The product profile requests PAGE only. ALTO remains useful comparison evidence and
a possible compatibility fallback, but it is not a required parallel output and
does not need to be semantically isomorphic to PAGE. If enabled later, ALTO needs
independent admission.

## PAGE Semantic Contract Still Required

The precise PAGE namespace/revision must be pinned. “PAGE XML” is not sufficient:
PRImA publishes 2024-07-15 while OCR-D interoperability material often anchors
2019-07-15.

The candidate normalized unit is one detected text line:

- each PAGE `TextLine` is nested in a `TextRegion`;
- preferred text uses `TextEquiv/@index=1` under the OCR-D convention;
- region-level reading order is explicit and its mapping to normalized line order
  is deterministic;
- Unicode and confidence semantics are fixed;
- the exact TextRegion/TextLine grouping rule is tested for multi-line and complex
  layouts.

All output coordinates refer to the exact image bytes sent in the request:

- page width/height and input identity are bound to the request;
- server-side crop, rotate, deskew, dewarp, or resize transforms are inverted
  before output;
- PDF source coordinates remain an outer Xenix concern through its stored
  source-to-rendered-image transform;
- PAGE integer encoding uses an explicit nearest-pixel or other pinned quantization
  rule with measured error;
- bounds, finite values, at least three polygon points, non-self-intersection, and
  parent/child containment are validated.

Xenix's engine-neutral polygon should not be restricted to Paddle's current
four-point quadrilateral merely because that implementation emits quads.

## Metadata and Provenance

KServe model metadata can validate standard tensor names, datatypes, shapes, and
model identity. It has no standardized OCR profile token, and current KServe
metadata documentation does not define general standard extension names.

The immutable AMD deployment profile and self-test therefore pin:

- PAGE namespace/profile revision and media type;
- input/output names, datatypes, shapes, and binary framing;
- OCR model/runtime/component generation;
- expected target process identity;
- backend/device/provenance evidence requirements.

Do not claim a custom `platform=xenix...` value or
`extensions=["binary_tensor_data"]` response as standard protocol negotiation.
Binary-tensor behavior is verified by the admitted request/response profile itself.

## Resource and Failure Contract

Admission must quantify and fail closed on:

- compressed input bytes;
- decoded width, height, pixels, channels, bit depth, frames, and decoded bytes;
- HTTP header/body and each binary tensor size;
- PAGE/XML response bytes;
- XML depth, element/attribute/text counts, DTD/entity/XInclude prohibition;
- region, line, polygon-point, ID, and reading-order-reference counts;
- per-attempt deadline, retry policy, concurrency, and total in-flight memory.

An 8 MiB compressed image limit with a 20,000 x 20,000 dimension limit is not by
itself a safe decode bound.

Transport loss, binding loss, malformed output, model failure, deadline, and user
cancellation are typed provider outcomes. A remote transport failure must never be
normalized to “OCR found no text”. The Knowledge import owner decides whether an
explicit failed page can coexist with successful pages or whether the attempt fails
closed; canonical publication remains atomic.

Client cancellation stops the local attempt. Remote work can outlive that client
unless the selected runtime proves a bounded server deadline or an admitted
cancellation extension. Retries after an ambiguous disconnect require request
identity/idempotency policy because they may duplicate GPU work.

## Executed Local Spike

The isolated [executable spike](../spikes/ocr-protocol/README.md) proves:

- KServe V2-shaped health, readiness, metadata, version, error, and inference
  envelopes between its own client and server;
- a real PNG and UTF-8 XML through length-prefixed `BYTES` tensors;
- official-XSD validity for PAGE 2024-07-15 and ALTO 4.4 fixtures;
- equality of selected normalized fields for one fixture;
- fail-closed behavior for several malformed framing/coordinate cases.

The self-contained black-box suite passed `7/7`, and the separate official-XSD
validation passed both fixtures. This is useful binary-framing and schema evidence.

It does not prove Open Inference Protocol conformance against an independent
implementation, real OCR, ROCm, general PAGE/ALTO semantic equivalence, OCR-D
conformance, hard cancellation, resource hardening, or hostile-XML safety. Its
PAGE `TextEquiv/@index=0` is XSD-valid but differs from the proposed
OCR-D-aligned product profile. Its dual PAGE+ALTO response is a comparative spike,
not the PAGE-only product signature.

## Selected Profile and Remaining Admission Evidence

The real Radeon runtime has now proven the leading KServe V2 Binary Tensor PNG to
PAGE 2024-07-15 shape with RapidOCR ROCm and official XSD validation. The task plan
therefore selects that profile. Product admission still requires:

- the exact single-image/PAGE signature and a second implementation where feasible;
- PAGE hierarchy, reading order, coordinate inverse mapping, integer quantization,
  and measured error bounds;
- Chinese accuracy and confidence semantics against accepted fixtures;
- every quantified decode/response/XML/concurrency bound above;
- timeout, ambiguous retry, local cancellation, bounded remote work, shutdown, and
  typed failure behavior;
- immutable component generation and Radeon/ROCm workload provenance;
- parser hardening and atomic outer document publication.

Failure of any required PAGE semantics/resource proof blocks that execution cell;
v1 does not silently switch to ALTO, a custom response, or a Xenix-specific HTTP
protocol. A future protocol change is a new separately admitted capability
decision, not an implementation-time fallback.
