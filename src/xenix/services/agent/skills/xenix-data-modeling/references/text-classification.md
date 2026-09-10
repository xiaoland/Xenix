# Text Classification

`text.classification.multilingual_logistic_regression_tfidf` accepts bilingual raw text. Roles are `text`, observed label `target`, and optional repeated business entity `group`. Missing labels are not negative labels.

The retained analyzer owns normalization, tokenization, masking, stopwords, and TF-IDF preparation. Custom dictionary and stopword resources are registered one-column Dataset IDs. Standalone tokenization is unnecessary unless tokens themselves are requested.

The service handles train-side vocabulary fitting and business/template grouping. Returned evaluation includes candidate-versus-dummy metrics, split facts, and preparation facts. Use the evidence relevant to label quality and generalization; there is no additional digest or overlap inspection ritual.

Apply accepts the same raw-text column and produces prediction and prediction_score alongside input columns. Deliver the returned Dataset and Artifact. Explain material label-quality or unfamiliar-text limitations; predictions remain estimates of labels.
