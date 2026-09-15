# Text Classification

`text.classification.multilingual_logistic_regression_tfidf` accepts bilingual raw text. Roles are `text`, observed label `target`, and optional repeated business entity `group`. Missing labels are not negative labels.

Choose `text_strategy` through model parameters: `words` segments text, `characters` uses character n-grams, and `pretokenized` consumes whitespace-separated tokens without another segmentation pass. Word/token filtering is configurable; custom dictionary and stopword resources are one-column Dataset IDs. The analyzer saves the choice and learned preparation for future batches. Separate business cleaning can use `data.transform`.

New training returns grouped cross-validation against a dummy baseline, fold variability and an `evaluation_id`; matching IDs mean reused validation data, not independent confirmation after tuning. Vocabulary is fitted inside each fold. A high score on a small sample does not guarantee future accuracy.

Apply reuses the saved strategy and reports feature coverage alongside predictions. `no_known_features` means the label relies only on class bias; `prediction_score` is uncalibrated model probability. Accuracy among auto-routed rows is distinct from accuracy across the whole batch. Deliver the returned Dataset and Artifact, with material limitations.
