# 1.5 Release Notes — 1.5.1 Preparation

This is the candidate release summary for changes since v1.4.0, not a publication announcement. Publication follows [Windows Distribution](windows-distribution.md); local preparation and evidence are tracked in the [closeout packet](../../tasks/minor-1-5-closeout/packet.md).

## User-visible changes

- Conversation Dataset lineage includes imported and transformed data. Task Center filters and background Knowledge status loading address missing results and UI stalls; startup error dialogs remain visible above bootstrap.
- Agent tools separate registration, execution and selective exposure. Namespace activation supports batches independently of Skill reading, and invalid tool parameters return actionable failures rather than terminating the conversation.
- App-owned business objects use persistent integer IDs across tasks, Datasets, models and Artifacts; upgrade implications are described below.
- Text classification offers retained word, character n-gram and pretokenized strategies. New classifiers use grouped cross-validation for selection, and prediction output identifies rows without known features. See [retained text classification](../30-unit-tdd/text-classification.md).
- Knowledge document import, structured retrieval, background processing and desktop interaction received substantial revisions; supported behavior remains owned by the PRD and unit documentation rather than historical task plans.

## Contributor changes

Application composition, storage ownership, task dispatch and tool execution boundaries have been simplified. Offline acceptance, explicit live business benchmarks and packaged smoke have separate purposes; benchmark infrastructure has no automated tests of its own. Tool and Skill descriptions have been reduced while retaining actionable parameter and result semantics.

## Upgrade implications

The integer identity transition rewrites stored references and managed artifacts. Back up runtime state, managed files and usage journals together before upgrading; historical UUID links copied outside Xenix have no compatibility lookup. Knowledge vector projections rebuild through the index service. The recovery and disk-space contract belongs to [Local State Evolution](local-state-evolution.md).

Saved text analyzers retain their preparation and vocabulary. New classification defaults preserve single-character words and omit the built-in stopword list unless selected. Explicit preprocessing choices are retained with new analyzers; separately transformed business input must still match the input contract used during training.

## Evidence and limits

The latest functional revision passed 303 offline tests, static checks, isolated startup, Windows packaging and packaged smoke. Targeted routing confirmation passed with 28/30 actual predictions correct (93.33%); this does not establish full live benchmark acceptance. The user closed benchmark improvement and failure investigation on 2026-09-15, with unresolved observations retained as historical evidence.

The reviewed bundle predates the 1.5.0 declaration and embeds the preceding build identity; it is not a 1.5.0 release artifact. The final promoted commit requires its own CI, tag identity verification, release build and packaged smoke. Preparation does not create or push a release tag.

## Initial publication recovery

v1.5.0 passed promotion CI but its Windows release identity step failed while decoding UTF-8 GitHub CLI output with the default Windows code page, before packaging or publication. The tag remains unchanged. Version 1.5.1 includes explicit UTF-8 subprocess decoding and is the approved publication target for this minor release.
