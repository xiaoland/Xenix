# Partially Labeled Data

Missing, unknown, or pending labels may mean unlabeled rather than negative. Resolve that distinction from the business context. The quality and coverage of observed labels determine what a model can learn.

Available semi-supervised models and roles are described by `model.metadata`. A supervised model applied to unlabeled rows is also useful when the request is prediction or prioritization. Choose according to the task; no mandatory baseline-then-pseudo-label pipeline is prescribed.

Predicted pseudo-labels are estimates, distinct from observed labels. Confidence thresholds depend on error costs and calibration; there are no universal 0.85/0.15 cutoffs. Deliver useful predictions or review candidates and explain limitations supported by the evaluation. More manual labels may be the most valuable improvement when evidence is weak.
