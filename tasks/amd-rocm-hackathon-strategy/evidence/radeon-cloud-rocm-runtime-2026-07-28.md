# Radeon Cloud ROCm Runtime Evidence — 2026-07-28

This is follow-on evidence for the
[captured Radeon Cloud cell](radeon-cloud-cell-2026-07-28.md). It records manual,
task-scoped preparation and black-box verification on that exact cell. Public
endpoint, SSH key path, host-key material, credentials, GPU UUID, and prompts or
business data are omitted.

## Verdict

The exact `gfx1100`/ROCm 7.2.1 cell can concurrently serve the selected Chat,
Embedding, and OCR candidates through clean capability protocols:

- Granite Chat and BGE-M3 Embedding run through the ROCm 7.2.1 vLLM nightly;
- PP-OCRv6 Det, Cls, and Rec all run through ROCm PyTorch;
- Chat/Embedding use their existing OpenAI-compatible wire shapes;
- OCR uses KServe V2 Binary Tensor input and one PAGE XML 2024-07-15 output;
- one temporary SSH process can privately forward all three loopback endpoints;
- no AMD-specific inference dialect or `RocmOcrAdapter` is needed.

This closes the framework/model/protocol feasibility questions for one development
cell. It does not close product lifecycle, Local Radeon, packaged one-click,
rainy-season end-to-end, or broad compatibility acceptance.

The exact versions and hashes are in
[the runtime manifest](../spikes/radeon-cloud/runtime-manifest.md).

## PyTorch ROCm

The AMD Radeon certified PyTorch 2.9.1/ROCm 7.2.1 wheel set reported:

```text
torch=2.9.1+rocm7.2.1.gitff65f5bc
HIP=7.2.53211
device=AMD Radeon Graphics
capability=(11, 0)
```

An FP16 4096-square GEMM completed in about 0.101 seconds after warm-up. A first
FP16 convolution completed in about 3.93 seconds. Maximum process allocation was
about 2.06 GB. These are compatibility smokes, not submission benchmarks.

## Chat and Embedding

Both vLLM services reached HTTP health on remote loopback and remained healthy
while OCR was loaded and invoked.

The Chat black-box sent the same core fields Xenix's OpenAI-compatible provider
uses and verified:

- non-streaming `/v1/chat/completions`;
- SSE streaming with one selected choice, an empty-choice usage chunk, and
  `[DONE]`;
- `stream_options.include_usage=true`;
- `tool_choice=auto` selecting exactly one `get_weather` call;
- streamed tool-call ID/name/argument accumulation;
- an assistant tool call followed by a `tool` message and final completion.

The Embedding black-box verified:

- three inputs return indexes `0..2`;
- every vector is finite, stable across repeated calls, and exactly 1024
  dimensions;
- an unknown model fails with HTTP 404;
- sending `dimensions=1024` fails with HTTP 400 because BGE-M3 is not a
  Matryoshka model.

Consequently, the managed BGE-M3 provider must persist `dimensions=None`, omit the
request field, observe 1024 from the response/self-test, and bind the vector-space
fingerprint to the exact model/tokenizer generation.

A 20-request, 32-input Embedding workload observed Radeon utilization up to 98%.
The post-contract coexistence snapshot reported about 37.2 GB VRAM in use and 100%
device busy. The latter is a whole-device observation, not per-service attribution.

## OCR Execution

RapidOCR 3.9.2 was installed in an isolated environment with:

- certified ROCm PyTorch and Triton;
- no ONNX Runtime, Paddle, OpenVINO, or TensorRT distribution;
- Det, Cls, and Rec each configured as `EngineType.TORCH`;
- each session device and model-parameter device asserted as `cuda:0`, which is
  PyTorch's ROCm API spelling;
- a forward pre-hook observing real input tensors on `cuda:0` in all three stages.

The fixed 1500 x 500 fixture contained:

```text
AMD Radeon GPU 文档识别
ROCm 7.2.1 私有部署
Invoice No. XENIX-2026
```

