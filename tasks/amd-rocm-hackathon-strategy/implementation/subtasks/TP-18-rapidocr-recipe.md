# TP-18 — RapidOCR/PAGE Recipe

## Outcome

Turn the verified RapidOCR 3.9.2 PP-OCRv6 Torch/ROCm runtime and PAGE server into
an immutable authenticated OCR component recipe.

## Owned Mutation

- add the RapidOCR component manifest under
  `src/xenix/resources/amd/manifests/components/`;
- add the product RapidOCR KServe/PAGE server and component self-test under
  `src/xenix/services/amd/components/`;
- add recipe/server/self-test tests.

The server implements TP-02/07; the placement driver remains protocol-neutral.
TP-19 owns final profile aggregation.

## Recipe

- exact certified ROCm PyTorch/Triton/RapidOCR/model refs, hashes, licenses,
  isolated roots, plugin/backend allow-list, launch/capacity/deadline bounds;
- Det, Cls, and Rec all explicitly `EngineType.TORCH`;
- framework HIP, device/session, parameter, and real input tensor attestation for
  all three stages;
- authenticated loopback KServe V2 Binary Tensor PNG to PAGE-only response;
- protected authentication handoff outside command-line/persisted summaries and
  required unauthenticated rejection;
- exact PAGE/resource/hostile-input/typed failure profile.

## Acceptance

- ONNX/Paddle/OpenVINO/TensorRT fallback distributions/backends are absent;
- fixed mixed-language fixture is exact and PAGE output passes pinned XSD;
- unauthenticated, wrong content type/model, oversized image/XML, malformed/hostile
  XML, and deadline cases fail typed;
- first compile and warm inference are separately measured;
- the service runtime remains a manifest acquisition rather than a desktop base
  dependency;
- coexists with Granite/BGE under declared capacity.

## Verification

- focused recipe/server tests and official PAGE XSD;
- real-cell TP-19 coexistence/device run;
- `pdm run check`.
