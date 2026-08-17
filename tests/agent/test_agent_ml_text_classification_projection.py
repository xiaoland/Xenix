from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import Mock

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


ACTIVE_MODEL_KEY = "text.classification.multilingual_logistic_regression_tfidf"
LEGACY_MODEL_KEY = "text.classification.logistic_regression_tfidf"
PARAMETER_NAMES = {
    "preparation_profile",
    "phrase_mode",
    "max_features",
    "minimum_document_frequency",
    "class_weight",
    "custom_dictionary_dataset_ids",
    "stopword_dataset_ids",
}
PRIVATE_LABELS = ("rt-t1-private-priority", "rt-t1-private-standard")
PRIVATE_CUSTOM_TERMS = ("AetherDesk", "龙鳞协议")
PRIVATE_STOPWORDS = ("privatefiller", "冗词")
PRIVATE_THEME_TOKENS = (
    ("orionalpha", "cobaltbravo", "maplecharlie"),
    ("juniperdelta", "saffronecho", "indigofalcon"),
    ("willowgamma", "amberhotel", "cedarindia"),
    ("silverjuliet", "coralkilo", "birchlim a".replace(" ", "")),
    ("violetmike", "cypressnovember", "scarletoscar"),
    ("tealpap a".replace(" ", ""), "mahoganyquebec", "ivoryromeo"),
)


class _InlineWorkerRunner:
    max_dispatch_threads = 1

    def run(
        self,
        entrypoint: Any,
        task_dir: Path,
        *,
        cancel_requested: Any | None = None,
    ) -> int:
        if cancel_requested is not None and cancel_requested():
            return -15
        entrypoint(str(task_dir))
        return 0


def _write_independent_clean_room_sources(tmp_path: Path) -> tuple[Path, Path, Path, Path, pd.DataFrame]:
    rows: list[dict[str, str]] = []
    for component_index, theme_tokens in enumerate(PRIVATE_THEME_TOKENS):
        theme = " ".join(theme_tokens)
        for entity_side in range(2):
            entity = f"rt-t1-private-entity-{component_index}-{entity_side}"
            number_base = 1000 + component_index * 100 + entity_side * 10
            rows.extend(
                [
                    {
                        "message": (
                            f"RT_T1_PRIVATE_RAW {PRIVATE_CUSTOM_TERMS[0]} {PRIVATE_CUSTOM_TERMS[1]} {theme} "
                            f"case {number_base + 1} resolved promptly {PRIVATE_STOPWORDS[0]} {PRIVATE_STOPWORDS[1]}"
                        ),
                        "outcome": PRIVATE_LABELS[0],
                        "business_entity": entity,
                    },
                    {
                        "message": (
                            f"RT_T1_PRIVATE_RAW {PRIVATE_CUSTOM_TERMS[0]} {PRIVATE_CUSTOM_TERMS[1]} {theme} "
                            f"case {number_base + 2} failed critically {PRIVATE_STOPWORDS[0]} {PRIVATE_STOPWORDS[1]}"
                        ),
                        "outcome": PRIVATE_LABELS[1],
                        "business_entity": entity,
                    },
                ]
            )

    source_dir = tmp_path / "independent-agent-text-inputs"
    source_dir.mkdir()
    training_path = source_dir / "agent_text_training.csv"
    apply_path = source_dir / "agent_text_apply.csv"
    dictionary_path = source_dir / "agent_text_dictionary.csv"
    stopwords_path = source_dir / "agent_text_stopwords.csv"
    training = pd.DataFrame(rows)
    training.to_csv(training_path, index=False)
    pd.DataFrame(
        {
            "message": [
                "RT_T1_PRIVATE_APPLY AetherDesk orionalpha resolved promptly",
                "RT_T1_PRIVATE_APPLY 龙鳞协议 juniperdelta failed critically",
                "quantumonlyword xylophonic",
                "",
            ]
        }
    ).to_csv(apply_path, index=False)
    pd.DataFrame({"term": list(PRIVATE_CUSTOM_TERMS)}).to_csv(dictionary_path, index=False)
    pd.DataFrame({"term": list(PRIVATE_STOPWORDS)}).to_csv(stopwords_path, index=False)
    return training_path, apply_path, dictionary_path, stopwords_path, training


