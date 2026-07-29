# Competition Requirements

This file owns the current competition facts and unresolved official conflicts.
Product scope remains in [product direction](product-direction.md); the task control
surface remains in [README](README.md).

## Sources and Authority

Reviewed on 2026-07-26:

- official submission repository:
  <https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07/blob/main/README.md>;
- official event page:
  <https://luma.com/amd-4dhi>;
- linked Rules and Conditions:
  <https://docs.google.com/document/d/1TwgwBNUAv8fRNQbkcTZmcRR0__Oi4WMsBfkW38ALZp4/edit?tab=t.0>;
- official Radeon Cloud guide:
  <https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07/blob/main/Radeon-Cloud-User%20Guide/README.md>.

The Rules document says it governs the competition. The event summary, Rules, and
repository contain at least one scoring inconsistency, so the conflict remains
explicit rather than being silently reconciled.

## Selected Track

Xenix fits Track 2: Development and Local Deployment of Private AI Agents.

The track covers Agents with reasoning, planning, Tool use, memory, and task
execution. It lists personal or enterprise assistants, workflow automation, RAG,
local-knowledge assistants, developer Agents, and multi-Agent systems as examples.

Track 2 requires:

- AMD Radeon Cloud and ROCm;
- core model inference on the Radeon GPU rather than a remote API carrying the core
  function;
- no complete dependency on a closed Agent platform;
- at least two of local RAG, Tool calling, multi-step planning, local multi-turn
  memory, and explicit permission/privacy controls;
- a description and measurement of Radeon inference-speed optimization.

The rules do not say that OCR, LLM, and Embedding must all execute on ROCm. Sir
selected full three-capability ROCm coverage as the Xenix product target, not as an
interpretation of this competition requirement.

## Scoring

The Luma summary describes Track 2 as 100 points:

- functional completeness and application value: 60;
- AMD Radeon GPU and ROCm optimization: 40.

The Rules document describes 120 possible points:

- functional completeness: 60;
- Radeon/ROCm adaptation and optimization: 40;
- an optional 20-point category involving Radeon Cloud model API use and
  quantization, distillation, or related optimization.

Sir decided that the scoring discrepancy is not a current product-design driver and
that the Radeon Cloud Dedicated Model API (`Deploy Type = vLLM Model API`) may be
treated as the optional API category. It may be an explicit product adapter, but it
does not replace the same-instance Radeon/ROCm core path or qualify as local/private
inference.

## Submission Schedule and Eligibility

- Registration opened: 2026-07-10 00:00 UTC+8.
- Submission opened: 2026-07-15 00:00 UTC+8.
- Final deadline: 2026-08-06 23:59 UTC+8.
- Participation is individual or a team of at most three.
- Luma registration and AMD AI Developer Program membership are required for prize
  eligibility.
- Participant identity, age, sanctions/export-control, GitHub, Discord, and
  team-name requirements remain as stated in the Rules.

## Required Track 2 Materials

Fork the official repository and submit a pull request titled:

```text
Track 2, Team name, application name
```

All submission materials, project descriptions, and pull-request content must be in
English.

The submission includes:

1. A project specification covering the application scenario, Agent architecture,
   core capabilities, model and local-deployment plan, and Radeon inference-speed
   optimization.
2. Complete project source plus a README with environment configuration, startup
   guide, and dependencies.
3. A recommended 3–5 minute video showing the real workflow and actual performance
   on an AMD Radeon GPU, with fluidity and functional completeness visible.
4. Either a PPT or a poster.

The contest repository does not itself supply a source-code license or clearly state
which SPDX license the entry must use. A public fork and pull request imply that the
submitted material must be reviewable, but the exact repository-visibility and
license expectation should be confirmed before publication.

## Rights and Content Risk

The Rules combine a broad, worldwide, royalty-free, irrevocable, non-exclusive
license to AMD with a separate statement that entries become AMD property. That
wording is legally material and potentially ambiguous; the packet does not
reinterpret it.

Submission materials therefore must exclude:

- real customer or confidential business data;
- secrets, credentials, private endpoints, SSH material, or private runtime logs;
- third-party assets, datasets, model weights, fonts, media, or code that the team
  cannot submit or license on the stated terms;
- user-owned repository changes outside the approved competition scope.

Model, dataset, fixture, media, and source-code licenses need an explicit submission
inventory.

## Organizer Confirmations

Ask the official Discord or `ai_dev_contests@amd.com` to confirm:

1. whether the source repository/fork must remain public and which license is
   expected;
2. the intended interpretation of the entry-license/property language;
3. whether a locally authoritative Xenix desktop using a participant-controlled
   Radeon Cloud execution target over guided SSH, plus a same-instance headless
   benchmark, is an accepted demonstration of the Track 2 local-deployment
   requirement.
