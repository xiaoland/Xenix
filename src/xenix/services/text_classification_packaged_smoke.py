from __future__ import annotations

import numpy as np
import pandas as pd

from .data_tokenization_contracts import TextPreparationInput
from .ml.models.text_analysis import MultilingualTextClassifier
from .ml.text_preparation import build_text_preparer


def run_text_classification_packaged_smoke() -> None:
    """Exercise retained bilingual preparation, TF-IDF, and raw-text apply."""

    training_texts = pd.Series(
        [
            "密码重置失败 access login blocked",
            "无法登录 password reset needed",
            "credential locked 账号密码错误",
            "登录验证失败 need access help",
            "access denied 密码无法使用",
            "forgot password 无法进入账户",
            "账单退款错误 billing refund review",
            "重复扣费 invoice charged twice",
            "refund missing 退款尚未到账",
            "billing amount wrong 账单金额不对",
            "invoice dispute 请求费用复核",
            "重复收费 need billing review",
        ],
        dtype="string",
    )
    labels = pd.Series(
        ["access"] * 6 + ["billing"] * 6,
        dtype="string",
    )
    preparer = build_text_preparer(
        TextPreparationInput(
            tokenizer_profile="multilingual_business_v1",
            phrase_mode="unigram_bigram",
        )
    )
    analyzer = MultilingualTextClassifier(
        preparer=preparer,
        max_features=500,
        minimum_document_frequency=1,
        class_weight="balanced",
    ).fit(training_texts, labels)
    apply_texts = pd.Series(
        ["PASSWORD reset 仍然失败", "invoice refund 重复扣费"],
        dtype="string",
    )
    predictions = analyzer.predict(apply_texts)
    probabilities = analyzer.predict_proba(apply_texts)
    apply_corpus = analyzer.prepare(apply_texts)
    if (
        predictions.tolist() != ["access", "billing"]
        or probabilities.shape != (2, 2)
        or not np.isfinite(probabilities).all()
        or not np.allclose(probabilities.sum(axis=1), 1.0)
        or analyzer.preparer.specification.profile_key
        != "multilingual_business_v1"
        or analyzer.fit_vectorization_facts.fit_row_count != 12
        or apply_corpus.quality_facts.eligible_row_count != 2
    ):
        raise RuntimeError("Packaged multilingual text classification smoke failed.")
