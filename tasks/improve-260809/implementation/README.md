# Implementation Plan Index

Implementation plans are execution working sets, not mutation authorization and not run history.

- An Impact Handshake defines the approved `From -> To`, blast radius, invariants, and proof boundary.
- An implementation plan decomposes one handshake into coherent passes, exact files, focused tests, and stop conditions.
- `execution/` records what actually ran after implementation starts; it never replaces either document.

| Plan | Handshake | Status | Purpose |
| --- | --- | --- | --- |
| [Foundation 1 — Dataset profile and cleaning evidence](F1-dataset-profile-cleaning.md) | [Impact Handshake F1 — Dataset profile and cleaning evidence](../handshakes/IH-F1.md) | implemented and objectively verified 2026-08-09 | Restore a bounded Dataset-ID profile Tool, enforce progressive disclosure, and qualify whole-Dataset cleaning through a clean-room service case |
| [Foundation 2 — Group-safe preparation, evaluation, and lifecycle facts](F2-group-safe-preparation-evaluation.md) | [Impact Handshake F2 — Group-safe preparation, evaluation, and lifecycle facts](../handshakes/IH-F2.md) | implemented and objectively service-verified 2026-08-09 | Bind training to immutable Dataset content, add group-disjoint preparation/evaluation, fix evaluation authority and apply lineage, and bound Agent result facts |
| [CF-C — Clustering trustworthiness](CF-C-clustering-trustworthiness.md) | [Impact Handshake CF — trustworthy clustering and native forecasting](../handshakes/IH-CF.md) | implemented and objectively verified; paid characterization/diagnosis recorded | Add typed quality/stability/null/profile evidence, stable labels, output identities, and truthful apply capability |
| [CF-F — Native forecasting v1](CF-F-native-forecasting.md) | [Impact Handshake CF — trustworthy clustering and native forecasting](../handshakes/IH-CF.md) | implemented and objectively verified; paid characterization passed | Add seasonal-naive, Holt-Winters, and bounded-auto SARIMA with temporal evaluation, intervals, and future apply |
| [RT-R — Personalized recommendation ranking](RT-R-recommendation-ranking.md) | [Impact Handshake RT — recommendation and text](../handshakes/IH-RT.md) | proposed; awaits design review | Add explicit-rating personalized Top-K, same-truth popularity comparison, seen exclusion, cold-user fallback, and reusable ranked output |
| [RT-T1 — Multilingual preparation and grouped classification](RT-T1-text-preparation-classification.md) | [Impact Handshake RT — recommendation and text](../handshakes/IH-RT.md) | proposed; awaits design review | Make tokenization reusable and privacy-bounded, then add raw-text classification with train-only vocabulary and business/template isolation |
| [RT-T2 — Text discovery and retrieval evidence](RT-T2-text-discovery-retrieval.md) | [Impact Handshake RT — recommendation and text](../handshakes/IH-RT.md) | proposed; awaits design review | Give clustering, topics, and similarity retrieval task-appropriate evidence, honest no-truth states, raw-text apply, and public outputs |

The two plans are independently accepted. Foundation 1 runs first because it provides the first low-cost Agent observation surface and the service qualification needed before the existing paid cleaning benchmark. Foundation 2 does not consume Foundation 1 test code, fixtures, or reports.

RT-R, RT-T1, and RT-T2 are separate working sets under one proposed handshake. Shared taxonomy, lifecycle, and Agent-projection files are serialized between them; recommendation and text domain changes are not loaded together by default.

Actual commands, verdicts, exceptions, and live metrics are owned by the [Foundation execution record](../execution/foundations-2026-08-09.md) and [CF execution record](../execution/CF-2026-08-09.md). RT receives its own execution record only after approval and implementation start.
