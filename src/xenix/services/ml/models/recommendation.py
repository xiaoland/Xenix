from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from ....exceptions import ValidationError
from ..contracts import (
    ApplySummary,
    ApplyTaskRequest,
    ApplyTaskResult,
    CandidateMetrics,
    EvaluateTaskRequest,
    EvaluateTaskResult,
    FitTaskRequest,
    FitTaskResult,
    HyperparameterTuningTaskRequest,
    HyperparameterTuningTaskResult,
    TrainingScopeFacts,
)
from ..dataset_loader import load_dataset
from ..evaluation import build_evaluation_comparison
from ..preparation import dataset_snapshot_digest
from ..recommendation_evidence import (
    RecommendationEngineConfig,
    RecommendationEvaluationContext,
    RecommendationRankingMetrics,
    RetainedRecommendationAnalyzer,
    fit_recommendation_engine,
    recompute_recommendation_evaluation,
)
from ..types import (
    ColumnRoleKind,
    EvaluationKind,
    ModelFamily,
    ModelResultContract,
    ModelRoleDefinition,
    ModelRoleSchema,
    ModelServiceBase,
    ModelTaskKind,
)
from ...storage.models import ProblemKind


class CollaborativeTopKRecommendationParams(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    min_user_interactions: int = Field(default=3, ge=2, le=1000)
    min_item_interactions: int = Field(default=2, ge=1, le=1000)
    positive_rating_threshold: float = Field(default=4.0, ge=-1_000_000, le=1_000_000)


class CollaborativeTopKRecommendationService(ModelServiceBase):
    key = "recommendation.collaborative_top_k"
    display_name = "Collaborative Top-K Recommender"
    problem_kind = ProblemKind.RECOMMENDATION
    evaluation_kind = EvaluationKind.RANKING
    model_family = ModelFamily.RECOMMENDATION
    model_task_kind = ModelTaskKind.RECOMMENDER
    family = "Collaborative filtering"
    guidance = (
        "Produces personalized unseen-item Top-K recommendations and uses deterministic "
        "popularity fallback for cold users."
    )
    recommendation_tier = 10
    requires_target = False
    supports_evaluation = True
    supports_hyperparameter_tuning = False
    params_model = CollaborativeTopKRecommendationParams
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="user",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="User or account identifier column.",
            ),
            ModelRoleDefinition(
                name="item",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Item, product, or content identifier column.",
            ),
            ModelRoleDefinition(
                name="rating",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Numeric explicit-preference rating; larger values mean stronger preference.",
            ),
            ModelRoleDefinition(
                name="time",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=False,
                description=(
                    "Optional interaction timestamp. When bound, evaluation holds out each "
                    "eligible user's latest positive interaction."
                ),
            ),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="user",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description=(
                    "Known or cold user identifier to receive retained Top-K recommendations."
                ),
            )
        ],
        additional_roles=False,
    )
    result_contract = ModelResultContract(
        train_result_kinds=["model", "metrics", "report", "table"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = CollaborativeTopKRecommendationParams.model_validate(
            cls.validate_params(request.manual_training.params)
        )
        user_column = _single_role_column(request.train_role_bindings, "user")
        item_column = _single_role_column(request.train_role_bindings, "item")
        rating_column = _single_role_column(request.train_role_bindings, "rating")
        time_column = _optional_single_role_column(request.train_role_bindings, "time")
        fitted = fit_recommendation_engine(
            dataframe,
            user_column=user_column,
            item_column=item_column,
            rating_column=rating_column,
            time_column=time_column,
            source_dataset_snapshot_digest=dataset_snapshot_digest(request.dataset_snapshot),
            config=_engine_config(params),
        )

        model_dir = task_dir / "models"
        input_dir = task_dir / "input"
        output_dir = task_dir / "output"
        model_dir.mkdir(parents=True, exist_ok=True)
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        evaluation_model_path = model_dir / "collaborative_top_k_evaluation.joblib"
        final_model_path = model_dir / "collaborative_top_k_final.joblib"
        evaluation_context_path = input_dir / "recommendation-evaluation.json"
        export_path = output_dir / "recommendations.csv"
        report_path = output_dir / "recommendation-report.json"
        joblib.dump(fitted.evaluation_analyzer, evaluation_model_path)
        joblib.dump(fitted.final_analyzer, final_model_path)
        fitted.full_recommendations.to_csv(export_path, index=False)
        evaluation_context_path.write_text(
            fitted.evaluation_context.model_dump_json(indent=2),
            encoding="utf-8",
        )
        report_path.write_text(fitted.facts.model_dump_json(indent=2), encoding="utf-8")

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(evaluation_model_path),
            final_model_artifact_path=str(final_model_path),
            holdout_artifact_path=str(evaluation_context_path),
            export_artifact_path=str(export_path),
            report_artifact_path=str(report_path),
            training_scopes=TrainingScopeFacts(
                evaluation_model="per_user_holdout_training_interactions",
                apply_model="all_admitted_interactions",
            ),
            recommendation_split_facts=fitted.facts.split,
            recommendation_preparation_facts=fitted.facts.preparation,
            result_summary={
                "recommendation_count": int(len(fitted.full_recommendations)),
                "user_count": fitted.facts.preparation.user_count,
                "candidate_item_count": fitted.facts.preparation.candidate_item_count,
                "recommendation_evaluation": fitted.facts.model_dump(mode="json"),
            },
        )

    @classmethod
    def tune(
        cls,
        request: HyperparameterTuningTaskRequest,
        task_dir: Path,
    ) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        analyzer = joblib.load(request.evaluate_model.trained_model_artifact_path)
        if not isinstance(analyzer, RetainedRecommendationAnalyzer):
            raise ValidationError("The evaluation artifact is not a retained Top-K recommender.")
        context = RecommendationEvaluationContext.model_validate_json(
            Path(request.evaluate_model.holdout_artifact_path).read_text(encoding="utf-8")
        )
        try:
            facts = recompute_recommendation_evaluation(analyzer, context)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        candidate = _ranking_candidate_metrics(facts.candidate)
        baseline = _ranking_candidate_metrics(facts.baseline)
        return EvaluateTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            trained_model_id=request.evaluate_model.trained_model_id,
            model_key=cls.key,
            evaluation=candidate,
            baseline_evaluation=baseline,
            comparison=build_evaluation_comparison(
                request.evaluation_policy,
                candidate,
                baseline,
            ),
            recommendation_evaluation=facts,
        )

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        analyzer = joblib.load(request.apply_model.trained_model_artifact_path)
        if not isinstance(analyzer, RetainedRecommendationAnalyzer):
            raise ValidationError("The selected artifact is not a retained Top-K recommender.")

        result_frames: list[pd.DataFrame] = []
        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if analyzer.user_column not in dataframe.columns:
                raise ValidationError(
                    f"Apply input '{input_file.file_name}' is missing required column: "
                    f"{analyzer.user_column}."
                )
            rows: list[dict[str, Any]] = []
            for row_number, user in enumerate(dataframe[analyzer.user_column], start=1):
                recommendations = analyzer.recommend_users([user])
                for recommendation in recommendations.to_dict(orient="records"):
                    rows.append(
                        {
                            "source_file": input_file.file_name,
                            "input_row_number": row_number,
                            **recommendation,
                        }
                    )
            result_frames.append(
                pd.DataFrame(
                    rows,
                    columns=[
                        "source_file",
                        "input_row_number",
                        "user_id",
                        "rank",
                        "recommended_item",
                        "score",
                        "strategy",
                    ],
                )
            )

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "recommendations.csv"
        combined = (
            pd.concat(result_frames, ignore_index=True)
            if result_frames
            else pd.DataFrame(
                columns=[
                    "source_file",
                    "input_row_number",
                    "user_id",
                    "rank",
                    "recommended_item",
                    "score",
                    "strategy",
                ]
            )
        )
        combined.to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(combined),
                input_file_count=len(request.input_files),
                prediction_column_name="recommended_item",
            ),
            source_dataset_ids=[
                input_file.dataset_id
                for input_file in request.input_files
                if input_file.dataset_id is not None
            ],
            source_artifact_ids=[
                input_file.artifact_id
                for input_file in request.input_files
                if input_file.artifact_id is not None
            ],
        )


