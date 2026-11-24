from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, PositiveInt, field_validator

from .....exceptions import ValidationError
from ....storage.models import ProblemKind
from ...contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    TrainingScopeFacts,
)
from ...dataset_loader import load_dataset
from ...preparation import dataset_snapshot_digest
from ...text_discovery import (
    MultilingualTextClusterer,
    MultilingualTextRetriever,
    MultilingualTopicDiscoverer,
    prepare_discovery_corpus,
)
from ...text_preparation import build_text_preparer
from ...types import (
    ColumnRoleKind,
    EvaluationKind,
    ModelFamily,
    ModelResultContract,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)
from .._text_helpers import (
    _append_topic_outputs,
    _cluster_candidate_metrics,
    _cluster_summary,
    _concat_optional_apply_column,
    _discovery_paths,
    _eligible_role_values,
    _load_raw_text_apply_inputs,
    _optional_role_column,
    _required_retained_column,
    _retrieval_candidate_metrics,
    _retrieval_export_frame,
    _retrieval_summary,
    _single_role_column,
    _text_preparation_input,
    _topic_candidate_metrics,
    _topic_summary,
    _verify_discovery_evidence,
    _verify_retrieval_source_identities,
    _write_discovery_evidence,
    _write_json_report,
)


class _TextDiscoveryParams(Protocol):
    @property
    def preparation_profile(self) -> str: ...

    @property
    def phrase_mode(self) -> str: ...

    @property
    def custom_dictionary_dataset_ids(self) -> list[int]: ...

    @property
    def stopword_dataset_ids(self) -> list[int]: ...


class _MultilingualDiscoveryParamsBase(BaseModel):
    preparation_profile: Literal["multilingual_business_v1"] = "multilingual_business_v1"
    phrase_mode: Literal["unigram", "unigram_bigram"] = "unigram"
    max_features: int = Field(default=5000, ge=200, le=50000)
    custom_dictionary_dataset_ids: list[PositiveInt] = Field(default_factory=list, max_length=4)
    stopword_dataset_ids: list[PositiveInt] = Field(default_factory=list, max_length=4)

    @field_validator("custom_dictionary_dataset_ids", "stopword_dataset_ids")
    @classmethod
    def _resource_ids_are_unique(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("Text preparation Dataset IDs cannot contain duplicates.")
        return values


class MultilingualTextClusteringParams(_MultilingualDiscoveryParamsBase):
    n_clusters: int = Field(default=4, ge=2, le=20)
    displayed_term_count: int = Field(default=8, ge=3, le=12)


class MultilingualTextTopicModelingParams(_MultilingualDiscoveryParamsBase):
    topic_count: int = Field(default=4, ge=2, le=20)
    displayed_term_count: int = Field(default=8, ge=3, le=12)


class MultilingualTextRetrievalParams(_MultilingualDiscoveryParamsBase):
    top_k: int = Field(default=5, ge=1, le=50)
    minimum_similarity: float = Field(default=0.1, ge=0.0, le=1.0)


class MultilingualTextClusteringService(ModelServiceBase):
    key = "text.clustering.multilingual_kmeans_tfidf"
    display_name = "Multilingual Raw Text Clustering"
    problem_kind = ProblemKind.CLUSTERING
    evaluation_kind = EvaluationKind.TEXT_CLUSTERING
    family = "Text clustering"
    guidance = "Explores bilingual raw text structure with retained preparation and recomputable cosine evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.TEXT_ANALYZER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextClusteringParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw business text prepared inside the retained clusterer.",
            ),
            ModelRoleDefinition(
                name="group",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional business entity joined with template groups for stability resampling.",
            ),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw text transformed by the exact retained preparation specification.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextClusteringParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=group_column,
            preparer=preparer,
            minimum_rows=max(4, params.n_clusters + 1),
        )
        analyzer = MultilingualTextClusterer(
            preparer=preparer,
            n_clusters=params.n_clusters,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        ).fit(prepared)
        analyzer.text_column = text_column
        analyzer.group_column = group_column
        evaluation = analyzer.evaluate(prepared)
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(analyzer, model_path)
        joblib.dump(analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, dataset_snapshot_digest(request.dataset_snapshot))
        _write_json_report(report_path, evaluation.facts)
        cluster_output = dataframe.copy()
        cluster_output["cluster_label"] = pd.NA
        cluster_output.iloc[
            prepared.source_positions,
            cluster_output.columns.get_loc("cluster_label"),
        ] = evaluation.labels.tolist()
        cluster_output.to_csv(export_path, index=False)
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="all_eligible_rows",
                apply_model="all_eligible_rows",
            ),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_clustering_evaluation=evaluation.facts,
            result_summary=_cluster_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTextClusterer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=analyzer.group_column,
            preparer=analyzer.preparer,
            minimum_rows=max(4, analyzer.n_clusters + 1),
        )
        facts = analyzer.evaluate(prepared).facts
        _verify_discovery_evidence(
            Path(request.evaluate_model.holdout_artifact_path),
            facts,
            dataset_snapshot_digest(request.dataset_snapshot),
        )
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_cluster_candidate_metrics(facts),
            text_clustering_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTextClusterer = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        application = analyzer.apply(texts)
        output = pd.concat(frames, ignore_index=True)
        if len(frames) > 1:
            output["source_file"] = [item["source_file"] for item in locations]
        output["cluster_label"] = application.labels
        output_path = task_dir / "output" / "text_cluster_assignments.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output.index),
                input_file_count=len(frames),
                prediction_column_name="cluster_label",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_clustering_apply_facts=application.facts,
        )


