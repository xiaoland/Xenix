from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer

from ....exceptions import ValidationError
from ...data_tokenization_contracts import TextPreparationInput
from ..contracts import (
    ApplyTaskRequest,
    CandidateMetrics,
    EvaluateTaskRequest,
    FitTaskRequest,
    HyperparameterTuningTaskRequest,
    PreparationFacts,
    SplitFacts,
)
from ..dataset_loader import load_dataset
from ..preparation import (
    PreparedSupervisedSplit,
    attach_evaluation_context,
    prepare_supervised_split,
)
from ..text_discovery import (
    MultilingualTextRetriever,
    TextClusteringEvaluationFacts,
    TextRetrievalEvaluationFacts,
    TextTopicEvaluationFacts,
)
from ..text_preparation import (
    PreparedTextClassificationData,
    TextLeakageFacts,
    TextPreparationQualityFacts,
    TextPreparer,
    TextVectorizationFacts,
    prepare_text_classification_data,
)

if TYPE_CHECKING:
    from .text_analysis import MultilingualTextClassificationParams, _TextDiscoveryParams


_TEXT_EVALUATION_CONTEXT_KEY = "xenix.text_classification_context.v1"


def _single_role_column(role_bindings: list[dict[str, Any]], role: str) -> str:
    for binding in role_bindings:
        if binding.get("role") == role and isinstance(binding.get("columns"), list):
            columns = [str(column) for column in binding["columns"]]
            if len(columns) == 1:
                return columns[0]
    raise ValidationError(f"Text analysis model requires exactly one '{role}' column.")


def _optional_role_column(role_bindings: list[dict[str, Any]], role: str) -> str | None:
    for binding in role_bindings:
        if binding.get("role") == role and isinstance(binding.get("columns"), list):
            columns = [str(column) for column in binding["columns"]]
            if len(columns) == 1:
                return columns[0]
    return None


def _text_preparation_input(
    request: FitTaskRequest | HyperparameterTuningTaskRequest,
    params: MultilingualTextClassificationParams | _TextDiscoveryParams,
) -> TextPreparationInput:
    value = getattr(request, "text_preparation", None)
    if value is None:
        raise ValidationError(
            "Multilingual raw-text analysis requires worker-staged text_preparation, including explicit empty resources."
        )
    elif isinstance(value, TextPreparationInput):
        prepared_input = value
    else:
        prepared_input = TextPreparationInput.model_validate(value)
    staged_dictionary_ids = [resource.dataset_id for resource in prepared_input.custom_dictionary_resources]
    staged_stopword_ids = [resource.dataset_id for resource in prepared_input.stopword_resources]
    if prepared_input.tokenizer_profile != params.preparation_profile:
        raise ValidationError("Staged text preparation profile does not match the admitted model parameters.")
    if prepared_input.phrase_mode != params.phrase_mode:
        raise ValidationError("Staged text preparation phrase mode does not match the admitted model parameters.")
    if staged_dictionary_ids != params.custom_dictionary_dataset_ids:
        raise ValidationError("Staged custom dictionary Dataset IDs do not match the admitted model parameters.")
    if staged_stopword_ids != params.stopword_dataset_ids:
        raise ValidationError("Staged stopword Dataset IDs do not match the admitted model parameters.")
    return prepared_input


def _prepare_multilingual_request_data(
    request: FitTaskRequest | HyperparameterTuningTaskRequest | EvaluateTaskRequest,
    preparer: TextPreparer,
) -> PreparedTextClassificationData:
    dataframe = load_dataset(Path(request.dataset_source_path))
    return prepare_text_classification_data(
        dataframe,
        text_column=_single_role_column(request.train_role_bindings, "text"),
        target_column=_single_role_column(request.train_role_bindings, "target"),
        business_group_column=_optional_role_column(request.train_role_bindings, "group"),
        preparer=preparer,
    )


def _multilingual_artifact_paths(model_key: str, task_dir: Path) -> tuple[Path, Path, Path]:
    model_dir = task_dir / "models"
    input_dir = task_dir / "input"
    model_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    stem = model_key.replace(".", "_")
    return (
        model_dir / f"{stem}.joblib",
        model_dir / f"{stem}-final.joblib",
        input_dir / "multilingual_text_holdout.pkl",
    )