class ItemSimilarityRecommendationParams(BaseModel):
    min_ratings_base: int = Field(default=20, ge=1, le=100000)
    min_ratings_candidate: int = Field(default=20, ge=1, le=100000)
    similarity_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=100)


class ItemSimilarityRecommendationService(ModelServiceBase):
    key = "recommendation.item_similarity"
    display_name = "Item Similarity Recommender"
    evaluation_kind = EvaluationKind.SUMMARY
    model_family = ModelFamily.RECOMMENDATION
    model_task_kind = ModelTaskKind.RECOMMENDER
    family = "Collaborative filtering"
    guidance = "Recommends similar items from shared user ratings using Euclidean similarity."
    recommendation_tier = 35
    requires_target = False
    supports_hyperparameter_tuning = False
    params_model = ItemSimilarityRecommendationParams
    train_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="user",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="User or account identifier column.",
            ),
            ModelRoleDefinition(
                name="item",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Item, product, or content identifier column.",
            ),
            ModelRoleDefinition(
                name="rating",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Numeric preference or rating column.",
            ),
        ],
        additional_roles=False,
    )
    apply_role_schema = ModelRoleSchema(
        roles=[
            ModelRoleDefinition(
                name="item",
                kind=ColumnRoleKind.SINGLE_COLUMN,
                required=True,
                description="Base item column used to look up recommendations.",
            )
        ],
        additional_roles=False,
    )
    result_contract = ModelResultContract(
        train_result_kinds=["model", "table"],
        apply_result_kinds=["table"],
        preview_kinds=["model", "table", "file"],
    )

    @classmethod
    def fit(cls, request: FitTaskRequest, task_dir: Path) -> FitTaskResult:
        dataframe = load_dataset(Path(request.dataset_source_path))
        params = cls.validate_params(request.manual_training.params)
        user_column = _single_role_column(request.train_role_bindings, "user")
        item_column = _single_role_column(request.train_role_bindings, "item")
        rating_column = _single_role_column(request.train_role_bindings, "rating")
        recommendations = _build_recommendations(
            dataframe,
            user_column=user_column,
            item_column=item_column,
            rating_column=rating_column,
            params=ItemSimilarityRecommendationParams.model_validate(params),
        )

        model_artifact_path = task_dir / "models" / f"{cls.key.replace('.', '_')}.joblib"
        export_artifact_path = task_dir / "output" / "item_recommendations.csv"
        model_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        export_artifact_path.parent.mkdir(parents=True, exist_ok=True)
        recommendations.to_csv(export_artifact_path, index=False)
        joblib.dump(
            {
                "model_key": cls.key,
                "user_column": user_column,
                "item_column": item_column,
                "rating_column": rating_column,
                "params": params.model_dump(mode="json"),
                "recommendations": recommendations.to_dict(orient="records"),
            },
            model_artifact_path,
        )

        return FitTaskResult(
            task_id=request.task_id,
            evaluation_kind=request.evaluation_kind,
            evaluation_policy=request.evaluation_policy,
            model_key=cls.key,
            params=params.model_dump(mode="json"),
            model_artifact_path=str(model_artifact_path),
            export_artifact_path=str(export_artifact_path),
            result_summary={
                "result_count": int(len(recommendations.index)),
                "recommendation_count": int(len(recommendations.index)),
                "unique_user_count": int(dataframe[user_column].nunique(dropna=True)),
                "unique_item_count": int(dataframe[item_column].nunique(dropna=True)),
            },
        )

    @classmethod
    def tune(cls, request: HyperparameterTuningTaskRequest, task_dir: Path) -> HyperparameterTuningTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support hyperparameter tuning.")

    @classmethod
    def evaluate(cls, request: EvaluateTaskRequest, task_dir: Path) -> EvaluateTaskResult:
        raise ValidationError(f"Model '{cls.key}' does not support evaluation.")

    @classmethod
    def apply(cls, request: ApplyTaskRequest, task_dir: Path) -> ApplyTaskResult:
        artifact = joblib.load(request.apply_model.trained_model_artifact_path)
        item_column = str(artifact.get("item_column") or (request.feature_columns[0] if request.feature_columns else ""))
        recommendations = [dict(row) for row in artifact.get("recommendations") or []]
        result_rows: list[dict[str, Any]] = []

        for input_file in request.input_files:
            dataframe = load_dataset(Path(input_file.absolute_path))
            if item_column not in dataframe.columns:
                raise ValidationError(f"Apply input '{input_file.file_name}' is missing required column: {item_column}.")
            for row_index, value in enumerate(dataframe[item_column].tolist(), start=1):
                if pd.isna(value):
                    continue
                base_item = str(value).strip()
                if not base_item:
                    continue
                matches = [
                    row
                    for row in recommendations
                    if str(row.get("base_item") or "") == base_item
                ]
                for match in matches:
                    result_rows.append(
                        {
                            "source_file": input_file.file_name,
                            "input_row_number": row_index,
                            "base_item": base_item,
                            "rank": int(match.get("rank") or 0),
                            "recommended_item": str(match.get("recommended_item") or ""),
                            "similarity": float(match.get("similarity") or 0.0),
                            "common_user_count": int(match.get("common_user_count") or 0),
                        }
                    )

        output_dir = task_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "item_recommendations.csv"
        pd.DataFrame(
            result_rows,
            columns=[
                "source_file",
                "input_row_number",
                "base_item",
                "rank",
                "recommended_item",
                "similarity",
                "common_user_count",
            ],
        ).to_csv(output_path, index=False)
        return ApplyTaskResult(
            task_id=request.task_id,
            trained_model_id=request.apply_model.trained_model_id,
            model_key=cls.key,
            output_file_path=str(output_path),
            summary=ApplySummary(
                row_count=len(result_rows),
                input_file_count=len(request.input_files),
                prediction_column_name="recommended_item",
            ),
        )


