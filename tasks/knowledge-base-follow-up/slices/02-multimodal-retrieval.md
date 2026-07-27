# Parked Follow-up — Multimodal Retrieval Design

**State:** parked outside Slice 02; no implementation authorized
**Question:** can Knowledge that contains images be searched and used, not merely stored?

## Capability Truth Today

| Capability | Current state | Meaning |
| --- | --- | --- |
| Import JPEG/PNG and picture-bearing documents | Supported | Source/canonical content can preserve image items. |
| Search OCR, table text, or surrounding text | Supported when a text projection exists | This is text retrieval over multimodal source material. |
| Retrieve an image by visual meaning from a text query | Not supported | The current provider protocol accepts text only and Lance rows represent text Units. |
| Give the retrieved pixels/region to the Agent | Not supported | `knowledge.lookup` returns JSON text excerpts; the conversation/provider path has no Knowledge visual-evidence operation. |
| Use a VLM to caption/interpret images | Not supported in the accepted MVP | VLM is a separate optional service, not a synonym for multimodal embeddings. |

The accurate short answer is therefore: **multimodal ingestion is partial; true
multimodal retrieval and consumption are not implemented.** OCR can recover labels
and prose, but not reliably encode trends, geometry, diagrams, photographs, or charts
whose answer is not present as text.

## Primary-Source Gleanings

