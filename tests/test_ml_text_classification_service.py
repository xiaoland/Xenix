from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from time import monotonic, sleep
import unicodedata
from typing import Any, Iterable

import jieba
import numpy as np
import pandas as pd
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.artifact_service import ArtifactService, build_artifact_uri
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml.contracts import EvaluateTaskResult, FitTaskResult
from xenix.services.ml.registry import get_model_catalog_entry
from xenix.services.ml_service import (
    ApplySourceInput,
    ApplyWithFilesInput,
    CreateColumnBindingInput,
    FitWithEvaluateInput,
    MLService,
)
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskArtifactKind, MLTaskStatus, ProjectRow
from xenix.services.trained_model_metadata import parse_trained_model_metadata


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ml_text_classification"
TRAINING_FIXTURE = FIXTURE_ROOT / "bilingual_raw_training_v1.csv"
APPLY_FIXTURE = FIXTURE_ROOT / "bilingual_raw_apply_v1.csv"
CUSTOM_DICTIONARY_FIXTURE = FIXTURE_ROOT / "custom_dictionary_v1.csv"
STOPWORDS_FIXTURE = FIXTURE_ROOT / "stopwords_v1.csv"
FIXTURE_SHA256 = {
    TRAINING_FIXTURE.name: "cca65179f6f5034338a882c77a55fa2df76c4c333111c164bb310aae1826ef22",
    APPLY_FIXTURE.name: "7083e373c4565cb4a82bd451e03cf2cfd96a8e5abfa81a283f23c291da366c7d",
    CUSTOM_DICTIONARY_FIXTURE.name: (
        "0a378ab4d45b3eb5c331a540d2d0f9e3136f04ccd940618a9fa671942b2a8bd6"
    ),
    STOPWORDS_FIXTURE.name: (
        "2f0d23fe17413e4c47674d7e224f8653a290dcaa6338a83da81408c91265053e"
    ),
}
NEAR_DUPLICATE_RECORD_PAIRS = (
    ("p01-02", "p02-02"),
    ("p03-02", "p04-02"),
    ("p05-02", "p06-02"),
    ("s01-02", "s02-02"),
    ("s03-02", "s04-02"),
    ("s05-02", "s06-02"),
)
ACTIVE_MODEL_KEY = "text.classification.multilingual_logistic_regression_tfidf"
PARAMS_TEMPLATE = {
    "preparation_profile": "multilingual_business_v1",
    "phrase_mode": "unigram_bigram",
    "max_features": 5000,
    "minimum_document_frequency": 1,
    "class_weight": "balanced",
}

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_EMAIL_RE = re.compile(r"(?i)\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?![\w])")
_TOKEN_RE = re.compile(r"<url>|<email>|<number>|[\u3400-\u9fff]+|[a-z]+(?:['-][a-z]+)*")
_TEMPLATE_TOKEN_RE = re.compile(r"<url>|<email>|<number>|[\u3400-\u9fff]+|[a-z]+")
_BASE_STOPWORDS = frozenset(
    {
        "的",
        "了",
        "是",
        "也",
        "很",
        "比较",
        "有点",
        "没有",
        "这家",
        "这次",
        "整体",
        "感觉",
        "一个",
        "一下",
        "还是",
        "但是",
        "不过",
        "非常",
        "不太",
        "中规中矩",
        "特别",
        "正常",
        "适合",
        "明显",
        "问题",
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)


@dataclass(frozen=True)
class _ClassificationMetrics:
    accuracy: float
    balanced_accuracy: float
    precision_macro: float
    precision_weighted: float
    recall_macro: float
    recall_weighted: float
    f1_macro: float
    f1_weighted: float


@dataclass
class _Runtime:
    storage: Any
    datasets: DatasetService
    tasks: MLTaskService
    ml: MLService
    artifacts: ArtifactService


@dataclass(frozen=True)
class _TextOracle:
    specification: dict[str, Any]
    preparation: dict[str, Any]
    leakage: dict[str, Any]
    vectorization: dict[str, Any]
    split: dict[str, Any]
    train_positions: np.ndarray
    holdout_positions: np.ndarray
    labels: pd.Series
    predictions: np.ndarray
    probabilities: np.ndarray
    candidate_metrics: _ClassificationMetrics
    baseline_predictions: list[str]
    baseline_metrics: _ClassificationMetrics
    vectorizer: TfidfVectorizer
    model: LogisticRegression
    custom_terms: tuple[str, ...]
    stopword_terms: tuple[str, ...]


@dataclass(frozen=True)
class _PreparedTextOracle:
    prepared_texts: pd.Series
    normalized_texts: pd.Series
    exact_fingerprints: pd.Series
    template_fingerprints: pd.Series
    token_sets: tuple[frozenset[str], ...]
    quality: dict[str, Any]


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


class _TamperingInlineWorkerRunner(_InlineWorkerRunner):
    target_path: Path | None = None

    def run(
        self,
        entrypoint: Any,
        task_dir: Path,
        *,
        cancel_requested: Any | None = None,
    ) -> int:
        if self.target_path is not None:
            self.target_path.write_text("term\ntampered-after-staging\n", encoding="utf-8")
            self.target_path = None
        return super().run(
            entrypoint,
            task_dir,
            cancel_requested=cancel_requested,
        )


class _DisjointSet:
    def __init__(self, values: Iterable[str]) -> None:
        self._parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        self._parent[max(left_root, right_root)] = min(left_root, right_root)


def _runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    worker_runner: Any | None = None,
) -> _Runtime:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    storage = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(storage.session_factory, paths)
    tasks = MLTaskService(
        storage.session_factory,
        paths,
        worker_runner=worker_runner or _InlineWorkerRunner(),
    )
    return _Runtime(
        storage=storage,
        datasets=datasets,
        tasks=tasks,
        ml=MLService(paths, storage.session_factory, datasets, tasks),
        artifacts=ArtifactService(storage.session_factory),
    )


