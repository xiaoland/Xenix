# Supervised Learning

Classification predicts observed categories; regression predicts numeric outcomes. Bind the outcome as `target`, usable predictors as features, and repeated business entities as `group` where appropriate. A field available only after the outcome is not a useful predictor for that earlier decision.

Models retain learned preprocessing and evaluate against a same-holdout baseline. Completed training returns the evidence and report links needed for comparison. Additional model runs, tuning, task queries, and charts are choices driven by the request, not prerequisites.

For classification, precision describes how many predicted positives are correct; recall describes how many true positives are recovered. F1 balances them, and AUC measures ranking. The business cost of misses versus false alarms matters more than accuracy alone. A threshold is a decision choice, not automatically 0.5.

For regression, MAE is average absolute error in target units, RMSE emphasizes large misses, and R² describes explained variance. Whether the error is acceptable depends on the decision.

Apply a returned retained model to the intended input Dataset or rows and deliver the public result. Explain important limits using the reported evaluation; feature importance and coefficients describe model behavior, not causal effects.
