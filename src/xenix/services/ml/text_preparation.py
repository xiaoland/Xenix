from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import jieba
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ...exceptions import ValidationError
from ..data_tokenization_contracts import StagedTextResourceInput, TextPreparationInput

_MULTILINGUAL_PROFILE: Literal["multilingual_business_v1"] = "multilingual_business_v1"
_NORMALIZATION_POLICY: Literal["unicode_nfkc_casefold_mask_entities.v1"] = (
    "unicode_nfkc_casefold_mask_entities.v1"
)
_TOKENIZER_POLICY: Literal["jieba_multilingual_business.v1"] = "jieba_multilingual_business.v1"
_GROUP_POLICY: Literal["business_template_connected_union.v1"] = "business_template_connected_union.v1"
_TEMPLATE_POLICY: Literal["masked_token_jaccard.v1"] = "masked_token_jaccard.v1"
_TEMPLATE_SIMILARITY_THRESHOLD = 0.8
_MAX_RESOURCE_TERMS = 20_000
_MAX_TERM_LENGTH = 64

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_EMAIL_RE = re.compile(r"(?i)\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_NUMBER_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?![\w])")
_TOKEN_RE = re.compile(r"<url>|<email>|<number>|[\u3400-\u9fff]+|[a-z]+(?:['-][a-z]+)*")
_TEMPLATE_TOKEN_RE = re.compile(r"<url>|<email>|<number>|[\u3400-\u9fff]+|[a-z]+")
_SPACE_RE = re.compile(r"\s+")