class MultilingualTextTopicModelingService(ModelServiceBase):
    key = "text.topic_modeling.multilingual_lda"
    display_name = "Multilingual Raw Text Topic Discovery"
    problem_kind = ProblemKind.TOPIC_MODELING
    evaluation_kind = EvaluationKind.TOPIC_MODELING
    family = "Topic modeling"
    guidance = "Explores bilingual raw text topics with group-safe heldout and permutation-matched stability evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.TEXT_ANALYZER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextTopicModelingParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw business text prepared inside the retained topic analyzer.",
            ),
            ModelRoleDefinition(
                name="group",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description="Optional business entity joined with template groups for heldout isolation.",
            ),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="text",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Raw text transformed by the exact retained topic preparation specification.",
            )
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextTopicModelingParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        group_column = _optional_role_column(request.train_role_bindings, "group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=group_column,
            preparer=preparer,
            minimum_rows=max(8, params.topic_count + 2),
        )
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        evaluation_analyzer = MultilingualTopicDiscoverer(
            preparer=preparer,
            topic_count=params.topic_count,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        )
        evaluation = evaluation_analyzer.fit_evaluation(
            prepared,
            source_dataset_snapshot_digest=snapshot_digest,
        )
        evaluation_analyzer.text_column = text_column
        evaluation_analyzer.group_column = group_column
        final_analyzer = MultilingualTopicDiscoverer(
            preparer=preparer,
            topic_count=params.topic_count,
            max_features=params.max_features,
            displayed_term_count=params.displayed_term_count,
        ).fit_all(prepared, evaluation_reference=evaluation_analyzer)
        final_analyzer.text_column = text_column
        final_analyzer.group_column = group_column
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(evaluation_analyzer, model_path)
        joblib.dump(final_analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, snapshot_digest)
        _write_json_report(report_path, evaluation.facts)
        full_application = final_analyzer.apply(prepared.raw_texts)
        _append_topic_outputs(dataframe, prepared.source_positions, full_application.distributions).to_csv(
            export_path,
            index=False,
        )
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="connected_group_train_split",
                apply_model="all_eligible_rows",
            ),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_topic_evaluation=evaluation.facts,
            result_summary=_topic_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTopicDiscoverer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=analyzer.group_column,
            preparer=analyzer.preparer,
            minimum_rows=max(8, analyzer.topic_count + 2),
        )
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        facts = analyzer.recompute_evaluation(
            prepared,
            source_dataset_snapshot_digest=snapshot_digest,
        ).facts
        _verify_discovery_evidence(Path(request.evaluate_model.holdout_artifact_path), facts, snapshot_digest)
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_topic_candidate_metrics(facts),
            text_topic_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTopicDiscoverer = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        application = analyzer.apply(texts)
        output = _append_topic_outputs(
            pd.concat(frames, ignore_index=True),
            np.arange(len(locations), dtype=int),
            application.distributions,
        )
        if len(frames) > 1:
            output["source_file"] = [item["source_file"] for item in locations]
        output_path = task_dir / "output" / "text_topic_distributions.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output.index),
                input_file_count=len(frames),
                prediction_column_name="dominant_topic",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_topic_apply_facts=application.facts,
        )


