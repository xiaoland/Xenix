# Multilingual Raw-Text Classification Reference

Use this reference for supervised bilingual business-text labels. It does not apply to descriptive keyword counts, unlabeled topic discovery, clustering, or similarity retrieval.

## Admission and roles

Profile missing text, missing labels, class counts, duplicates, and business-group cardinality. Bind exactly:

- `text`: one raw-text column;
- `target`: one observed label column;
- optional `group`: a stable customer, account, case, campaign, or other business entity that must not cross evaluation partitions.

Do not use the group, identifiers, timestamps, or post-resolution fields as predictive text. Empty or unlabeled rows are excluded with explicit counts; they are not silently assigned a class.

## Retained preparation

Inspect `text.classification.multilingual_logistic_regression_tfidf` and fill only its advertised shallow schema. `multilingual_business_v1` owns deterministic Unicode NFKC/case normalization, URL/email/number masking, bilingual tokenization, built-in business stopwords, and unigram or short-phrase mode.

Optional custom dictionary and stopword sources must be registered one-column Datasets. Pass only their Dataset IDs; never copy terms into the model prompt or invent local paths. Xenix stages the registered materialization, verifies its hash, and retains only bounded Dataset/hash/term-count references in the public specification.

## Leakage and evaluation

Xenix creates service-owned exact/template/near-duplicate groups and takes the connected union with the optional business group. A credible Evaluate report has zero business-group, template-group, and connected-group overlap between train and holdout.

TF-IDF vocabulary and IDF are fit only on the outer training partition. Require the authoritative Evaluate task and compare the candidate against its same-holdout dummy baseline using balanced accuracy, macro/weighted F1, accuracy, and any admitted probability metrics. Vocabulary size/digest and OOV counts are bounded facts; vocabulary terms and raw text stay local.

If grouping cannot leave every required class in both train and holdout, stop. Do not request a row-random fallback or weaken template grouping.

## Apply and interpretation

Apply the retained full-history analyzer to a registered Dataset or inline rows containing the same raw-text column. The local result preserves input columns and adds `prediction` and `prediction_score`. Check the retained preparation specification and apply prediction digest, then link the public result Dataset and Artifact.

Historical label recovery is not causal evidence, a fairness review, or permission for automatic decisions. State label-quality limits, OOV/empty-text facts, business-group scope, human-review needs, and monitoring/retraining triggers.