def _save_multilingual_holdout(
    texts: pd.Series,
    labels: pd.Series,
    training_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    split_facts: SplitFacts,
    preparation_facts: PreparationFacts,
    text_preparation_facts: TextPreparationQualityFacts,
    text_leakage_facts: TextLeakageFacts,
    text_vectorization_facts: TextVectorizationFacts,
    path: Path,
) -> None:
    holdout = pd.DataFrame({text_column: texts.tolist(), target_column: labels.tolist()})
    attach_evaluation_context(
        holdout,
        training_target=training_labels,
        split_facts=split_facts,
        preparation_facts=preparation_facts,
    )
    holdout.attrs[_TEXT_EVALUATION_CONTEXT_KEY] = {
        "text_preparation_facts": text_preparation_facts.model_dump(mode="json"),
        "text_leakage_facts": text_leakage_facts.model_dump(mode="json"),
        "text_vectorization_facts": text_vectorization_facts.model_dump(mode="json"),
    }
    holdout.to_pickle(path)


def _read_multilingual_holdout_context(
    holdout: pd.DataFrame,
) -> tuple[TextPreparationQualityFacts, TextLeakageFacts, TextVectorizationFacts]:
    payload = holdout.attrs.get(_TEXT_EVALUATION_CONTEXT_KEY)
    if not isinstance(payload, dict):
        raise ValidationError(
            "The holdout artifact predates retained multilingual text evidence; retrain before evaluation."
        )
    return (
        TextPreparationQualityFacts.model_validate(payload.get("text_preparation_facts")),
        TextLeakageFacts.model_validate(payload.get("text_leakage_facts")),
        TextVectorizationFacts.model_validate(payload.get("text_vectorization_facts")),
    )


def _verify_recomputed_text_context(
    holdout: pd.DataFrame,
    recomputed_texts: pd.Series,
    recomputed_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    stored_split: SplitFacts,
    recomputed_split: SplitFacts,
    stored_text_facts: tuple[TextPreparationQualityFacts, TextLeakageFacts, TextVectorizationFacts],
    recomputed_preparation: TextPreparationQualityFacts,
    recomputed_leakage: TextLeakageFacts,
    recomputed_fit_vectorization: TextVectorizationFacts,
) -> None:
    if stored_split.model_dump(mode="json") != recomputed_split.model_dump(mode="json"):
        raise ValidationError("Recomputed text split facts do not match the private FIT evidence.")
    stored_preparation, stored_leakage, stored_vectorization = stored_text_facts
    if (
        stored_preparation != recomputed_preparation
        or stored_leakage != recomputed_leakage
        or stored_vectorization != recomputed_fit_vectorization
    ):
        raise ValidationError(
            "Recomputed text preparation, leakage, or train-only vocabulary facts do not match the private FIT evidence."
        )
    if text_column not in holdout.columns or target_column not in holdout.columns:
        raise ValidationError("The private text holdout artifact is missing its raw text or target column.")
    stored_texts = _as_text_series(holdout[text_column])
    expected_texts = _as_text_series(recomputed_texts)
    if stored_texts.tolist() != expected_texts.tolist():
        raise ValidationError("Recomputed text holdout membership does not match the private FIT evidence.")
    if holdout[target_column].tolist() != recomputed_labels.tolist():
        raise ValidationError("Recomputed text holdout targets do not match the private FIT evidence.")


def _require_zero_text_leakage(facts: TextLeakageFacts) -> None:
    if (
        facts.train_business_group_overlap_count
        or facts.train_template_group_overlap_count
        or facts.train_connected_group_overlap_count
    ):
        raise ValidationError("Text classification rejected a split with business or template leakage.")


def _multilingual_result_summary(
    prepared: PreparedTextClassificationData,
    split: PreparedSupervisedSplit,
    vectorization: TextVectorizationFacts,
) -> dict[str, Any]:
    return {
        "class_count": int(prepared.labels.nunique(dropna=True)),
        "train_row_count": int(len(split.train_target.index)),
        "holdout_row_count": int(len(split.holdout_target.index)),
        "evaluation_model_training_scope": "holdout_train_split",
        "apply_model_training_scope": "all_eligible_rows",
        "preparation_specification_digest": prepared.specification.specification_digest,
        "connected_group_count": int(prepared.connected_groups.nunique(dropna=False)),
        "transformed_feature_count": vectorization.transformed_feature_count,
        "vocabulary_digest": vectorization.vocabulary_digest,
    }


def _as_text_series(values: pd.Series) -> pd.Series:
    return values.astype("string").fillna("").reset_index(drop=True)