def _single_role_column(role_bindings: list[dict[str, Any]], role: str) -> str:
    for binding in role_bindings:
        if binding.get("role") == role and isinstance(binding.get("columns"), list):
            columns = [str(column) for column in binding["columns"]]
            if len(columns) == 1:
                return columns[0]
    raise ValidationError(f"Recommendation model requires exactly one '{role}' column.")


def _optional_single_role_column(
    role_bindings: list[dict[str, Any]],
    role: str,
) -> str | None:
    for binding in role_bindings:
        if binding.get("role") != role:
            continue
        columns = binding.get("columns")
        if isinstance(columns, list) and len(columns) == 1:
            return str(columns[0])
        raise ValidationError(f"Recommendation role '{role}' requires exactly one column.")
    return None


def _engine_config(
    params: CollaborativeTopKRecommendationParams,
) -> RecommendationEngineConfig:
    return RecommendationEngineConfig(
        top_k=params.top_k,
        min_user_interactions=params.min_user_interactions,
        min_item_interactions=params.min_item_interactions,
        positive_rating_threshold=params.positive_rating_threshold,
    )


def _ranking_candidate_metrics(facts: RecommendationRankingMetrics) -> CandidateMetrics:
    metrics = {
        key: value
        for key, value in {
            "ndcg_at_k": facts.ndcg_at_k,
            "recall_at_k": facts.recall_at_k,
            "hit_rate_at_k": facts.hit_rate_at_k,
            "mrr_at_k": facts.mrr_at_k,
            "catalog_coverage_at_k": facts.catalog_coverage_at_k,
            "mean_novelty_at_k": facts.mean_novelty_at_k,
            "mean_intra_list_diversity_at_k": facts.mean_intra_list_diversity_at_k,
        }.items()
        if value is not None
    }
    if facts.ndcg_at_k is None:
        raise ValidationError("Recommendation evaluation has no eligible ranking truth.")
    return CandidateMetrics(
        primary_metric_name="ndcg_at_k",
        primary_metric_value=facts.ndcg_at_k,
        metrics=metrics,
        details={
            "ranking_digest": facts.ranking_digest,
            "seen_item_violation_count": facts.seen_item_violation_count,
            "evaluated_user_count": facts.evaluated_user_count,
            "short_list_user_count": facts.short_list_user_count,
        },
    )