def _register(
    datasets: DatasetService,
    source: Path,
    *,
    project_id: str | None = None,
):
    return datasets.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            project_id=project_id,
            name=source.stem,
        )
    )


def _wait_for_terminal(
    tasks: MLTaskService,
    task_id: str,
    *,
    timeout: float = 30.0,
):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        task = tasks.get_ml_task(task_id)
        if task.status in {
            MLTaskStatus.SUCCEEDED,
            MLTaskStatus.FAILED,
            MLTaskStatus.CANCELLED,
        }:
            return task
        sleep(0.02)
    raise AssertionError(f"ML task {task_id} did not finish within {timeout} seconds")


def _wait_for_evaluation_id(
    ml: MLService,
    trained_model_id: str,
    *,
    timeout: float = 30.0,
) -> str:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        model = ml.get_trained_model(trained_model_id)
        metadata = parse_trained_model_metadata(
            model.metadata_payload if model is not None else None
        )
        if metadata is not None and metadata.evaluation_ml_task_id:
            return metadata.evaluation_ml_task_id
        sleep(0.02)
    raise AssertionError("Text classifier did not receive an evaluation task reference")


def _fixture_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _normalized_exact_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _json_digest(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_raw_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    normalized = _URL_RE.sub(" <url> ", normalized)
    normalized = _EMAIL_RE.sub(" <email> ", normalized)
    normalized = _NUMBER_RE.sub(" <number> ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _normalized_terms(path: Path) -> tuple[str, ...]:
    frame = (
        pd.read_parquet(path)
        if path.suffix.lower() == ".parquet" or path.read_bytes()[:4] == b"PAR1"
        else pd.read_csv(path)
    )
    values = frame.iloc[:, 0].tolist()
    terms = {
        re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()
        for value in values
        if value is not None and not pd.isna(value)
    }
    terms.discard("")
    return tuple(sorted(terms))


def _preparation_specification(
    *,
    custom_dataset: Any,
    stopword_dataset: Any,
) -> dict[str, Any]:
    custom_terms = _normalized_terms(Path(custom_dataset.source_path))
    stopword_terms = _normalized_terms(Path(stopword_dataset.source_path))
    resource_payload = {
        "custom_dictionary_references": [
            {
                "dataset_id": custom_dataset.id,
                "source_sha256": _fixture_digest(Path(custom_dataset.source_path)),
                "term_count": len(custom_terms),
            }
        ],
        "stopword_references": [
            {
                "dataset_id": stopword_dataset.id,
                "source_sha256": _fixture_digest(Path(stopword_dataset.source_path)),
                "term_count": len(stopword_terms),
            }
        ],
    }
    resource_digest = _json_digest(resource_payload)
    specification_payload = {
        "profile_key": "multilingual_business_v1",
        "normalization_policy_key": "unicode_nfkc_casefold_mask_entities.v1",
        "tokenizer_policy_key": "jieba_multilingual_business.v1",
        "phrase_mode": "unigram_bigram",
        "ngram_max": 2,
        **resource_payload,
        "resource_identity_digest": resource_digest,
    }
    return {
        **specification_payload,
        "specification_digest": _json_digest(specification_payload),
    }


def _prepare_oracle_texts(
    values: pd.Series,
    *,
    specification: dict[str, Any],
    custom_terms: tuple[str, ...],
    stopword_terms: tuple[str, ...],
) -> _PreparedTextOracle:
    tokenizer = jieba.Tokenizer()
    for term in custom_terms:
        tokenizer.add_word(term)
    stopwords = _BASE_STOPWORDS | frozenset(stopword_terms)

    token_rows: list[list[str]] = []
    normalized_values: list[str] = []
    exact_fingerprints: list[str] = []
    template_fingerprints: list[str] = []
    token_sets: list[frozenset[str]] = []
    missing_count = 0
    custom_match_count = 0
    cjk_count = 0
    latin_count = 0
    mixed_count = 0
    for value in values.tolist():
        if value is None or pd.isna(value):
            missing_count += 1
        normalized = _normalize_raw_text(value)
        template_tokens = _TEMPLATE_TOKEN_RE.findall(normalized)
        tokens: list[str] = []
        if normalized:
            for segment in tokenizer.lcut(normalized, HMM=False):
                for raw_token in _TOKEN_RE.findall(str(segment)):
                    token = raw_token.strip()
                    if not token or token in stopwords:
                        continue
                    if token not in {"<url>", "<email>", "<number>"} and len(token) < 2:
                        continue
                    tokens.append(token)
        custom_match_count += sum(token in custom_terms for token in tokens)
        has_cjk = bool(re.search(r"[\u3400-\u9fff]", normalized))
        has_latin = bool(re.search(r"[a-z]", normalized))
        cjk_count += int(has_cjk and not has_latin)
        latin_count += int(has_latin and not has_cjk)
        mixed_count += int(has_cjk and has_latin)
        token_rows.append(tokens)
        normalized_values.append(normalized)
        exact_fingerprints.append(
            sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""
        )
        template = " ".join(template_tokens)
        template_fingerprints.append(
            sha256(template.encode("utf-8")).hexdigest() if template else ""
        )
        token_sets.append(frozenset(template_tokens))

    prepared_values = [" ".join(tokens) for tokens in token_rows]
    non_empty_count = sum(bool(value) for value in prepared_values)
    quality = {
        "specification_digest": specification["specification_digest"],
        "source_row_count": len(prepared_values),
        "eligible_row_count": non_empty_count,
        "missing_text_row_count": missing_count,
        "non_empty_text_row_count": non_empty_count,
        "empty_after_preparation_row_count": len(prepared_values) - non_empty_count,
        "cjk_text_row_count": cjk_count,
        "latin_text_row_count": latin_count,
        "mixed_script_text_row_count": mixed_count,
        "token_count": sum(len(tokens) for tokens in token_rows),
        "custom_dictionary_term_count": len(custom_terms),
        "stopword_term_count": len(stopwords),
        "custom_term_match_count": custom_match_count,
        "collapsed_exact_duplicate_row_count": len(
            [value for value in exact_fingerprints if value]
        )
        - len({value for value in exact_fingerprints if value}),
        "collapsed_template_duplicate_row_count": len(
            [value for value in template_fingerprints if value]
        )
        - len({value for value in template_fingerprints if value}),
        "prepared_text_digest": _json_digest(prepared_values),
    }
    return _PreparedTextOracle(
        prepared_texts=pd.Series(prepared_values, dtype="string"),
        normalized_texts=pd.Series(normalized_values, dtype="string"),
        exact_fingerprints=pd.Series(exact_fingerprints, dtype="string"),
        template_fingerprints=pd.Series(template_fingerprints, dtype="string"),
        token_sets=tuple(token_sets),
        quality=quality,
    )


def _exact_template_components(frame: pd.DataFrame) -> dict[str, str]:
    """Fixture oracle: union business groups and non-empty exact text duplicates."""

    record_ids = frame["record_id"].astype(str).tolist()
    disjoint_set = _DisjointSet(record_ids)
    for _group, rows in frame.groupby("business_group", sort=True):
        members = rows["record_id"].astype(str).tolist()
        for member in members[1:]:
            disjoint_set.union(members[0], member)

    duplicate_buckets: dict[str, list[str]] = defaultdict(list)
    for row in frame.to_dict(orient="records"):
        key = _normalized_exact_text(row["message"])
        if key:
            duplicate_buckets[key].append(str(row["record_id"]))
    for members in duplicate_buckets.values():
        for member in members[1:]:
            disjoint_set.union(members[0], member)
    return {record_id: disjoint_set.find(record_id) for record_id in record_ids}


class _PositionUnion:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return False
        first, second = sorted((left_root, right_root))
        self.parent[second] = first
        return True

    def keys(self, prefix: str) -> pd.Series:
        members: dict[int, list[int]] = defaultdict(list)
        for position in range(len(self.parent)):
            members[self.find(position)].append(position)
        keys = {
            root: f"{prefix}-{sha256(','.join(str(value) for value in positions).encode()).hexdigest()[:24]}"
            for root, positions in members.items()
        }
        return pd.Series(
            [keys[self.find(position)] for position in range(len(self.parent))],
            dtype="string",
        )


def _template_groups(
    fingerprints: pd.Series,
    token_sets: tuple[frozenset[str], ...],
) -> tuple[pd.Series, int]:
    union = _PositionUnion(len(fingerprints.index))
    first_by_fingerprint: dict[str, int] = {}
    for position, fingerprint in enumerate(fingerprints.astype(str).tolist()):
        previous = first_by_fingerprint.setdefault(fingerprint, position)
        union.union(previous, position)

    inverted_index: dict[str, list[int]] = defaultdict(list)
    near_duplicate_edges = 0
    for position, tokens in enumerate(token_sets):
        candidates = {
            candidate
            for token in tokens
            for candidate in inverted_index.get(token, [])
        }
        for candidate in sorted(candidates):
            union_tokens = tokens | token_sets[candidate]
            similarity = (
                len(tokens & token_sets[candidate]) / len(union_tokens)
                if union_tokens
                else 1.0
            )
            if similarity >= 0.8:
                near_duplicate_edges += int(union.union(candidate, position))
        for token in tokens:
            inverted_index[token].append(position)
    return union.keys("template"), near_duplicate_edges


def _connected_groups(
    business_values: pd.Series,
    template_groups: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    business_keys = business_values.map(
        lambda value: ""
        if value is None or pd.isna(value)
        else _json_digest({"type": type(value).__name__, "value": str(value)})
    ).astype("string")
    union = _PositionUnion(len(template_groups.index))
    first_by_key: dict[str, int] = {}
    for position, template_key in enumerate(template_groups.astype(str).tolist()):
        previous = first_by_key.setdefault(f"template:{template_key}", position)
        union.union(previous, position)
    for position, business_key in enumerate(business_keys.astype(str).tolist()):
        if not business_key:
            continue
        previous = first_by_key.setdefault(f"business:{business_key}", position)
        union.union(previous, position)
    return business_keys, union.keys("connected")


def _component_overlap_count(
    components: dict[str, str],
    *,
    train_record_ids: Iterable[str],
    holdout_record_ids: Iterable[str],
) -> int:
    train_components = {components[value] for value in train_record_ids}
    holdout_components = {components[value] for value in holdout_record_ids}
    return len(train_components & holdout_components)


def _membership_digest(
    snapshot_digest: str,
    partition: str,
    positions: np.ndarray,
) -> str:
    payload = ",".join(str(int(position)) for position in sorted(positions.tolist()))
    return sha256(f"{snapshot_digest}|{partition}|{payload}".encode()).hexdigest()


def _group_hash_split(
    groups: pd.Series,
    labels: pd.Series,
    *,
    dataset_snapshot_payload: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    snapshot_digest = _json_digest(dataset_snapshot_payload)
    canonical_groups = groups.reset_index(drop=True).map(
        lambda value: json.dumps(
            {"type": type(value).__name__, "value": str(value)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    unique_groups = canonical_groups.drop_duplicates().tolist()
    ordered_groups = sorted(
        unique_groups,
        key=lambda value: sha256(
            f"group_hash_holdout.v1|42|{snapshot_digest}|{value}".encode()
        ).hexdigest(),
    )
    target_rows = max(1, round(len(canonical_groups.index) * 0.2))
    counts = canonical_groups.value_counts(dropna=False).to_dict()
    cumulative = 0
    candidates: list[tuple[int, int]] = []
    for count, group in enumerate(ordered_groups[:-1], start=1):
        cumulative += int(counts[group])
        candidates.append((abs(cumulative - target_rows), count))
    _distance, selected_count = min(candidates)
    holdout_groups = set(ordered_groups[:selected_count])
    holdout_mask = canonical_groups.isin(holdout_groups).to_numpy(dtype=bool)
    holdout_positions = np.flatnonzero(holdout_mask)
    train_positions = np.flatnonzero(~holdout_mask)
    assert set(labels.iloc[train_positions]) == set(labels)
    assert set(labels.iloc[holdout_positions]) == set(labels)
    assert not set(canonical_groups.iloc[train_positions]) & set(
        canonical_groups.iloc[holdout_positions]
    )
    split = {
        "schema_version": 1,
        "policy_key": "classification.group_hash_holdout.v1",
        "requested_strategy": "group_hash_holdout.v1",
        "realized_strategy": "group_hash_holdout.v1",
        "source_dataset_snapshot_digest": snapshot_digest,
        "eligible_row_count": len(labels.index),
        "train_row_count": len(train_positions),
        "holdout_row_count": len(holdout_positions),
        "eligible_group_count": len(unique_groups),
        "train_group_count": len(set(canonical_groups.iloc[train_positions])),
        "holdout_group_count": len(set(canonical_groups.iloc[holdout_positions])),
        "train_membership_digest": _membership_digest(
            snapshot_digest,
            "train",
            train_positions,
        ),
        "holdout_membership_digest": _membership_digest(
            snapshot_digest,
            "holdout",
            holdout_positions,
        ),
        "group_overlap_count": 0,
        "random_state": 42,
        "evaluation_scope": "holdout",
    }
    return train_positions, holdout_positions, split


def _vectorization_facts(
    vectorizer: TfidfVectorizer,
    prepared_texts: pd.Series,
    *,
    fit_row_count: int,
) -> dict[str, Any]:
    feature_names = [str(value) for value in vectorizer.get_feature_names_out()]
    matrix = vectorizer.transform(prepared_texts.astype("string").fillna("").tolist())
    empty_count = int(prepared_texts.astype("string").fillna("").eq("").sum())
    nonzero = np.asarray(matrix.getnnz(axis=1)).reshape(-1)
    return {
        "fit_row_count": fit_row_count,
        "transformed_feature_count": len(feature_names),
        "vocabulary_digest": _json_digest(feature_names),
        "inspected_row_count": len(prepared_texts.index),
        "empty_after_preparation_row_count": empty_count,
        "out_of_vocabulary_row_count": int((nonzero == 0).sum()) - empty_count,
    }


def _partition_overlap(
    values: pd.Series,
    train_positions: np.ndarray,
    holdout_positions: np.ndarray,
) -> int:
    train = {value for value in values.iloc[train_positions].astype(str) if value}
    holdout = {value for value in values.iloc[holdout_positions].astype(str) if value}
    return len(train & holdout)


def _build_text_oracle(
    frame: pd.DataFrame,
    *,
    dataset_snapshot_payload: dict[str, Any],
    custom_dataset: Any,
    stopword_dataset: Any,
) -> _TextOracle:
    specification = _preparation_specification(
        custom_dataset=custom_dataset,
        stopword_dataset=stopword_dataset,
    )
    custom_terms = _normalized_terms(Path(custom_dataset.source_path))
    stopword_terms = _normalized_terms(Path(stopword_dataset.source_path))
    corpus = _prepare_oracle_texts(
        frame["message"],
        specification=specification,
        custom_terms=custom_terms,
        stopword_terms=stopword_terms,
    )
    eligible_mask = corpus.prepared_texts.ne("") & frame["label"].notna()
    source_positions = np.flatnonzero(eligible_mask.to_numpy(dtype=bool))
    prepared_texts = corpus.prepared_texts.loc[eligible_mask].reset_index(drop=True)
    labels = frame.loc[eligible_mask, "label"].reset_index(drop=True)
    fingerprints = corpus.template_fingerprints.loc[eligible_mask].reset_index(drop=True)
    token_sets = tuple(corpus.token_sets[position] for position in source_positions.tolist())
    template_groups, near_duplicate_edges = _template_groups(fingerprints, token_sets)
    business_keys, connected_groups = _connected_groups(
        frame.loc[eligible_mask, "business_group"].reset_index(drop=True),
        template_groups,
    )
    train_positions, holdout_positions, split = _group_hash_split(
        connected_groups,
        labels,
        dataset_snapshot_payload=dataset_snapshot_payload,
    )
    preparation = {
        **corpus.quality,
        "eligible_row_count": len(labels.index),
        "collapsed_template_duplicate_row_count": len(template_groups.index)
        - int(template_groups.nunique(dropna=False)),
    }
    leakage = {
        "group_policy_key": "business_template_connected_union.v1",
        "template_policy_key": "masked_token_jaccard.v1",
        "template_similarity_threshold": 0.8,
        "business_group_supplied": True,
        "eligible_row_count": len(labels.index),
        "business_group_count": int(business_keys.loc[business_keys.ne("")].nunique()),
        "template_group_count": int(template_groups.nunique(dropna=False)),
        "connected_group_count": int(connected_groups.nunique(dropna=False)),
        "near_duplicate_edge_count": near_duplicate_edges,
        "train_business_group_overlap_count": _partition_overlap(
            business_keys,
            train_positions,
            holdout_positions,
        ),
        "train_template_group_overlap_count": _partition_overlap(
            template_groups,
            train_positions,
            holdout_positions,
        ),
        "train_connected_group_overlap_count": _partition_overlap(
            connected_groups,
            train_positions,
            holdout_positions,
        ),
        "group_assignment_digest": _json_digest(
            connected_groups.astype(str).tolist()
        ),
    }

    vectorizer = TfidfVectorizer(
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
        max_features=5000,
        min_df=1,
        ngram_range=(1, 2),
    )
    train_matrix = vectorizer.fit_transform(
        prepared_texts.iloc[train_positions].tolist()
    )
    model = LogisticRegression(
        class_weight="balanced",
        max_iter=500,
        random_state=42,
    )
    model.fit(train_matrix, labels.iloc[train_positions].reset_index(drop=True))
    holdout_matrix = vectorizer.transform(
        prepared_texts.iloc[holdout_positions].tolist()
    )
    predictions = model.predict(holdout_matrix)
    probabilities = model.predict_proba(holdout_matrix)
    holdout_truth = labels.iloc[holdout_positions].reset_index(drop=True)
    candidate_metrics = _classification_metrics(holdout_truth, predictions)
    baseline_predictions = _most_frequent_dummy_predictions(
        labels.iloc[train_positions],
        holdout_row_count=len(holdout_positions),
    )
    baseline_metrics = _classification_metrics(holdout_truth, baseline_predictions)
    return _TextOracle(
        specification=specification,
        preparation=preparation,
        leakage=leakage,
        vectorization=_vectorization_facts(
            vectorizer,
            prepared_texts.iloc[train_positions].reset_index(drop=True),
            fit_row_count=len(train_positions),
        ),
        split=split,
        train_positions=train_positions,
        holdout_positions=holdout_positions,
        labels=labels,
        predictions=predictions,
        probabilities=probabilities,
        candidate_metrics=candidate_metrics,
        baseline_predictions=baseline_predictions,
        baseline_metrics=baseline_metrics,
        vectorizer=vectorizer,
        model=model,
        custom_terms=custom_terms,
        stopword_terms=stopword_terms,
    )


def _classification_metrics(
    truth: Iterable[str],
    predictions: Iterable[str],
) -> _ClassificationMetrics:
    truth_values = [str(value) for value in truth]
    predicted_values = [str(value) for value in predictions]
    if not truth_values or len(truth_values) != len(predicted_values):
        raise ValueError("Classification oracle requires equal, non-empty vectors.")

    labels = sorted(set(truth_values) | set(predicted_values))
    support = Counter(truth_values)
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    for label in labels:
        true_positive = sum(
            actual == label and predicted == label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        false_positive = sum(
            actual != label and predicted == label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        false_negative = sum(
            actual == label and predicted != label
            for actual, predicted in zip(truth_values, predicted_values, strict=True)
        )
        precision[label] = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall[label] = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1[label] = (
            2.0 * precision[label] * recall[label] / (precision[label] + recall[label])
            if precision[label] + recall[label]
            else 0.0
        )

    row_count = len(truth_values)
    accuracy = sum(
        actual == predicted
        for actual, predicted in zip(truth_values, predicted_values, strict=True)
    ) / row_count

    def macro(values: dict[str, float]) -> float:
        return sum(values.values()) / len(labels)

    def weighted(values: dict[str, float]) -> float:
        return sum(values[label] * support[label] for label in labels) / row_count

    return _ClassificationMetrics(
        accuracy=accuracy,
        balanced_accuracy=macro(recall),
        precision_macro=macro(precision),
        precision_weighted=weighted(precision),
        recall_macro=macro(recall),
        recall_weighted=weighted(recall),
        f1_macro=macro(f1),
        f1_weighted=weighted(f1),
    )


def _most_frequent_dummy_predictions(
    training_truth: Iterable[str],
    *,
    holdout_row_count: int,
) -> list[str]:
    counts = Counter(str(value) for value in training_truth)
    if not counts or holdout_row_count < 1:
        raise ValueError("Dummy oracle requires training labels and a positive holdout size.")
    winner = min(counts, key=lambda label: (-counts[label], label))
    return [winner] * holdout_row_count


def _generic_prediction_digest(predictions: Iterable[str]) -> str:
    payload = [
        {"type": "str", "value": str(value)}
        for value in predictions
    ]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _assert_metric_snapshot(actual: Any, expected: _ClassificationMetrics) -> None:
    for field in expected.__dataclass_fields__:
        assert actual.metrics[field] == pytest.approx(getattr(expected, field))


def test_clean_room_bilingual_fixtures_exercise_leakage_and_apply_edges() -> None:
    fixtures = (
        TRAINING_FIXTURE,
        APPLY_FIXTURE,
        CUSTOM_DICTIONARY_FIXTURE,
        STOPWORDS_FIXTURE,
    )
    assert all(_fixture_digest(path) == FIXTURE_SHA256[path.name] for path in fixtures)

    training = pd.read_csv(TRAINING_FIXTURE, keep_default_na=False)
    assert training.columns.tolist() == [
        "record_id",
        "business_group",
        "message",
        "label",
    ]
    assert len(training) == 48
    assert training["record_id"].is_unique
    assert training["business_group"].nunique() == 12
    assert training.groupby("business_group")["label"].nunique().eq(1).all()
    assert training.groupby("business_group").size().eq(4).all()
    assert training["label"].value_counts().to_dict() == {
        "priority": 24,
        "standard": 24,
    }
    assert training["message"].map(_normalized_exact_text).eq("").sum() == 2

    components = _exact_template_components(training)
    component_members: dict[str, list[str]] = defaultdict(list)
    for record_id, component in components.items():
        component_members[component].append(record_id)
    assert sorted(len(members) for members in component_members.values()) == [16] * 3
    assert all(
        training.loc[training["record_id"].isin(members), "label"].nunique() == 2
        for members in component_members.values()
    )
    assert _component_overlap_count(
        components,
        train_record_ids=["p01-01", "p02-02"],
        holdout_record_ids=["p01-03", "p02-04"],
    ) == 1
    assert _component_overlap_count(
        components,
        train_record_ids=["p01-01", "s02-01"],
        holdout_record_ids=["p03-01", "s04-01"],
    ) == 0

    indexed = training.set_index("record_id")
    for left, right in NEAR_DUPLICATE_RECORD_PAIRS:
        assert indexed.at[left, "business_group"] != indexed.at[right, "business_group"]
        assert indexed.at[left, "label"] == indexed.at[right, "label"]
        assert indexed.at[left, "message"] != indexed.at[right, "message"]

    custom_terms = pd.read_csv(CUSTOM_DICTIONARY_FIXTURE)["term"].astype(str).tolist()
    stopwords = pd.read_csv(STOPWORDS_FIXTURE)["term"].astype(str).tolist()
    corpus = "\n".join(training["message"].astype(str))
    apply = pd.read_csv(APPLY_FIXTURE, keep_default_na=False)
    apply_corpus = "\n".join(apply["message"].astype(str))
    assert len(custom_terms) == 4
    assert all(term in f"{corpus}\n{apply_corpus}" for term in custom_terms)
    assert len(stopwords) == 5
    assert all(term.casefold() in corpus.casefold() for term in stopwords)
    assert apply.columns.tolist() == ["request_id", "message"]
    assert len(apply) == 6
    assert apply["message"].map(_normalized_exact_text).eq("").sum() == 2
    assert "QuantumFoam" in apply_corpus
    assert "龙鳞协议" in apply_corpus


def test_independent_classification_and_dummy_oracles_are_deterministic() -> None:
    truth = ["priority", "priority", "standard", "standard"]
    predictions = ["priority", "standard", "standard", "standard"]
    metrics = _classification_metrics(truth, predictions)
    assert metrics.accuracy == pytest.approx(0.75)
    assert metrics.balanced_accuracy == pytest.approx(0.75)
    assert metrics.precision_macro == pytest.approx(5.0 / 6.0)
    assert metrics.precision_weighted == pytest.approx(5.0 / 6.0)
    assert metrics.recall_macro == pytest.approx(0.75)
    assert metrics.recall_weighted == pytest.approx(0.75)
    assert metrics.f1_macro == pytest.approx(11.0 / 15.0)
    assert metrics.f1_weighted == pytest.approx(11.0 / 15.0)

    dummy = _most_frequent_dummy_predictions(
        ["standard", "priority", "standard", "priority"],
        holdout_row_count=4,
    )
    assert dummy == ["priority"] * 4
    digest = _generic_prediction_digest(predictions)
    assert len(digest) == 64
    assert digest == _generic_prediction_digest(predictions)
    assert digest != _generic_prediction_digest(list(reversed(predictions)))
    assert math.isfinite(metrics.f1_weighted)


def test_multilingual_text_classification_real_lifecycle_is_leakage_safe_and_public(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        project_id = training_dataset.project_id
        apply_dataset = _register(
            runtime.datasets,
            APPLY_FIXTURE,
            project_id=project_id,
        )
        custom_dataset = _register(
            runtime.datasets,
            CUSTOM_DICTIONARY_FIXTURE,
            project_id=project_id,
        )
        stopword_dataset = _register(
            runtime.datasets,
            STOPWORDS_FIXTURE,
            project_id=project_id,
        )
        registered_sources = {
            dataset.id: (
                Path(dataset.source_path),
                _fixture_digest(Path(dataset.source_path)),
            )
            for dataset in (
                training_dataset,
                apply_dataset,
                custom_dataset,
                stopword_dataset,
            )
        }

        catalog = get_model_catalog_entry(ACTIVE_MODEL_KEY)
        assert catalog.supports_hyperparameter_tuning is False
        assert set(catalog.param_schema["properties"]) == {
            *PARAMS_TEMPLATE,
            "custom_dictionary_dataset_ids",
            "stopword_dataset_ids",
        }
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["label"]},
                    {"role": "group", "columns": ["business_group"]},
                ],
            )
        )
        assert binding.dataset_snapshot_payload is not None
        params = {
            **PARAMS_TEMPLATE,
            "custom_dictionary_dataset_ids": [custom_dataset.id],
            "stopword_dataset_ids": [stopword_dataset.id],
        }
        fit_task = runtime.ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=binding.id,
                run_name="Leakage-safe bilingual request classification",
                model_key=ACTIVE_MODEL_KEY,
                params=params,
            )
        )
        completed_fit = _wait_for_terminal(runtime.tasks, fit_task.id)
        assert completed_fit.status is MLTaskStatus.SUCCEEDED, completed_fit.error_summary
        fit_payload = completed_fit.result_payload or {}
        fit_result = FitTaskResult.model_validate(fit_payload)
        assert fit_result.training_scopes is not None
        assert fit_result.training_scopes.model_dump(mode="json") == {
            "evaluation_model": "holdout_train_split",
            "apply_model": "all_eligible_rows",
        }
        assert fit_result.params == params
        assert fit_result.text_preparation_specification is not None
        assert fit_result.text_preparation_facts is not None
        assert fit_result.text_leakage_facts is not None
        assert fit_result.text_vectorization_facts is not None

        oracle = _build_text_oracle(
            pd.read_parquet(training_dataset.source_path),
            dataset_snapshot_payload=binding.dataset_snapshot_payload,
            custom_dataset=custom_dataset,
            stopword_dataset=stopword_dataset,
        )
        assert fit_result.text_preparation_specification.model_dump(
            mode="json"
        ) == oracle.specification
        assert fit_result.text_preparation_facts.model_dump(mode="json") == oracle.preparation
        assert fit_result.text_leakage_facts.model_dump(mode="json") == oracle.leakage
        assert fit_result.text_vectorization_facts.model_dump(
            mode="json"
        ) == oracle.vectorization
        assert fit_result.split_facts is not None
        assert fit_result.split_facts.model_dump(mode="json") == oracle.split
        assert oracle.leakage["connected_group_count"] == 3
        assert oracle.leakage["near_duplicate_edge_count"] == 6
        assert oracle.leakage["train_business_group_overlap_count"] == 0
        assert oracle.leakage["train_template_group_overlap_count"] == 0
        assert oracle.leakage["train_connected_group_overlap_count"] == 0

        trained_model = runtime.ml.get_trained_model_by_ml_task(fit_task.id)
        assert trained_model is not None
        assert trained_model.dataset_id == training_dataset.id
        metadata = parse_trained_model_metadata(trained_model.metadata_payload)
        assert metadata is not None
        assert metadata.training_params == params
        assert metadata.evaluation_model_training_scope == "holdout_train_split"
        assert metadata.apply_model_training_scope == "all_eligible_rows"
        evaluation_task_id = _wait_for_evaluation_id(runtime.ml, trained_model.id)
        completed_evaluation = _wait_for_terminal(runtime.tasks, evaluation_task_id)
        assert completed_evaluation.status is MLTaskStatus.SUCCEEDED, (
            completed_evaluation.error_summary
        )
        evaluation = EvaluateTaskResult.model_validate(
            completed_evaluation.result_payload
        )
        assert evaluation.evaluation is not None
        assert evaluation.baseline_evaluation is not None
        assert evaluation.comparison is not None
        assert evaluation.split_facts is not None
        assert evaluation.split_facts.model_dump(mode="json") == oracle.split
        _assert_metric_snapshot(evaluation.evaluation, oracle.candidate_metrics)
        _assert_metric_snapshot(evaluation.baseline_evaluation, oracle.baseline_metrics)
        assert evaluation.evaluation.details["prediction_digest"] == (
            _generic_prediction_digest(oracle.predictions)
        )
        text_evaluation = evaluation.text_classification_evaluation
        assert text_evaluation is not None
        assert text_evaluation.specification.model_dump(
            mode="json"
        ) == oracle.specification
        assert text_evaluation.preparation.model_dump(mode="json") == oracle.preparation
        assert text_evaluation.leakage.model_dump(mode="json") == oracle.leakage
        assert text_evaluation.prediction_digest == _generic_prediction_digest(
            oracle.predictions
        )
        assert text_evaluation.prediction_digest == evaluation.evaluation.details[
            "prediction_digest"
        ]

        prepared_training = _prepare_oracle_texts(
            pd.read_parquet(training_dataset.source_path)["message"],
            specification=oracle.specification,
            custom_terms=oracle.custom_terms,
            stopword_terms=oracle.stopword_terms,
        ).prepared_texts
        eligible_training = prepared_training.loc[prepared_training.ne("")].reset_index(
            drop=True
        )
        expected_evaluation_vectorization = _vectorization_facts(
            oracle.vectorizer,
            eligible_training.iloc[oracle.holdout_positions].reset_index(drop=True),
            fit_row_count=len(oracle.train_positions),
        )
        assert text_evaluation.vectorization.model_dump(
            mode="json"
        ) == expected_evaluation_vectorization

        evaluation_report = next(
            artifact
            for artifact in runtime.tasks.list_ml_task_artifacts(evaluation_task_id)
            if artifact.artifact_kind is MLTaskArtifactKind.EVALUATION_REPORT
        )
        assert evaluation_report.ready_to_open is True
        assert evaluation_report.artifact_id
        assert runtime.artifacts.resolve_uri(
            build_artifact_uri(evaluation_report.artifact_id)
        ).exists is True

        apply_task = runtime.ml.apply(
            ApplyWithFilesInput(
                trained_model_id=trained_model.id,
                input_sources=[
                    ApplySourceInput(
                        source_path=apply_dataset.source_path,
                        dataset_id=apply_dataset.id,
                    )
                ],
            )
        )
        completed_apply = _wait_for_terminal(runtime.tasks, apply_task.id)
        assert completed_apply.status is MLTaskStatus.SUCCEEDED, completed_apply.error_summary
        apply_payload = completed_apply.result_payload or {}
        apply_facts = apply_payload["text_classification_apply_facts"]
        assert apply_facts["specification"] == oracle.specification
        result_dataset = runtime.datasets.get_dataset(apply_payload["result_dataset_id"])
        assert result_dataset.derived_from_dataset_id == apply_dataset.id
        assert result_dataset.ml_task_id == apply_task.id
        result_frame = pd.read_parquet(result_dataset.source_path)
        assert result_frame.columns.tolist() == [
            "request_id",
            "message",
            "prediction",
            "prediction_score",
        ]

        full_vectorizer = TfidfVectorizer(
            tokenizer=str.split,
            preprocessor=None,
            token_pattern=None,
            lowercase=False,
            max_features=5000,
            min_df=1,
            ngram_range=(1, 2),
        )
        full_matrix = full_vectorizer.fit_transform(eligible_training.tolist())
        full_model = LogisticRegression(
            class_weight="balanced",
            max_iter=500,
            random_state=42,
        )
        full_model.fit(full_matrix, oracle.labels)
        apply_source = pd.read_parquet(apply_dataset.source_path)
        apply_corpus = _prepare_oracle_texts(
            apply_source["message"],
            specification=oracle.specification,
            custom_terms=oracle.custom_terms,
            stopword_terms=oracle.stopword_terms,
        )
        apply_matrix = full_vectorizer.transform(apply_corpus.prepared_texts.tolist())
        expected_apply_predictions = full_model.predict(apply_matrix)
        expected_apply_scores = full_model.predict_proba(apply_matrix).max(axis=1)
        assert result_frame["prediction"].tolist() == expected_apply_predictions.tolist()
        assert result_frame["prediction_score"].to_numpy() == pytest.approx(
            expected_apply_scores
        )
        assert apply_facts["preparation"] == apply_corpus.quality
        assert apply_facts["vectorization"] == _vectorization_facts(
            full_vectorizer,
            apply_corpus.prepared_texts,
            fit_row_count=len(oracle.labels.index),
        )
        assert apply_facts["prediction_digest"] == _generic_prediction_digest(
            expected_apply_predictions
        )
        assert apply_facts["preparation"]["empty_after_preparation_row_count"] == 2
        assert apply_facts["vectorization"]["out_of_vocabulary_row_count"] >= 1

        apply_artifact = next(
            artifact
            for artifact in runtime.tasks.list_ml_task_artifacts(apply_task.id)
            if artifact.artifact_kind is MLTaskArtifactKind.APPLY_RESULT
        )
        assert apply_artifact.ready_to_open is True
        assert apply_artifact.artifact_id
        resolved_apply = runtime.artifacts.resolve_uri(
            build_artifact_uri(apply_artifact.artifact_id)
        )
        assert resolved_apply.exists is True
        assert resolved_apply.metadata_payload["training_dataset_id"] == training_dataset.id
        assert resolved_apply.metadata_payload["source_dataset_ids"] == [apply_dataset.id]
        assert resolved_apply.metadata_payload["result_dataset_id"] == result_dataset.id

        bounded_evidence = json.dumps(
            {
                "fit_specification": oracle.specification,
                "fit_preparation": oracle.preparation,
                "fit_leakage": oracle.leakage,
                "fit_vectorization": oracle.vectorization,
                "evaluation": text_evaluation.model_dump(mode="json"),
                "apply": apply_facts,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for forbidden in (
            "absolute_path",
            "source_path",
            "artifact_path",
            "acct-north",
            "acct-south",
            "p01-",
            "s01-",
            "支付网关 timeout",
            "BlueHarbor mobile",
            "QuantumFoam",
            "星云工单",
            "龙鳞协议",
            "checkout",
            "invoice",
            "feature_names",
        ):
            assert forbidden not in bounded_evidence

        for source_path, original_digest in registered_sources.values():
            assert _fixture_digest(source_path) == original_digest
        assert all(
            _fixture_digest(path) == FIXTURE_SHA256[path.name]
            for path in (
                TRAINING_FIXTURE,
                APPLY_FIXTURE,
                CUSTOM_DICTIONARY_FIXTURE,
                STOPWORDS_FIXTURE,
            )
        )
    finally:
        runtime.storage.engine.dispose()


def test_text_resources_reject_cross_project_dataset_references(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        with runtime.storage.session_factory() as session:
            other_project = ProjectRow(name="Independent text resource project")
            session.add(other_project)
            session.commit()
            session.refresh(other_project)
        cross_project_resource = _register(
            runtime.datasets,
            CUSTOM_DICTIONARY_FIXTURE,
            project_id=other_project.id,
        )
        assert cross_project_resource.project_id != training_dataset.project_id
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["label"]},
                    {"role": "group", "columns": ["business_group"]},
                ],
            )
        )
        with pytest.raises(
            ValidationError,
            match="resources must belong to the training project",
        ):
            runtime.ml.fit_with_evaluate(
                FitWithEvaluateInput(
                    binding_id=binding.id,
                    model_key=ACTIVE_MODEL_KEY,
                    params={
                        **PARAMS_TEMPLATE,
                        "custom_dictionary_dataset_ids": [cross_project_resource.id],
                        "stopword_dataset_ids": [],
                    },
                )
            )
    finally:
        runtime.storage.engine.dispose()


def test_text_resource_integrity_fails_closed_after_staging_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = _TamperingInlineWorkerRunner()
    runtime = _runtime(monkeypatch, tmp_path, worker_runner=runner)
    try:
        training_dataset = _register(runtime.datasets, TRAINING_FIXTURE)
        mutable_terms = tmp_path / "mutable_terms.csv"
        mutable_terms.write_text("term\n星云工单\n", encoding="utf-8")
        resource_dataset = _register(
            runtime.datasets,
            mutable_terms,
            project_id=training_dataset.project_id,
        )
        binding = runtime.ml.create_column_binding(
            CreateColumnBindingInput(
                dataset_id=training_dataset.id,
                model_key=ACTIVE_MODEL_KEY,
                role_bindings=[
                    {"role": "text", "columns": ["message"]},
                    {"role": "target", "columns": ["label"]},
                    {"role": "group", "columns": ["business_group"]},
                ],
            )
        )
        runner.target_path = Path(resource_dataset.source_path)
        fit_task = runtime.ml.fit_with_evaluate(
            FitWithEvaluateInput(
                binding_id=binding.id,
                model_key=ACTIVE_MODEL_KEY,
                params={
                    **PARAMS_TEMPLATE,
                    "custom_dictionary_dataset_ids": [resource_dataset.id],
                    "stopword_dataset_ids": [],
                },
            )
        )
        failed = _wait_for_terminal(runtime.tasks, fit_task.id)
        assert failed.status is MLTaskStatus.FAILED
        assert "SHA-256 integrity check" in str(failed.error_summary)
    finally:
        runtime.storage.engine.dispose()