_MULTILINGUAL_BUSINESS_STOPWORDS = frozenset(
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


class _StrictFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TextResourceReference(_StrictFact):
    dataset_id: str = Field(min_length=1, max_length=128)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    term_count: int = Field(ge=0, le=_MAX_RESOURCE_TERMS)


class TextPreparationSpecification(_StrictFact):
    profile_key: Literal["multilingual_business_v1"] = _MULTILINGUAL_PROFILE
    normalization_policy_key: Literal["unicode_nfkc_casefold_mask_entities.v1"] = _NORMALIZATION_POLICY
    tokenizer_policy_key: Literal["jieba_multilingual_business.v1"] = _TOKENIZER_POLICY
    phrase_mode: Literal["unigram", "unigram_bigram"]
    ngram_max: int = Field(ge=1, le=2)
    custom_dictionary_references: list[TextResourceReference] = Field(default_factory=list, max_length=4)
    stopword_references: list[TextResourceReference] = Field(default_factory=list, max_length=4)
    resource_identity_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    specification_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextPreparationQualityFacts(_StrictFact):
    specification_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_count: int = Field(ge=0)
    eligible_row_count: int = Field(ge=0)
    missing_text_row_count: int = Field(ge=0)
    non_empty_text_row_count: int = Field(ge=0)
    empty_after_preparation_row_count: int = Field(ge=0)
    cjk_text_row_count: int = Field(ge=0)
    latin_text_row_count: int = Field(ge=0)
    mixed_script_text_row_count: int = Field(ge=0)
    token_count: int = Field(ge=0)
    custom_dictionary_term_count: int = Field(ge=0, le=_MAX_RESOURCE_TERMS)
    stopword_term_count: int = Field(ge=0, le=_MAX_RESOURCE_TERMS)
    custom_term_match_count: int = Field(ge=0)
    collapsed_exact_duplicate_row_count: int = Field(ge=0)
    collapsed_template_duplicate_row_count: int = Field(ge=0)
    prepared_text_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextLeakageFacts(_StrictFact):
    group_policy_key: Literal["business_template_connected_union.v1"] = _GROUP_POLICY
    template_policy_key: Literal["masked_token_jaccard.v1"] = _TEMPLATE_POLICY
    template_similarity_threshold: float = Field(ge=0.0, le=1.0)
    business_group_supplied: bool
    eligible_row_count: int = Field(ge=0)
    business_group_count: int = Field(ge=0)
    template_group_count: int = Field(ge=0)
    connected_group_count: int = Field(ge=0)
    near_duplicate_edge_count: int = Field(ge=0)
    train_business_group_overlap_count: int = Field(ge=0)
    train_template_group_overlap_count: int = Field(ge=0)
    train_connected_group_overlap_count: int = Field(ge=0)
    group_assignment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextVectorizationFacts(_StrictFact):
    fit_row_count: int = Field(ge=0)
    transformed_feature_count: int = Field(ge=0)
    vocabulary_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inspected_row_count: int = Field(ge=0)
    empty_after_preparation_row_count: int = Field(ge=0)
    out_of_vocabulary_row_count: int = Field(ge=0)


class TextClassificationEvaluationFacts(_StrictFact):
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    leakage: TextLeakageFacts
    vectorization: TextVectorizationFacts
    prediction_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextClassificationApplyFacts(_StrictFact):
    specification: TextPreparationSpecification
    preparation: TextPreparationQualityFacts
    vectorization: TextVectorizationFacts
    prediction_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PreparedTextCorpus:
    token_rows: list[list[str]]
    prepared_texts: pd.Series
    normalized_texts: pd.Series
    exact_fingerprints: pd.Series
    template_fingerprints: pd.Series
    token_sets: tuple[frozenset[str], ...]
    quality_facts: TextPreparationQualityFacts


@dataclass(frozen=True)
class PreparedTextClassificationData:
    raw_texts: pd.Series
    prepared_texts: pd.Series
    labels: pd.Series
    connected_groups: pd.Series
    business_group_keys: pd.Series
    template_group_keys: pd.Series
    source_positions: np.ndarray
    preparation_facts: TextPreparationQualityFacts
    specification: TextPreparationSpecification
    near_duplicate_edge_count: int


class TextPreparer:
    """Deterministic raw-text preparation retained privately with trained analyzers."""

    def __init__(
        self,
        *,
        specification: TextPreparationSpecification,
        custom_terms: Sequence[str],
        stopwords: Sequence[str],
    ) -> None:
        self.specification = specification
        self.custom_terms = tuple(sorted(set(custom_terms)))
        self.stopwords = frozenset(stopwords)

    @property
    def ngram_max(self) -> int:
        return self.specification.ngram_max

    def prepare_series(self, series: pd.Series) -> PreparedTextCorpus:
        tokenizer = jieba.Tokenizer()
        for term in self.custom_terms:
            tokenizer.add_word(term)

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

        for value in series.tolist():
            if _is_missing(value):
                missing_count += 1
                raw_text = ""
            else:
                raw_text = str(value)
            normalized = normalize_multilingual_text(raw_text)
            template = template_fingerprint(normalized)
            tokens = _tokenize_normalized(normalized, tokenizer=tokenizer, stopwords=self.stopwords)
            custom_match_count += sum(token in self.custom_terms for token in tokens)
            has_cjk = bool(re.search(r"[\u3400-\u9fff]", normalized))
            has_latin = bool(re.search(r"[a-z]", normalized))
            cjk_count += int(has_cjk and not has_latin)
            latin_count += int(has_latin and not has_cjk)
            mixed_count += int(has_cjk and has_latin)
            token_rows.append(tokens)
            normalized_values.append(normalized)
            exact_fingerprints.append(_digest(normalized) if normalized else "")
            template_fingerprints.append(_digest(template) if template else "")
            token_sets.append(frozenset(_TEMPLATE_TOKEN_RE.findall(template)))

        prepared_values = [" ".join(tokens) for tokens in token_rows]
        source_row_count = len(prepared_values)
        non_empty_count = sum(bool(value) for value in prepared_values)
        quality = TextPreparationQualityFacts(
            specification_digest=self.specification.specification_digest,
            source_row_count=source_row_count,
            eligible_row_count=non_empty_count,
            missing_text_row_count=missing_count,
            non_empty_text_row_count=non_empty_count,
            empty_after_preparation_row_count=source_row_count - non_empty_count,
            cjk_text_row_count=cjk_count,
            latin_text_row_count=latin_count,
            mixed_script_text_row_count=mixed_count,
            token_count=sum(len(tokens) for tokens in token_rows),
            custom_dictionary_term_count=len(self.custom_terms),
            stopword_term_count=len(self.stopwords),
            custom_term_match_count=custom_match_count,
            collapsed_exact_duplicate_row_count=_collapsed_count(exact_fingerprints, ignore_empty=True),
            collapsed_template_duplicate_row_count=_collapsed_count(template_fingerprints, ignore_empty=True),
            prepared_text_digest=_ordered_digest(prepared_values),
        )
        return PreparedTextCorpus(
            token_rows=token_rows,
            prepared_texts=pd.Series(prepared_values, index=series.index, dtype="string"),
            normalized_texts=pd.Series(normalized_values, index=series.index, dtype="string"),
            exact_fingerprints=pd.Series(exact_fingerprints, index=series.index, dtype="string"),
            template_fingerprints=pd.Series(template_fingerprints, index=series.index, dtype="string"),
            token_sets=tuple(token_sets),
            quality_facts=quality,
        )


def build_text_preparer(input_data: TextPreparationInput) -> TextPreparer:
    if input_data.tokenizer_profile != _MULTILINGUAL_PROFILE:
        raise ValidationError(
            "Raw text classification requires tokenizer profile 'multilingual_business_v1'."
        )
    custom_terms, custom_references = _load_resource_terms(input_data.custom_dictionary_resources)
    custom_stopwords, stopword_references = _load_resource_terms(input_data.stopword_resources)
    stopwords = set(_MULTILINGUAL_BUSINESS_STOPWORDS)
    stopwords.update(custom_stopwords)
    ngram_max = 2 if input_data.phrase_mode == "unigram_bigram" else 1
    resource_payload = {
        "custom_dictionary_references": [item.model_dump(mode="json") for item in custom_references],
        "stopword_references": [item.model_dump(mode="json") for item in stopword_references],
    }
    resource_digest = _json_digest(resource_payload)
    specification_payload = {
        "profile_key": _MULTILINGUAL_PROFILE,
        "normalization_policy_key": _NORMALIZATION_POLICY,
        "tokenizer_policy_key": _TOKENIZER_POLICY,
        "phrase_mode": input_data.phrase_mode,
        "ngram_max": ngram_max,
        **resource_payload,
        "resource_identity_digest": resource_digest,
    }
    specification = TextPreparationSpecification(
        profile_key=_MULTILINGUAL_PROFILE,
        normalization_policy_key=_NORMALIZATION_POLICY,
        tokenizer_policy_key=_TOKENIZER_POLICY,
        phrase_mode=input_data.phrase_mode,
        ngram_max=ngram_max,
        custom_dictionary_references=custom_references,
        stopword_references=stopword_references,
        resource_identity_digest=resource_digest,
        specification_digest=_json_digest(specification_payload),
    )
    return TextPreparer(
        specification=specification,
        custom_terms=custom_terms,
        stopwords=tuple(sorted(stopwords)),
    )


def prepare_text_classification_data(
    dataframe: pd.DataFrame,
    *,
    text_column: str,
    target_column: str,
    business_group_column: str | None,
    preparer: TextPreparer,
) -> PreparedTextClassificationData:
    required = [text_column, target_column]
    if business_group_column is not None:
        required.append(business_group_column)
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise ValidationError(f"Text classification columns are missing: {', '.join(missing)}.")
    if len(set(required)) != len(required):
        raise ValidationError("Text, target, and optional business group columns must be distinct.")

    corpus = preparer.prepare_series(dataframe[text_column])
    eligible_mask = corpus.prepared_texts.ne("") & dataframe[target_column].notna()
    source_positions = np.flatnonzero(eligible_mask.to_numpy(dtype=bool))
    if len(source_positions) < 4:
        raise ValidationError("Text classification requires at least four non-empty labeled rows.")
    labels = dataframe.loc[eligible_mask, target_column].reset_index(drop=True)
    if labels.nunique(dropna=True) < 2:
        raise ValidationError("Text classification requires at least two target classes.")

    eligible_templates = corpus.template_fingerprints.loc[eligible_mask].reset_index(drop=True)
    eligible_token_sets = tuple(corpus.token_sets[position] for position in source_positions.tolist())
    template_groups, near_duplicate_edge_count = _template_groups(eligible_templates, eligible_token_sets)
    business_values = (
        dataframe.loc[eligible_mask, business_group_column].reset_index(drop=True)
        if business_group_column is not None
        else pd.Series([None] * len(source_positions), dtype="object")
    )
    business_keys = business_values.map(_business_group_key).astype("string")
    connected_groups = _connected_union_groups(business_keys, template_groups)
    eligible_prepared = corpus.prepared_texts.loc[eligible_mask].reset_index(drop=True)
    preparation_facts = corpus.quality_facts.model_copy(
        update={
            "eligible_row_count": len(source_positions),
            "collapsed_template_duplicate_row_count": len(template_groups.index)
            - int(template_groups.nunique(dropna=False)),
        }
    )
    return PreparedTextClassificationData(
        raw_texts=dataframe.loc[eligible_mask, text_column].astype("string").fillna("").reset_index(drop=True),
        prepared_texts=eligible_prepared,
        labels=labels,
        connected_groups=connected_groups,
        business_group_keys=business_keys,
        template_group_keys=template_groups,
        source_positions=source_positions,
        preparation_facts=preparation_facts,
        specification=preparer.specification,
        near_duplicate_edge_count=near_duplicate_edge_count,
    )


def build_text_leakage_facts(
    prepared: PreparedTextClassificationData,
    *,
    train_positions: Sequence[int] | np.ndarray,
    holdout_positions: Sequence[int] | np.ndarray,
) -> TextLeakageFacts:
    train = np.asarray(train_positions, dtype=int)
    holdout = np.asarray(holdout_positions, dtype=int)
    _validate_partition_positions(len(prepared.labels.index), train, holdout)
    return TextLeakageFacts(
        template_similarity_threshold=_TEMPLATE_SIMILARITY_THRESHOLD,
        business_group_supplied=bool(prepared.business_group_keys.ne("").any()),
        eligible_row_count=len(prepared.labels.index),
        business_group_count=int(prepared.business_group_keys.loc[prepared.business_group_keys.ne("")].nunique()),
        template_group_count=int(prepared.template_group_keys.nunique(dropna=False)),
        connected_group_count=int(prepared.connected_groups.nunique(dropna=False)),
        near_duplicate_edge_count=prepared.near_duplicate_edge_count,
        train_business_group_overlap_count=_partition_overlap(prepared.business_group_keys, train, holdout),
        train_template_group_overlap_count=_partition_overlap(prepared.template_group_keys, train, holdout),
        train_connected_group_overlap_count=_partition_overlap(prepared.connected_groups, train, holdout),
        group_assignment_digest=_ordered_digest(prepared.connected_groups.astype(str).tolist()),
    )


def build_text_vectorization_facts(
    vectorizer: Any,
    prepared_texts: pd.Series,
    *,
    fit_row_count: int,
) -> TextVectorizationFacts:
    try:
        feature_names = [str(name) for name in vectorizer.get_feature_names_out()]
        matrix = vectorizer.transform(prepared_texts.astype("string").fillna("").tolist())
    except Exception as exc:
        raise ValidationError("The fitted text analyzer did not expose a reusable TF-IDF vocabulary.") from exc
    empty_count = int(prepared_texts.astype("string").fillna("").eq("").sum())
    row_nonzero = np.asarray(matrix.getnnz(axis=1)).reshape(-1)
    return TextVectorizationFacts(
        fit_row_count=fit_row_count,
        transformed_feature_count=len(feature_names),
        vocabulary_digest=_ordered_digest(feature_names),
        inspected_row_count=len(prepared_texts.index),
        empty_after_preparation_row_count=empty_count,
        out_of_vocabulary_row_count=int((row_nonzero == 0).sum()) - empty_count,
    )


def normalize_multilingual_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = _URL_RE.sub(" <url> ", normalized)
    normalized = _EMAIL_RE.sub(" <email> ", normalized)
    normalized = _NUMBER_RE.sub(" <number> ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def template_fingerprint(normalized_text: str) -> str:
    tokens = _TEMPLATE_TOKEN_RE.findall(normalized_text)
    return " ".join(tokens)


def _tokenize_normalized(
    normalized: str,
    *,
    tokenizer: jieba.Tokenizer,
    stopwords: frozenset[str],
) -> list[str]:
    if not normalized:
        return []
    tokens: list[str] = []
    for segment in tokenizer.lcut(normalized, HMM=False):
        for raw_token in _TOKEN_RE.findall(str(segment)):
            token = raw_token.strip()
            if not token or token in stopwords:
                continue
            if token not in {"<url>", "<email>", "<number>"} and len(token) < 2:
                continue
            tokens.append(token)
    return tokens


def _load_resource_terms(
    resources: Sequence[StagedTextResourceInput],
) -> tuple[tuple[str, ...], list[TextResourceReference]]:
    terms: set[str] = set()
    references: list[TextResourceReference] = []
    for resource in resources:
        path = Path(resource.absolute_path)
        if not path.is_absolute() or not path.is_file():
            raise ValidationError(f"Staged text resource '{resource.dataset_id}' is not an absolute existing file.")
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != resource.source_sha256:
            raise ValidationError(f"Staged text resource '{resource.dataset_id}' failed its SHA-256 integrity check.")
        loaded_terms = {_normalize_term(value) for value in _read_term_values(path)}
        loaded_terms.discard("")
        if len(terms | loaded_terms) > _MAX_RESOURCE_TERMS:
            raise ValidationError(f"Text preparation accepts at most {_MAX_RESOURCE_TERMS} distinct resource terms.")
        terms.update(loaded_terms)
        references.append(
            TextResourceReference(
                dataset_id=resource.dataset_id,
                source_sha256=resource.source_sha256,
                term_count=len(loaded_terms),
            )
        )
    return tuple(sorted(terms)), references


def _read_term_values(path: Path) -> list[Any]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(path)
        elif suffix == ".parquet":
            frame = pd.read_parquet(path)
        elif suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(path)
        else:
            return path.read_text(encoding="utf-8-sig").splitlines()
    except Exception as exc:
        raise ValidationError(f"Could not read staged text resource '{path.name}': {exc}") from exc
    if len(frame.columns) != 1:
        raise ValidationError(f"Text resource '{path.name}' must contain exactly one term column.")
    return list(frame.iloc[:, 0].tolist())


def _normalize_term(value: Any) -> str:
    if _is_missing(value):
        return ""
    term = _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()
    if len(term) > _MAX_TERM_LENGTH:
        raise ValidationError(f"Text preparation terms cannot exceed {_MAX_TERM_LENGTH} characters.")
    return term


class _UnionFind:
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
        members: dict[int, list[int]] = {}
        for position in range(len(self.parent)):
            members.setdefault(self.find(position), []).append(position)
        keys = {
            root: f"{prefix}-{_digest(','.join(str(position) for position in positions))[:24]}"
            for root, positions in members.items()
        }
        return pd.Series([keys[self.find(position)] for position in range(len(self.parent))], dtype="string")


def _template_groups(
    fingerprints: pd.Series,
    token_sets: tuple[frozenset[str], ...],
) -> tuple[pd.Series, int]:
    union = _UnionFind(len(fingerprints.index))
    first_by_fingerprint: dict[str, int] = {}
    for position, fingerprint in enumerate(fingerprints.astype(str).tolist()):
        previous = first_by_fingerprint.setdefault(fingerprint, position)
        union.union(previous, position)

    inverted_index: dict[str, list[int]] = {}
    near_duplicate_edges = 0
    for position, tokens in enumerate(token_sets):
        candidates: set[int] = set()
        for token in tokens:
            candidates.update(inverted_index.get(token, []))
        for candidate in sorted(candidates):
            if _jaccard(tokens, token_sets[candidate]) >= _TEMPLATE_SIMILARITY_THRESHOLD:
                near_duplicate_edges += int(union.union(candidate, position))
        for token in tokens:
            inverted_index.setdefault(token, []).append(position)
    return union.keys("template"), near_duplicate_edges


def _connected_union_groups(business_keys: pd.Series, template_groups: pd.Series) -> pd.Series:
    union = _UnionFind(len(template_groups.index))
    first_by_key: dict[str, int] = {}
    for position, template_key in enumerate(template_groups.astype(str).tolist()):
        previous = first_by_key.setdefault(f"template:{template_key}", position)
        union.union(previous, position)
    for position, business_key in enumerate(business_keys.astype(str).tolist()):
        if not business_key:
            continue
        previous = first_by_key.setdefault(f"business:{business_key}", position)
        union.union(previous, position)
    return union.keys("connected")


def _business_group_key(value: Any) -> str:
    if _is_missing(value):
        return ""
    payload = {"type": type(value).__name__, "value": str(value)}
    return _json_digest(payload)


def _validate_partition_positions(row_count: int, train: np.ndarray, holdout: np.ndarray) -> None:
    if not len(train) or not len(holdout):
        raise ValidationError("Text evidence requires non-empty training and holdout partitions.")
    all_positions = np.concatenate([train, holdout])
    if len(set(all_positions.tolist())) != len(all_positions) or min(all_positions) < 0 or max(all_positions) >= row_count:
        raise ValidationError("Text evidence partition positions are invalid or overlapping.")


def _partition_overlap(values: pd.Series, train: np.ndarray, holdout: np.ndarray) -> int:
    train_values = {value for value in values.iloc[train].astype(str).tolist() if value}
    holdout_values = {value for value in values.iloc[holdout].astype(str).tolist() if value}
    return len(train_values & holdout_values)


def _collapsed_count(values: Sequence[str], *, ignore_empty: bool) -> int:
    selected = [value for value in values if value or not ignore_empty]
    return len(selected) - len(set(selected))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _json_digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ordered_digest(values: Sequence[str]) -> str:
    return _json_digest(list(values))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