def _normalize_token_text_series(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .fillna("")
        .map(lambda value: " ".join(str(value).split()))
        .astype("string")
    )


def _prepare_supervised_text(
    dataframe: pd.DataFrame,
    *,
    text_column: str,
    target_column: str,
    group_column: str | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series | None]:
    if text_column not in dataframe.columns:
        raise ValidationError(f"Text column '{text_column}' is missing.")
    if target_column not in dataframe.columns:
        raise ValidationError(f"Target column '{target_column}' is missing.")
    if group_column is not None and group_column not in dataframe.columns:
        raise ValidationError(f"Group column '{group_column}' is missing.")
    if group_column in {text_column, target_column}:
        raise ValidationError("The group column must be distinct from text and target columns.")
    texts = _normalize_token_text_series(dataframe[text_column])
    labels = dataframe[target_column].copy()
    mask = texts.ne("") & labels.notna()
    if not mask.any():
        raise ValidationError("Text classification requires non-empty tokenized text rows with target labels.")
    filtered_texts = texts.loc[mask].reset_index(drop=True)
    filtered_labels = labels.loc[mask].reset_index(drop=True)
    if filtered_labels.nunique(dropna=True) < 2:
        raise ValidationError("Text classification requires at least two target classes.")
    groups = dataframe.loc[mask, group_column].reset_index(drop=True) if group_column is not None else None
    return filtered_texts, filtered_labels, groups


def _text_train_test_split(
    texts: pd.Series,
    labels: pd.Series,
    request: FitTaskRequest | HyperparameterTuningTaskRequest,
    *,
    groups: pd.Series | None = None,
) -> PreparedSupervisedSplit:
    return prepare_supervised_split(texts, labels, request, groups=groups)


def _save_text_holdout(
    texts: pd.Series,
    labels: pd.Series,
    training_labels: pd.Series,
    *,
    text_column: str,
    target_column: str,
    split_facts: SplitFacts,
    preparation_facts: PreparationFacts,
    path: Path,
) -> None:
    holdout = pd.DataFrame({text_column: texts.tolist(), target_column: labels.tolist()})
    attach_evaluation_context(
        holdout,
        training_target=training_labels,
        split_facts=split_facts,
        preparation_facts=preparation_facts,
    )
    holdout.to_pickle(path)


def _serialize_search_best_params(best_params: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    for key, value in best_params.items():
        simple_key = str(key).split("__", 1)[-1]
        if simple_key == "ngram_range" and isinstance(value, tuple) and len(value) == 2:
            serialized["ngram_max"] = int(value[1])
        else:
            serialized[simple_key] = value
    return serialized


def _single_role_column_from_artifact(estimator: Any, fallback_columns: list[str]) -> str:
    text_column = getattr(estimator, "text_column", None)
    if isinstance(text_column, str) and text_column.strip():
        return text_column
    if fallback_columns:
        return str(fallback_columns[0])
    raise ValidationError("The trained text model does not expose its required text column.")


def _write_apply_output(task_dir: Path, file_name: str, frames: list[pd.DataFrame]) -> Path:
    output_dir = task_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / file_name
    pd.concat(frames, ignore_index=True).to_csv(output_path, index=False)
    return output_path


def _tfidf_vectorizer(*, max_features: int, ngram_max: int) -> TfidfVectorizer:
    return TfidfVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        max_features=max_features,
        ngram_range=(1, ngram_max),
    )


def _top_terms_from_centers(
    centers: np.ndarray,
    feature_names: Any,
    *,
    top_n: int,
    label_prefix: str,
) -> list[dict[str, Any]]:
    terms = list(feature_names)
    rows: list[dict[str, Any]] = []
    for group_index, weights in enumerate(np.asarray(centers)):
        ranked_indexes = np.argsort(weights)[::-1][:top_n]
        rows.append(
            {
                f"{label_prefix}_id": int(group_index),
                "terms": [str(terms[index]) for index in ranked_indexes],
            }
        )
    return rows