- The [OpenAI Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
  defines its input as strings or token arrays and creates vectors for input text.
  Xenix's current OpenAI-compatible adapter intentionally implements this text wire
  shape; it is not a generic image protocol.
- [Cohere Embed v2](https://docs.cohere.com/v2/reference/embed) defines text, image
  data-URI, and mixed text/image inputs. Embed v4 places mixed content in one vector
  space and distinguishes search-query from search-document use.
- The official [Qwen3-VL-Embedding repository](https://github.com/QwenLM/Qwen3-VL-Embedding)
  accepts text, images, screenshots, video, and mixed inputs and maps them into a
  shared representation space. Its local/vLLM integration is not the same wire
  contract as OpenAI text embeddings.

These sources prove feasible implementations, not that one provider's request schema
should become Xenix's domain model.

The first spike should stay with one-vector-per-visual-unit models, which fit the
current immutable Lance generation shape. Multi-vector late-interaction retrieval is
a separate complexity class and should be admitted only if the visual benchmark shows
that whole-image/region single vectors are materially inadequate.

## First-Principles Requirement

Visual recall alone has no product value if the Agent cannot inspect the evidence:

```text
text question
  -> visual vector hit
  -> current canonical image/figure/page region
  -> model-visible visual evidence
  -> final data insight or business recommendation
```

Stopping at a visual vector hit would repeat the earlier ID problem: it would return
identity that enables no next action. Phase D is complete only when the hit is either
consumable by a second operation or explicitly remains a research spike.

## Proposed Content Model

Keep two retrieval-unit kinds with one content authority:

```text
TextUnit
  -> current SQLite text + locator + canonical generation

VisualUnit
  -> current canonical asset or derived page/region raster
  -> media type, pixel bounds/page locator, content SHA-256
  -> optional OCR/surrounding text projection
```

The image bytes remain in the content-addressed asset/derivative store. SQLite owns
the VisualUnit identity/current relationship and safe locator; LanceDB owns only the
derived vector. A PDF page raster or figure crop is a content-addressed derivative,
not a second canonical document.

Granularity needs measured evidence:

- JPEG/PNG source: whole image first;
- DOCX/PDF figure with a reliable Docling asset/region: figure region;
- complex-layout page where figure extraction loses context: bounded page raster;
- never create every possible crop or pyramid level before retrieval evidence pays
  for that storage and indexing cost.

## Capability-Neutral Service Boundary

Do not add image parameters to `embed_texts`. Introduce a separate multimodal
capability whose frozen operation describes what it can actually encode:

```text
MultimodalEmbeddingProfile
  provider/protocol/model/dimensions
  supported document modalities: image | text_image
  supported query modalities: text (required for MVP)
  request byte/pixel/item limits
  profile fingerprint (no secret)

MultimodalEmbeddingSession
  embed_query_text(text)
  embed_documents([image or text+image inputs])
```

The first adapter may target a provider-defined mixed-input API such as Cohere v2 or
a local/vLLM Qwen3-VL worker, but the Knowledge domain receives validated vectors and
capabilities—not provider payloads. Provider credentials remain user-controlled in
Knowledge settings and document content may be sent externally under the already
accepted service policy.

## Separate Visual Generation

Text and visual indexes have independent compatibility and corpus lifecycles:

```text
text_vector_generation
  = text profile + current TextUnit corpus

visual_vector_generation
  = multimodal profile + current VisualUnit/asset corpus
```

Even when one model can encode both, keep immutable generations separate. This lets a
user retain the existing high-quality text model, rebuild only changed visual assets,
and disable visual transmission without invalidating text search. It also prevents
raw cosine scores from unrelated spaces being compared accidentally.

Query routing becomes:

```text
keyword rank (FTS text)
text semantic rank (text vectors)
visual semantic rank (visual vectors, when ready)
             |
             v
bounded deterministic rank fusion
             |
             v
rehydrate current SQLite/canonical evidence
```

Fuse ranks rather than raw scores across legs. If text and visual legs use different
models, their cosine scales are not comparable. `semantic` and `hybrid` may include
the ready visual leg without adding provider/index details to the Agent-facing mode;
the returned evidence type must remain truthful.

## Actionable Agent Evidence

The likely minimal contract extension is:

```text
knowledge.lookup
  -> results[{source, location?, excerpt?, evidence_ref?}]

knowledge.inspect(evidence_ref)
  -> the current image/region as a model-visible image content block
```

Rules:

- `evidence_ref` appears only for a result that `knowledge.inspect` can consume. It
  is the minimum actionable reference, not a bundle of document/unit/generation IDs.
- Lookup still emits one canonical ToolResult value; there is no hidden provenance
  plane. The optional reference is part of that one value and must survive canonical
  conversation replay as itself.
- Inspect resolves and validates current Knowledge authority; stale/deleted evidence
  fails safely. It does not expose a filesystem path.
- A visual hit without a text excerpt is allowed only after the result schema defines
  “at least one of excerpt/evidence_ref.” Filename or OCR noise must not pretend to be
  a visual interpretation.
- Inspect is registered only when the selected Agent provider can receive image
  content blocks. Otherwise visual hits are not advertised as consumable.

This crosses the generic ToolResult/provider message boundary and therefore requires
review against Agent Harness Unit TDD before implementation. If Xenix instead chooses
a VLM service that interprets evidence and returns text, that is a different design:
the VLM output becomes a derived text projection with its own provenance/profile and
must not be conflated with the visual embedding service.

## Index and Settings UX

Once supported, the Knowledge Base Settings tab gains a separate `Visual Embedding`
card and the rebuild sheet gains `Visual vector index`. Text and visual profiles do
not share an enabled flag or credentials implicitly.

The Workspace status strip reports text and visual index readiness separately. A
document row still reports content state rather than claiming per-document global
generation readiness.

No disabled “Visual index” checkbox is shown before this capability exists. Product
copy should continue to say that image meaning is not searchable when only OCR/text
projection is available.

## Vertical Spike and Benchmark

Before schema or Tool implementation, run one disposable spike over:

1. a text query whose answer is represented only by a chart/diagram shape;
2. an image/region and a visually similar hard negative with comparable OCR text;
3. one text embedding leg as a baseline;
4. one candidate multimodal provider/local model; and
5. a model-visible inspection step if the selected LLM supports images.

Record model/protocol, dimensions, payload/pixel limits, latency, provider calls,
recall rank, package/runtime cost, and whether the final Agent answer correctly turns
the visual fact into a data insight or business recommendation.

Acceptance grades the final answer and public artifacts. Tool calls, vector hits,
`evidence_ref`, and inspect execution remain diagnostic telemetry. A case passes only
when the answer cannot be obtained from OCR/surrounding text alone and the final
deliverable uses the visual evidence correctly.

## Failure Preplay

| Scenario | Required behavior |
| --- | --- |
| Multimodal provider disabled/unconfigured | Text keyword/semantic behavior is unchanged; visual capability is not advertised. |
| Visual generation stale or failed | Text legs remain usable; explicit visual-capable behavior is honest about unavailability. |
| Oversized/corrupt image | Bounded validation/resize policy; no partial generation publication. |
| Figure crop loses axes/legend | Retrieval evidence retains page locator; spike decides whether page raster is required. |
| OCR and visual ranks disagree | Preserve both evidence paths; deterministic fusion, no raw-score comparison. |
| Agent model cannot receive images | Do not return an unusable reference as if the task can consume it. |
| Evidence deleted/replaced after lookup | Inspect resolves current authority and returns a bounded unavailable result. |
| Provider returns mixed dimensions/non-finite vectors | Reject the batch; no visual generation is published. |
| External request/log error | No image bytes, document text, URL, key, or provider body enters logs/Tool values. |

## Recommendation

Treat Phase D's first commitment as **design plus vertical spike**, not full product
delivery. The spike should choose between a well-specified external mixed-input API
and a local/vLLM adapter using actual Xenix documents and final-answer value. Only
then freeze the VisualUnit granularity, provider protocol, Agent image-content seam,
storage migration, and packaged-runtime impact.
