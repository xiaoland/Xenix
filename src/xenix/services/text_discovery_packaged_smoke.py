from __future__ import annotations

import math

import pandas as pd

from .data_tokenization_contracts import TextPreparationInput
from .ml.text_discovery import (
    MultilingualTextClusterer,
    MultilingualTextRetriever,
    MultilingualTopicDiscoverer,
    prepare_discovery_corpus,
)
from .ml.text_preparation import build_text_preparer


def run_text_discovery_packaged_smoke() -> None:
    """Exercise packaged raw-text clustering, topics, and exact retrieval."""

    frame = pd.DataFrame(
        {
            "text": [
                "隔音很好 room stayed quiet through the night",
                "安静办公 acoustic focus was excellent",
                "走廊噪声 sound insulation needs attention",
                "quiet meeting space 适合专注讨论",
                "夜间无噪音 the room felt peaceful",
                "acoustic panels kept calls 清晰安静",
                "牛肉面汤底浓郁 noodle broth tasted rich",
                "早餐面包新鲜 breakfast pastry was fresh",
                "spicy tofu flavor 香辣豆腐很入味",
                "咖啡香气很好 the roast tasted balanced",
                "fresh salad ingredients 蔬菜很清爽",
                "dessert texture 甜点口感细腻",
                "前台耐心解释 staff gave patient guidance",
                "friendly support 团队响应很及时",
                "服务人员主动协助 proactive help arrived quickly",
                "patient host explained every step 主持人很耐心",
                "客服回复清楚 support response was clear",
                "团队友善并快速解决问题 friendly resolution",
            ],
            "relevance_group": ["quiet"] * 6 + ["food"] * 6 + ["service"] * 6,
            "document_id": [f"packaged-doc-{index:02d}" for index in range(18)],
        }
    )
    preparer = build_text_preparer(
        TextPreparationInput(
            tokenizer_profile="multilingual_business_v1",
            phrase_mode="unigram_bigram",
        )
    )
    prepared = prepare_discovery_corpus(
        frame,
        text_column="text",
        business_group_column=None,
        preparer=preparer,
        minimum_rows=12,
    )

    clusterer = MultilingualTextClusterer(
        preparer=preparer,
        n_clusters=3,
        max_features=500,
        displayed_term_count=4,
    ).fit(prepared)
    cluster_evaluation = clusterer.evaluate(prepared)
    cluster_apply = clusterer.apply(pd.Series(["安静房间", "fresh breakfast", "friendly support"]))

    topic_evaluator = MultilingualTopicDiscoverer(
        preparer=preparer,
        topic_count=3,
        max_features=500,
        displayed_term_count=4,
    )
    topic_evaluation = topic_evaluator.fit_evaluation(
        prepared,
        source_dataset_snapshot_digest="a" * 64,
    )
    topic_apply_analyzer = MultilingualTopicDiscoverer(
        preparer=preparer,
        topic_count=3,
        max_features=500,
        displayed_term_count=4,
    ).fit_all(prepared, evaluation_reference=topic_evaluator)
    topic_apply = topic_apply_analyzer.apply(pd.Series(["quiet acoustic room", "早餐味道新鲜"]))

    retriever = MultilingualTextRetriever(
        preparer=preparer,
        max_features=500,
        top_k=3,
        minimum_similarity=0.0,
    ).fit(
        prepared,
        document_ids=frame["document_id"],
        relevance_groups=frame["relevance_group"],
    )
    retrieval_evaluation = retriever.evaluate(prepared)
    retrieval_apply = retriever.apply(pd.Series(["patient friendly support"]))

    if (
        cluster_evaluation.facts.quality.realized_cluster_count != 3
        or cluster_evaluation.facts.stability.successful_run_count < 4
        or cluster_apply.facts.assigned_row_count != 3
        or topic_evaluation.facts.split.group_overlap_count != 0
        or topic_evaluation.facts.stability.successful_run_count != 5
        or topic_apply.facts.topic_label_identity_digest
        != topic_evaluation.facts.topic_label_identity_digest
        or topic_apply.facts.assigned_row_count != 2
        or retrieval_evaluation.facts.mode != "relevance_evaluated"
        or retrieval_evaluation.facts.ranking is None
        or not math.isfinite(retrieval_evaluation.facts.ranking.ndcg_at_k)
        or retrieval_evaluation.facts.diagnostics.self_match_violation_count != 0
        or retrieval_apply.facts.diagnostics.result_row_count != 3
    ):
        raise RuntimeError("Packaged multilingual text discovery smoke failed.")