def _discovery_paths(model_key: str, task_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    stem = model_key.replace(".", "_")
    model_dir = task_dir / "models"
    input_dir = task_dir / "input"
    output_dir = task_dir / "output"
    model_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    return (
        model_dir / f"{stem}.joblib",
        model_dir / f"{stem}-final.joblib",
        input_dir / f"{stem}-evidence.json",
        output_dir / f"{stem}-results.csv",
        output_dir / f"{stem}-report.json",
    )


def _write_discovery_evidence(path: Path, facts: BaseModel, snapshot_digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_key": facts.__class__.__name__,
                "source_dataset_snapshot_digest": snapshot_digest,
                "facts": facts.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _write_json_report(path: Path, facts: BaseModel) -> None:
    path.write_text(facts.model_dump_json(indent=2), encoding="utf-8")


def _verify_discovery_evidence(path: Path, facts: BaseModel, snapshot_digest: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValidationError("The private text discovery evidence could not be read.") from exc
    if payload.get("source_dataset_snapshot_digest") != snapshot_digest:
        raise ValidationError("The text discovery Dataset snapshot no longer matches FIT evidence.")
    if payload.get("schema_key") != facts.__class__.__name__:
        raise ValidationError("The private text discovery evidence has the wrong fact type.")
    if payload.get("facts") != facts.model_dump(mode="json"):
        raise ValidationError("Recomputed text discovery facts do not match authoritative FIT evidence.")


def _cluster_summary(facts: TextClusteringEvaluationFacts) -> dict[str, Any]:
    return {
        "cluster_count": facts.quality.realized_cluster_count,
        "evaluated_row_count": facts.quality.evaluated_row_count,
        "cosine_silhouette": facts.quality.cosine_silhouette,
        "mean_resampling_stability": facts.stability.mean_adjusted_rand,
        "preparation_specification_digest": facts.specification.specification_digest,
    }


def _topic_summary(facts: TextTopicEvaluationFacts) -> dict[str, Any]:
    return {
        "topic_count": facts.quality.topic_count,
        "train_row_count": facts.split.train_row_count,
        "holdout_row_count": facts.split.holdout_row_count,
        "heldout_perplexity": facts.quality.heldout_perplexity,
        "topic_label_identity_digest": facts.topic_label_identity_digest,
        "preparation_specification_digest": facts.specification.specification_digest,
    }


def _retrieval_summary(facts: TextRetrievalEvaluationFacts) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": facts.mode,
        "indexed_document_count": facts.diagnostics.indexed_document_count,
        "result_row_count": facts.diagnostics.result_row_count,
        "preparation_specification_digest": facts.specification.specification_digest,
    }
    if facts.ranking is not None:
        result.update(facts.ranking.model_dump(mode="json"))
    return result


def _cluster_candidate_metrics(facts: TextClusteringEvaluationFacts) -> CandidateMetrics:
    silhouette = facts.quality.cosine_silhouette
    if silhouette is None:
        raise ValidationError("Text clustering cannot publish evaluation without a defined cosine silhouette.")
    return CandidateMetrics(
        primary_metric_name="cosine_silhouette",
        primary_metric_value=silhouette,
        metrics={
            "cosine_silhouette": silhouette,
            "resampling_stability": facts.stability.mean_adjusted_rand or 0.0,
            "minimum_cluster_share": facts.quality.minimum_cluster_share,
        },
        details={"assignment_digest": facts.quality.assignment_digest},
    )


def _topic_candidate_metrics(facts: TextTopicEvaluationFacts) -> CandidateMetrics:
    return CandidateMetrics(
        primary_metric_name="heldout_perplexity",
        primary_metric_value=facts.quality.heldout_perplexity,
        metrics={
            "heldout_perplexity": facts.quality.heldout_perplexity,
            "coherence": facts.quality.mean_coherence,
            "topic_diversity": facts.quality.term_diversity,
            "resampling_stability": facts.stability.mean_matched_cosine or 0.0,
        },
        details={
            "dominant_topic_digest": facts.quality.dominant_topic_digest,
            "topic_label_identity_digest": facts.topic_label_identity_digest,
        },
    )


def _retrieval_candidate_metrics(facts: TextRetrievalEvaluationFacts) -> CandidateMetrics | None:
    if facts.ranking is None:
        return None
    return CandidateMetrics(
        primary_metric_name="ndcg_at_k",
        primary_metric_value=facts.ranking.ndcg_at_k,
        metrics={
            "ndcg_at_k": facts.ranking.ndcg_at_k,
            "recall_at_k": facts.ranking.recall_at_k,
            "mrr_at_k": facts.ranking.mrr_at_k,
        },
        details={"result_digest": facts.diagnostics.result_digest},
    )


def _required_retained_column(value: str | None, role: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise ValidationError(f"The retained text analyzer does not expose its '{role}' column.")


def _load_raw_text_apply_inputs(
    request: ApplyTaskRequest,
    text_column: str,
) -> tuple[list[pd.DataFrame], pd.Series, list[dict[str, Any]]]:
    frames: list[pd.DataFrame] = []
    texts: list[Any] = []
    locations: list[dict[str, Any]] = []
    for input_file in request.input_files:
        dataframe = load_dataset(Path(input_file.absolute_path))
        if text_column not in dataframe.columns:
            raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {text_column}.")
        frames.append(dataframe)
        texts.extend(dataframe[text_column].tolist())
        locations.extend(
            {"source_file": input_file.file_name, "input_row_number": row_number}
            for row_number in range(1, len(dataframe.index) + 1)
        )
    return frames, pd.Series(texts, dtype="object"), locations


def _topic_export_frame(
    source_positions: np.ndarray,
    distributions: list[list[float] | None],
) -> pd.DataFrame:
    topic_count = max((len(row) for row in distributions if row is not None), default=0)
    rows: list[dict[str, Any]] = []
    for source_position, distribution in zip(source_positions.tolist(), distributions, strict=True):
        row: dict[str, Any] = {"source_row_number": int(source_position) + 1}
        if distribution is None:
            row.update({"dominant_topic": None, "topic_score": None})
            row.update({f"topic_{topic}_share": None for topic in range(1, topic_count + 1)})
        else:
            row.update(
                {
                    "dominant_topic": int(np.argmax(distribution)) + 1,
                    "topic_score": float(max(distribution)),
                }
            )
            row.update(
                {f"topic_{topic}_share": float(distribution[topic - 1]) for topic in range(1, topic_count + 1)}
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _append_topic_outputs(
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
    distributions: list[list[float] | None],
) -> pd.DataFrame:
    output = dataframe.copy()
    topic_values = _topic_export_frame(source_positions, distributions).drop(columns=["source_row_number"])
    for column in topic_values.columns:
        output[column] = pd.NA
        output.iloc[source_positions, output.columns.get_loc(column)] = topic_values[column].tolist()
    return output


def _eligible_role_values(
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
    column: str | None,
) -> pd.Series | None:
    if column is None:
        return None
    if column not in dataframe.columns:
        raise ValidationError(f"Text retrieval role column '{column}' is missing.")
    return dataframe.iloc[source_positions][column].reset_index(drop=True)


def _retrieval_export_frame(analyzer: MultilingualTextRetriever, matches: Any) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "query_document_id": analyzer.matched_document_id(match.query_position),
                "query_text": analyzer.matched_document_text(match.query_position),
                "matched_document_id": analyzer.matched_document_id(match.matched_document_position),
                "matched_text": analyzer.matched_document_text(match.matched_document_position),
                "rank": match.rank,
                "similarity": match.similarity,
            }
            for match in matches
        ],
        columns=[
            "query_document_id",
            "query_text",
            "matched_document_id",
            "matched_text",
            "rank",
            "similarity",
        ],
    )


def _verify_retrieval_source_identities(
    analyzer: MultilingualTextRetriever,
    dataframe: pd.DataFrame,
    source_positions: np.ndarray,
) -> None:
    document_ids = _eligible_role_values(dataframe, source_positions, analyzer.document_id_column)
    if analyzer.document_id_column is None:
        expected_ids = tuple(f"row-{position + 1}" for position in source_positions)
    else:
        if document_ids is None:
            raise ValidationError("The retained retrieval document identity role is missing.")
        expected_ids = tuple(document_ids.astype("string").fillna("").astype(str).tolist())
    if expected_ids != analyzer.document_ids:
        raise ValidationError("Recomputed retrieval document identities do not match the retained local index.")
    relevance = _eligible_role_values(dataframe, source_positions, analyzer.relevance_group_column)
    current_hashes = (
        tuple(hashlib.sha256(str(value).encode("utf-8")).hexdigest() for value in relevance.tolist())
        if relevance is not None
        else None
    )
    if current_hashes != analyzer.relevance_group_hashes:
        raise ValidationError("Recomputed retrieval relevance truth does not match authoritative FIT evidence.")


def _concat_optional_apply_column(frames: list[pd.DataFrame], column: str | None) -> pd.Series | None:
    if column is None:
        return None
    if any(column not in frame.columns for frame in frames):
        raise ValidationError(f"Retrieval apply inputs are missing retained document ID column '{column}'.")
    return pd.concat([frame[column] for frame in frames], ignore_index=True)