All three lines were reproduced exactly at confidences `0.99336`, `0.98709`, and
`0.99360`. Repeated text, boxes, and scores were stable. Initialization took about
1.06 seconds. The first inference, including ROCm kernel compilation, took about
13.8 seconds; subsequent observations were about 0.19 and 0.67 seconds. Peak
process allocation was 2,147,201,024 bytes.

This proves the three neural OCR stages used ROCm on the declared target. It is one
synthetic-fixture compatibility result, not an accuracy benchmark.

## OCR Protocol

The real RapidOCR server admitted one PNG as KServe V2 `BYTES[1]` using the Binary
Tensor Data Extension and returned one PAGE XML `BYTES[1]`.

The PAGE profile is `page-xml-text-regions-v1`:

- each detected line becomes one `TextRegion type="other"`;
- region order is explicit through zero-based `RegionRefIndexed`;
- preferred `TextEquiv index="1"` carries Unicode and confidence;
- request-image coordinates are quantized with round-half-up and clamped to image
  bounds;
- the response declares PAGE schema version 2024-07-15.

The client recovered all three regions, exact text, confidence, polygons, page
geometry, and reading order. Wrong content type failed with HTTP 400 and an unknown
model failed with HTTP 404.

The generated document passed the official PRImA PAGE 2024-07-15 XSD whose observed
100,037-byte payload has SHA-256
`2c245d38e365fdf71b495750eba76a5055e421e6d7cc1f90a4651b41db01ff2d`.
The same schema rejected a fractional polygon. This validates the selected wire and
profile document independently of the spike client; it does not establish full
OCR-D conformance or KServe server cancellation.

## Private SSH Transport

A single temporary SSH process published three local-loopback forwards to the
three remote-loopback listeners. Through those forwarded URLs, the complete Chat,
Embedding, and OCR contract suites passed again.

The validation guarded cleanup by checking:

- the PID still referred to the expected `ssh.exe`;
- the command line independently contained the expected host alias and all three
  forward specifications;
- the process was stopped only after those checks;
- local ports `18101`, `18102`, and `18103` were all closed afterward.

No live URL, chosen local port, PID, key path, or cloud endpoint was written to
provider settings or this packet. This is transport feasibility, not packaged
reconnect, host-trust, controller fencing, or remote cleanup acceptance.

## Verified Development Services and Teardown

At the protocol-verification check:

| Capability | Health | Listener |
| --- | --- | --- |
| Chat | HTTP 200 | remote loopback `8101` |
| Embedding | HTTP 200 | remote loopback `8102` |
| OCR | HTTP 200 | remote loopback `8103` |

They were session-scoped development processes with append-only logs and PID files
under `/opt/xenix-rocm-lab`. They did not auto-start, survive by contract, or
constitute deployment records.

Before implementation planning, all three exact process groups were checked
against their executable/command identity and stopped. Their PID files were
removed, no matching process or listener remained, and reported GPU memory use
fell to about 28 MB. Verified model/runtime assets, logs, and the six evidence
files were retained in the isolated lab namespaces.

The retained lab is intentionally not a clean-room acceptance target. Future
product lifecycle actions must verify the process group, command, start identity,
generation, and runtime incarnation; a PID file alone is insufficient. Cold
one-click acceptance starts from a fresh or equivalently attested target with an
absent product root and empty product-controlled caches.

## Remaining Gates

- Run the real Xenix headless rainy-season journey with Knowledge indexing, Tool
  execution, local canonical Artifact finalization, and correlated measurements.
- Convert manual preparation into an approved forward-only deployment slice with
  immutable manifests, generations, owner-scoped provider registration, repair,
  retirement, and typed diagnostics.
- Define OCR concurrency, decoded-pixel/XML bounds, disconnect/cancellation,
  inverse transform, hostile document, and atomic-result policy.
- Prove remote process restart, stale-controller fencing, target reboot, occupied
  ports, host-key change, interrupted acquisition, corrupt assets, and removal.
- Decide and verify per-placement service authentication. The current loopback
  services accept Xenix's Bearer header but do not reject an unauthenticated
  request.
- Run a distinct Local placement acceptance from a fresh baseline. This manual
  externally controlled lab does not prove it; a later product controller running
  headlessly on the Radeon host itself may prove the same-host Linux path.
