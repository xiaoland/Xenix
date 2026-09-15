# Retained Text Classification

The Agent selects a preprocessing strategy through model parameters discovered with `model.metadata`; MLService stages explicit resources, the worker executes the strategy, and the saved analyzer owns its reuse. The Tool design rationale belongs to [Agent Tool boundaries](agent-tools.md); task and artifact ownership remain in [ML lifecycle](../20-prd-tdd/ml-task-lifecycle.md).

## Strategy and Reuse

`text_strategy=words` uses multilingual segmentation with configurable word length, stopwords and unigrams/bigrams. New classification defaults retain single-character words and disable the built-in stopword list. `characters` uses normalized character n-grams of lengths 2 through `character_ngram_max`; word segmentation, word length, dictionary and stopword options do not apply. `pretokenized` consumes whitespace-separated tokens without re-segmenting, lowercasing or masking them, with the selected token filtering and word n-grams. Business cleaning can be performed separately through `data.transform`; application inputs must provide the same raw-text or prepared-token column that trained the analyzer.

The shared staging contract and retained specification carry these choices across local/remote workers. Other text families and standalone legacy tokenization retain their existing default preparation. Old serialized analyzers use their retained stopwords and vocabulary; missing strategy fields mean the former word strategy and length-two filter. They are not silently reprocessed using new classification defaults.

## Evaluation Ownership

The evaluation policy owner selects grouped cross-validation for new multilingual classification training. Each connected business/template group stays within a fold; each fold fits its own vocabulary and classifier using only training rows, then records out-of-fold predictions and a training-partition dummy baseline. Up to five folds are used, limited by the number of independent groups. Expected candidate failures such as an empty fold vocabulary are reported per fold; incomplete evaluation does not receive an aggregate accuracy computed from only successful folds. A usable final model can still be retained when validation is unavailable, with that limitation returned explicitly.

The worker persists out-of-fold predictions, probabilities, membership and evidence in the existing evaluation artifact slot. Evaluation computes metrics from those predictions rather than from the all-rows model. The artifact slot retains its historical `holdout_artifact_path` field name for lifecycle compatibility; policy identifies its contents. The canonical apply model is fitted on all eligible rows. Existing saved holdout policies retain their evaluation path; no migration or second task lifecycle is introduced.

Tool feedback includes pooled out-of-fold metrics, per-fold accuracy and counts, variability, coverage and a short `evaluation_id` based on source content, eligible labels and fold membership. Equal IDs mean reused validation data, even across different parameter choices. This is model-selection evidence, not independent acceptance after repeated tuning or a guarantee that future accuracy exceeds a requested threshold. Full internal artifacts remain available through normal ML reports rather than filling the initial tool catalog.

## Prediction Feedback

Apply preserves input rows and adds the predicted label, uncalibrated maximum class probability, recognized feature occurrence count, recognized/total feature occurrence ratio and an evidence label. `no_known_features` denotes a bias-only prediction and remains an ordinary output row. Character strategy coverage counts character n-grams; word and pretokenized coverage counts their configured word n-grams. The summary reports the selected strategy, number of zero-feature rows and average coverage. Coverage is evidence about the input representation, not a probability of correctness or an automatic routing threshold.

Existing service lifecycle coverage verifies persistence, evaluation artifacts, application and source immutability. Manual strategy probes exercise all three representations, numeric labels, out-of-fold grouping and retained-model application; benchmark judgments remain separate from these checks.
