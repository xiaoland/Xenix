# Neural Networks

`classification.mlp` and `regression.mlp` are nonlinear tabular candidates. Choose them when their likely predictive value justifies runtime and reduced interpretability; they can be compared with other candidates in the same training request.

Xenix exposes `hidden_layer_size` as one integer, not a tuple of layer sizes. Metadata describes supported activation, regularization, learning rate, and iteration options. Defaults are appropriate when the request does not justify tuning.

Use evaluation to judge practical improvement and overfitting. There is no requirement to train a separate baseline first or recite a fixed risk statement. Explain the tradeoffs that matter to the user's decision.