def _build_recommendations(
    dataframe: pd.DataFrame,
    *,
    user_column: str,
    item_column: str,
    rating_column: str,
    params: ItemSimilarityRecommendationParams,
) -> pd.DataFrame:
    for column in (user_column, item_column, rating_column):
        if column not in dataframe.columns:
            raise ValidationError(f"Recommendation column is missing: {column}.")

    working = dataframe.loc[:, [user_column, item_column, rating_column]].copy()
    working[rating_column] = pd.to_numeric(working[rating_column], errors="coerce")
    working = working.dropna(subset=[user_column, item_column, rating_column])
    if working.empty:
        raise ValidationError("Recommendation model requires at least one valid user-item-rating row.")

    rating_pivot = working.pivot_table(
        index=user_column,
        columns=item_column,
        values=rating_column,
        aggfunc="mean",
    )
    item_rating_counts = working.groupby(item_column)[rating_column].count()
    item_values = rating_pivot.columns.tolist()
    item_labels = [str(item) for item in item_values]
    item_to_index = {item: index for index, item in enumerate(item_labels)}
    counts_by_label = {
        str(item): int(item_rating_counts[item])
        for item in item_values
    }
    base_items = [
        str(item)
        for item in item_values
        if item_rating_counts[item] >= params.min_ratings_base
    ]
    candidate_items = [
        str(item)
        for item in item_values
        if item_rating_counts[item] >= params.min_ratings_candidate
    ]

    ratings = rating_pivot.to_numpy(dtype=float)
    present = ~np.isnan(ratings)
    rows: list[dict[str, Any]] = []
    for base_item in base_items:
        base_index = item_to_index[base_item]
        base_ratings = ratings[:, base_index]
        base_present = present[:, base_index]
        candidates: list[tuple[str, float, int]] = []
        for candidate_item in candidate_items:
            if candidate_item == base_item:
                continue
            candidate_index = item_to_index[candidate_item]
            candidate_present = present[:, candidate_index]
            common_mask = base_present & candidate_present
            common_count = int(common_mask.sum())
            if common_count == 0:
                continue
            diff = base_ratings[common_mask] - ratings[common_mask, candidate_index]
            distance = float(np.sqrt(np.sum(diff * diff)))
            similarity = 1.0 / (1.0 + distance)
            if similarity >= params.similarity_threshold:
                candidates.append((candidate_item, similarity, common_count))

        candidates.sort(key=lambda item: (-item[1], -item[2], item[0]))
        for rank, (recommended_item, similarity, common_count) in enumerate(candidates[: params.top_k], start=1):
            rows.append(
                {
                    "base_item": base_item,
                    "base_rating_count": counts_by_label[base_item],
                    "rank": rank,
                    "recommended_item": recommended_item,
                    "similarity": similarity,
                    "common_user_count": common_count,
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "base_item",
            "base_rating_count",
            "rank",
            "recommended_item",
            "similarity",
            "common_user_count",
        ],
    )