class MultilingualTextSimilarityService(ModelServiceBase):
    key = "text.similarity.multilingual_tfidf_cosine"
    display_name = "Multilingual Local Text Retrieval"
    problem_kind = ProblemKind.RETRIEVAL
    evaluation_kind = EvaluationKind.RETRIEVAL
    family = "Similarity retrieval"
    guidance = "Builds a retained local raw-text index with self-excluding Top-K and truth-gated ranking evidence."
    recommendation_tier = 20
    model_family = ModelFamily.TEXT_ANALYSIS
    model_task_kind = ModelTaskKind.RETRIEVER
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = MultilingualTextRetrievalParams
    param_grid_model = None
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table", "metrics", "report"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(name="text", kind=ColumnRoleKind.SINGLE_COLUMN, required=True),
            ModelRoleDefinition(name="document_id", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
            ModelRoleDefinition(name="relevance_group", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(name="text", kind=ColumnRoleKind.SINGLE_COLUMN, required=True),
            ModelRoleDefinition(name="document_id", kind=ColumnRoleKind.SINGLE_COLUMN, required=False),
        ],
        additional_roles=False,
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        params = MultilingualTextRetrievalParams.model_validate(request.manual_training.params)
        preparer = build_text_preparer(_text_preparation_input(request, params))
        dataframe = load_dataset(Path(request.dataset_source_path))
        text_column = _single_role_column(request.train_role_bindings, "text")
        document_id_column = _optional_role_column(request.train_role_bindings, "document_id")
        relevance_group_column = _optional_role_column(request.train_role_bindings, "relevance_group")
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=text_column,
            business_group_column=None,
            preparer=preparer,
            minimum_rows=2,
        )
        document_ids = _eligible_role_values(dataframe, prepared.source_positions, document_id_column)
        relevance_groups = _eligible_role_values(dataframe, prepared.source_positions, relevance_group_column)
        analyzer = MultilingualTextRetriever(
            preparer=preparer,
            max_features=params.max_features,
            top_k=params.top_k,
            minimum_similarity=params.minimum_similarity,
        ).fit(prepared, document_ids=document_ids, relevance_groups=relevance_groups)
        analyzer.text_column = text_column
        analyzer.document_id_column = document_id_column
        analyzer.relevance_group_column = relevance_group_column
        evaluation = analyzer.evaluate(prepared)
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        model_path, final_path, evidence_path, export_path, report_path = _discovery_paths(cls.key, task_dir)
        joblib.dump(analyzer, model_path)
        joblib.dump(analyzer, final_path)
        _write_discovery_evidence(evidence_path, evaluation.facts, snapshot_digest)
        _write_json_report(report_path, evaluation.facts)
        _retrieval_export_frame(analyzer, evaluation.matches).to_csv(export_path, index=False)
        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_path),
            final_model_artifact_path=str(final_path),
            holdout_artifact_path=str(evidence_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(evaluation_model="full_local_index", apply_model="full_local_index"),
            text_preparation_facts=evaluation.facts.preparation,
            text_preparation_specification=evaluation.facts.specification,
            text_vectorization_facts=evaluation.facts.vectorization,
            text_retrieval_evaluation=evaluation.facts,
            result_summary=_retrieval_summary(evaluation.facts),
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer: MultilingualTextRetriever = joblib.load(request.evaluate_model.trained_model_artifact_path)
        dataframe = load_dataset(Path(request.dataset_source_path))
        prepared = prepare_discovery_corpus(
            dataframe,
            text_column=_required_retained_column(analyzer.text_column, "text"),
            business_group_column=None,
            preparer=analyzer.preparer,
            minimum_rows=2,
        )
        _verify_retrieval_source_identities(analyzer, dataframe, prepared.source_positions)
        facts = analyzer.evaluate(prepared).facts
        snapshot_digest = dataset_snapshot_digest(request.dataset_snapshot)
        _verify_discovery_evidence(Path(request.evaluate_model.holdout_artifact_path), facts, snapshot_digest)
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=_retrieval_candidate_metrics(facts),
            text_retrieval_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer: MultilingualTextRetriever = joblib.load(request.apply_model.trained_model_artifact_path)
        text_column = _required_retained_column(analyzer.text_column, "text")
        frames, texts, locations = _load_raw_text_apply_inputs(request, text_column)
        query_ids = _concat_optional_apply_column(frames, analyzer.document_id_column)
        application = analyzer.apply(texts, document_ids=query_ids)
        output_rows = []
        query_frame = pd.concat(frames, ignore_index=True)
        for match in application.matches:
            location = locations[match.query_position]
            output_rows.append(
                {
                    **query_frame.iloc[match.query_position].to_dict(),
                    **location,
                    "matched_document_id": analyzer.matched_document_id(match.matched_document_position),
                    "matched_text": analyzer.matched_document_text(match.matched_document_position),
                    "rank": match.rank,
                    "similarity": match.similarity,
                }
            )
        output_path = task_dir / "output" / "text_similarity_matches.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(output_rows).to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(output_rows),
                input_file_count=len(frames),
                prediction_column_name="matched_document_id",
            ),
            source_dataset_ids=[item.dataset_id for item in request.input_files if item.dataset_id],
            source_artifact_ids=[item.artifact_id for item in request.input_files if item.artifact_id],
            text_retrieval_apply_facts=application.facts,
        )