def _xtt_metadata_value(payload: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s+(.+)$", payload)
    if match is None:
        raise AssertionError(f"Xenix Table Text omitted {key!r}: {payload}")
    return match.group(1).strip().strip('"')


def test_agent_text_classification_projection_is_authoritative_private_and_lineage_truthful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    training_path, apply_path, dictionary_path, stopwords_path, private_training = (
        _write_independent_clean_room_sources(tmp_path)
    )
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    task_service = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=_InlineWorkerRunner(),
    )
    ml = MLService(paths, storage.session_factory, datasets, task_service)
    artifacts = ArtifactService(storage.session_factory)
    tools = AgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=Mock(),
        data_transform_service=Mock(),
        ml_service=ml,
        artifact_service=artifacts,
    )

    try:
        training_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(training_path.resolve()),
                name="Independent grouped raw text",
            )
        )
        apply_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(apply_path.resolve()),
                project_id=training_dataset.project_id,
                name="Independent raw text apply batch",
            )
        )
        dictionary_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(dictionary_path.resolve()),
                project_id=training_dataset.project_id,
                name="Registered custom dictionary",
            )
        )
        stopword_dataset = datasets.register_dataset(
            RegisterDatasetInput(
                source_path=str(stopwords_path.resolve()),
                project_id=training_dataset.project_id,
                name="Registered stopword list",
            )
        )
        context = ToolExecutionContext(
            thread_id="agent-text-classification-projection",
            dataset_ids=(
                training_dataset.id,
                apply_dataset.id,
                dictionary_dataset.id,
                stopword_dataset.id,
            ),
        )

        tokenized_projection = tools.execute(
            "data.tokenize",
            {
                "dataset_id": training_dataset.id,
                "name": "Independent multilingual token inspection",
                "text_column": "message",
                "output": "token_text",
                "tokenizer_profile": "multilingual_business_v1",
                "phrase_mode": "unigram_bigram",
                "custom_dictionary_dataset_ids": [dictionary_dataset.id],
                "stopword_dataset_ids": [stopword_dataset.id],
            },
            context,
        ).value
        assert isinstance(tokenized_projection, str)
        tokenized_dataset_id = _xtt_metadata_value(tokenized_projection, "dataset_id")
        tokenized_artifact_id = _xtt_metadata_value(tokenized_projection, "artifact_id")
        tokenized_dataset = datasets.get_dataset(tokenized_dataset_id)
        assert tokenized_dataset.derived_from_dataset_id == training_dataset.id
        tokenized_artifact = artifacts.resolve_uri(build_artifact_uri(tokenized_artifact_id))
        tokenization_report = tokenized_artifact.metadata_payload["tokenization_report"]
        tokenization_specification = tokenization_report["preparation_specification"]
        assert tokenization_specification["profile_key"] == "multilingual_business_v1"
        assert tokenization_specification["phrase_mode"] == "unigram_bigram"
        assert tokenization_specification["custom_dictionary_references"][0]["dataset_id"] == (
            dictionary_dataset.id
        )
        assert tokenization_specification["stopword_references"][0]["dataset_id"] == stopword_dataset.id
        assert tokenization_report["preparation_quality"]["source_row_count"] == len(private_training.index)
        assert tokenized_artifact.exists is True
        assert tokenized_artifact.metadata_payload["dataset_id"] == tokenized_dataset.id

        family_metadata = tools.execute(
            "model.metadata",
            {"model_family": "text_analysis"},
            context,
        ).value
        assert ACTIVE_MODEL_KEY in family_metadata["model_keys"]
        assert LEGACY_MODEL_KEY in family_metadata["model_keys"]
        assert all("param_schema" not in model for model in family_metadata["models"])
        family_models = {model["model_key"]: model for model in family_metadata["models"]}
        assert family_models[ACTIVE_MODEL_KEY]["supports_hyperparameter_tuning"] is False
        assert family_models[LEGACY_MODEL_KEY]["supports_hyperparameter_tuning"] is True

        active_metadata = tools.execute(
            "model.metadata",
            {"model_key": ACTIVE_MODEL_KEY},
            context,
        ).value
        active_detail = active_metadata["models"][0]
        assert active_metadata["model_keys"] == [ACTIVE_MODEL_KEY]
        assert active_detail["model_family"] == "text_analysis"
        assert active_detail["model_task_kind"] == "predictor"
        assert active_detail["evaluation_kind"] == "classification"
        assert active_detail["supports_evaluation"] is True
        assert active_detail["supports_apply"] is True
        assert active_detail["apply_mode"] == "rows"
        assert active_detail["supports_hyperparameter_tuning"] is False
        assert active_detail["result_contract"] == {
            "train_result_kinds": ["model", "metrics", "report"],
            "apply_result_kinds": ["table"],
            "preview_kinds": ["model", "table", "file"],
        }
        active_schema = active_detail["param_schema"]
        assert set(active_schema["properties"]) == PARAMETER_NAMES
        assert len(active_schema["properties"]) == 7
        for field_name in ("custom_dictionary_dataset_ids", "stopword_dataset_ids"):
            assert active_schema["properties"][field_name]["type"] == "array"
            assert active_schema["properties"][field_name]["maxItems"] == 4
            assert active_schema["properties"][field_name]["items"]["type"] == "string"
        assert all(
            "properties" not in field_schema
            for field_schema in active_schema["properties"].values()
        )

        legacy_metadata = tools.execute(
            "model.metadata",
            {"model_key": LEGACY_MODEL_KEY},
            context,
        ).value
        legacy_detail = legacy_metadata["models"][0]
        assert legacy_metadata["model_keys"] == [LEGACY_MODEL_KEY]
        assert legacy_detail["supports_hyperparameter_tuning"] is True
        assert set(legacy_detail["param_schema"]["properties"]) == {
            "max_features",
            "ngram_max",
            "c",
            "max_iter",
        }
        assert "Pre-tokenized" in legacy_detail["train_role_schema"]["roles"][0]["description"]
        assert "Raw business text" in active_detail["train_role_schema"]["roles"][0]["description"]

        binding = tools.execute(
            "data.feature.select",
            {
                "dataset_id": training_dataset.id,
                "model_key": ACTIVE_MODEL_KEY,
                "role_bindings": [
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["outcome"]},
                    {"role": "group", "columns": ["business_entity"]},
                ],
            },
            context,
        ).value
        assert binding["dataset_id"] == training_dataset.id
        assert binding["model_key"] == ACTIVE_MODEL_KEY
        assert binding["model_family"] == "text_analysis"

        params = {
            "preparation_profile": "multilingual_business_v1",
            "phrase_mode": "unigram_bigram",
            "max_features": 400,
            "minimum_document_frequency": 1,
            "class_weight": "balanced",
            "custom_dictionary_dataset_ids": [dictionary_dataset.id],
            "stopword_dataset_ids": [stopword_dataset.id],
        }
        training = tools.execute(
            "model.train",
            {
                "binding_id": binding["binding_id"],
                "models": [ACTIVE_MODEL_KEY],
                "params_by_model": {ACTIVE_MODEL_KEY: params},
                "run_name": "Independent grouped multilingual classification",
            },
            context,
        ).value
        assert training["async_state"] == "completed"
        trained_model = training["trained_models"][0]
        assert trained_model["model_key"] == ACTIVE_MODEL_KEY
        assert trained_model["dataset_id"] == training_dataset.id
        assert trained_model["evaluation_kind"] == "classification"
        assert trained_model["training_scope"] == {
            "evaluation_model": "holdout_train_split",
            "apply_model": "all_eligible_rows",
        }
        assert trained_model["evaluation_facts_authority"] == "ml_task_result"

        query = tools.execute(
            "model.task.query",
            {"task_ids": training["task_ids"]},
            context,
        ).value
        fit_task = next(task for task in query["tasks"] if task["task_type"] == "fit")
        evaluation_task = next(task for task in query["tasks"] if task["task_type"] == "evaluate")
        fit_result = fit_task["result"]
        specification = fit_result["text_preparation_specification"]
        preparation = fit_result["text_preparation_facts"]
        leakage = fit_result["text_leakage_facts"]
        vectorization = fit_result["text_vectorization_facts"]
        split = fit_result["split_facts"]
        assert specification["profile_key"] == "multilingual_business_v1"
        assert specification["phrase_mode"] == "unigram_bigram"
        assert specification["custom_dictionary_references"][0]["dataset_id"] == dictionary_dataset.id
        assert specification["custom_dictionary_references"][0]["term_count"] == len(PRIVATE_CUSTOM_TERMS)
        assert specification["stopword_references"][0]["dataset_id"] == stopword_dataset.id
        assert specification["stopword_references"][0]["term_count"] == len(PRIVATE_STOPWORDS)
        assert preparation["source_row_count"] == len(private_training.index)
        assert preparation["eligible_row_count"] == len(private_training.index)
        assert preparation["custom_dictionary_term_count"] == len(PRIVATE_CUSTOM_TERMS)
        assert preparation["custom_term_match_count"] == len(private_training.index) * len(PRIVATE_CUSTOM_TERMS)
        assert preparation["collapsed_exact_duplicate_row_count"] > 0
        assert preparation["collapsed_template_duplicate_row_count"] > 0
        assert leakage["business_group_count"] == 12
        assert leakage["connected_group_count"] == 6
        assert leakage["train_business_group_overlap_count"] == 0
        assert leakage["train_template_group_overlap_count"] == 0
        assert leakage["train_connected_group_overlap_count"] == 0
        assert split["realized_strategy"] == "group_hash_holdout.v1"
        assert split["group_overlap_count"] == 0
        assert vectorization["fit_row_count"] == split["train_row_count"]
        assert len(vectorization["vocabulary_digest"]) == 64
        assert fit_result["training_scope"] == {
            "evaluation_model": "holdout_train_split",
            "apply_model": "all_eligible_rows",
        }
        assert fit_result["result_dataset_id"] is None

        evaluation = evaluation_task["result"]
        text_evaluation = evaluation["text_classification_evaluation"]
        primary_metric = evaluation["evaluation"]["primary_metric_name"]
        assert primary_metric == "f1_weighted"
        assert evaluation["baseline_evaluation"]["primary_metric_name"] == primary_metric
        assert evaluation["comparison"]["primary_metric_name"] == primary_metric
        assert evaluation["comparison"]["verdict"] in {
            "candidate_better",
            "baseline_better",
            "tied",
        }
        assert text_evaluation["specification"] == specification
        assert text_evaluation["preparation"] == preparation
        assert text_evaluation["leakage"] == leakage
        assert text_evaluation["leakage"]["train_connected_group_overlap_count"] == 0
        assert text_evaluation["vectorization"]["fit_row_count"] == split["train_row_count"]
        assert text_evaluation["vectorization"]["inspected_row_count"] == split["holdout_row_count"]
        assert len(text_evaluation["prediction_digest"]) == 64
        assert evaluation["evaluation"]["prediction_digest"] == text_evaluation["prediction_digest"]
        assert evaluation["baseline_evaluation"]["prediction_digest"] != text_evaluation["prediction_digest"]

        applied = tools.execute(
            "model.apply",
            {
                "trained_model_id": trained_model["trained_model_id"],
                "input_sources": [apply_dataset.id],
            },
            context,
        ).value
        assert applied["async_state"] == "completed"
        assert applied["model_key"] == ACTIVE_MODEL_KEY
        assert applied["apply_input_contract"] == "raw_text"
        assert applied["training_dataset_id"] == training_dataset.id
        assert applied["source_dataset_ids"] == [apply_dataset.id]
        assert applied["source_artifact_ids"] == []
        assert applied["result_dataset_id"]
        assert applied["artifact_id"]
        result_dataset = datasets.get_dataset(applied["result_dataset_id"])
        assert result_dataset.derived_from_dataset_id == apply_dataset.id
        assert result_dataset.ml_task_id == applied["ml_task_id"]
        resolved_apply = artifacts.resolve_uri(build_artifact_uri(applied["artifact_id"]))
        assert resolved_apply.exists is True
        assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
        assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
        assert resolved_apply.metadata_payload["source_artifact_ids"] == []
        assert resolved_apply.metadata_payload["result_dataset_id"] == result_dataset.id

        apply_query = tools.execute(
            "model.task.query",
            {"task_ids": [applied["ml_task_id"]]},
            context,
        ).value["tasks"][0]
        apply_facts = apply_query["result"]["text_classification_apply_facts"]
        assert applied["text_classification_apply_facts"] == apply_facts
        assert apply_query["request"]["input_sources"] == [
            {"source_kind": "user_file", "dataset_id": apply_dataset.id}
        ]
        assert apply_query["result"]["source_dataset_ids"] == [apply_dataset.id]
        assert apply_query["result"]["result_dataset_id"] == result_dataset.id
        assert apply_facts["specification"] == specification
        assert apply_facts["preparation"]["source_row_count"] == 4
        assert apply_facts["preparation"]["empty_after_preparation_row_count"] == 1
        assert apply_facts["vectorization"]["fit_row_count"] == len(private_training.index)
        assert apply_facts["vectorization"]["inspected_row_count"] == 4
        assert apply_facts["vectorization"]["out_of_vocabulary_row_count"] >= 1
        assert len(apply_facts["prediction_digest"]) == 64

        provider_projection = json.dumps(
            {
                "family_metadata": family_metadata,
                "tokenized_projection": tokenized_projection,
                "active_metadata": active_metadata,
                "legacy_metadata": legacy_metadata,
                "binding": binding,
                "training": training,
                "query": query,
                "applied": applied,
                "apply_query": apply_query,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        forbidden_values = [
            str(paths.home),
            str(tmp_path),
            "absolute_path",
            "source_path",
            "artifact_path",
            "preview_rows",
            "raw_rows",
            *PRIVATE_LABELS,
            *PRIVATE_CUSTOM_TERMS,
            *PRIVATE_STOPWORDS,
            *private_training["business_entity"].astype(str).tolist(),
            *private_training["message"].astype(str).tolist(),
            *(token for theme in PRIVATE_THEME_TOKENS for token in theme),
            "quantumonlyword",
            "xylophonic",
        ]
        for forbidden in forbidden_values:
            assert forbidden not in provider_projection
    finally:
        storage.engine.dispose()
