from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError as PydanticValidationError

from xenix.config import AppPaths
from xenix.exceptions import ValidationError
from xenix.services.data_tokenization import DataTokenizationService
from xenix.services.data_tokenization_contracts import (
    StagedTextResourceInput,
    TextPreparationInput,
    TokenizeDatasetInput,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ml_rt_service" / "text_classification"


def _paths(root: Path) -> AppPaths:
    return AppPaths(
        home=root,
        config=root / "config",
        logs=root / "logs",
        cache=root / "cache",
        state=root / "state",
        temp=root / "temp",
        artifacts=root / "artifacts",
        resources=root / "resources",
    )


def _resource(path: Path, dataset_id: str) -> StagedTextResourceInput:
    return StagedTextResourceInput(
        dataset_id=dataset_id,
        absolute_path=str(path.resolve()),
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_legacy_zh_business_profile_remains_byte_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "legacy.csv"
    source.write_text("id,text\n1,产品质量 Stable\n2,物流速度 FAST\n", encoding="utf-8")
    service = DataTokenizationService(_paths(tmp_path))
    request = TokenizeDatasetInput(
        source_path=str(source.resolve()),
        name="legacy",
        text_column="text",
        tokenizer_profile="zh_business_v1",
    )

    first = service.tokenize_dataset(request)
    second = service.tokenize_dataset(request)

    first_bytes = Path(first.output_path).read_bytes()
    assert first_bytes == Path(second.output_path).read_bytes()
    output = pd.read_csv(first.output_path)
    assert output["token_text"].tolist() == ["产品质量 stable", "物流 速度 fast"]
    assert first.report["tokenizer_profile"] == "zh_business_v1"
    assert "preparation_specification" not in first.report


def test_multilingual_profile_retains_safe_spec_and_bilingual_quality(tmp_path: Path) -> None:
    source = tmp_path / "bilingual.csv"
    source.write_text(
        "id,text\n"
        "1,诺华臻享 service 很满意 Order １２３\n"
        "2,NovaCare SERVICE arrived via https://example.com\n"
        "3,\n",
        encoding="utf-8",
    )
    dictionary = FIXTURE_ROOT / "custom_dictionary.csv"
    stopwords = FIXTURE_ROOT / "stopwords.csv"
    service = DataTokenizationService(_paths(tmp_path))
    request = TokenizeDatasetInput(
        source_path=str(source.resolve()),
        name="bilingual",
        text_column="text",
        tokenizer_profile="multilingual_business_v1",
        phrase_mode="unigram_bigram",
        custom_dictionary_resources=[_resource(dictionary, "dictionary-dataset")],
        stopword_resources=[_resource(stopwords, "stopword-dataset")],
    )

    result = service.tokenize_dataset(request)
    output = pd.read_csv(result.output_path).fillna("")
    report_json = json.dumps(result.report, ensure_ascii=False, sort_keys=True)

    assert "诺华臻享" in output.loc[0, "token_text"]
    assert "novacare" in output.loc[1, "token_text"]
    assert "service" not in " ".join(output["token_text"].tolist())
    assert "number" in output.loc[0, "token_text"]
    assert "url" in output.loc[1, "token_text"]
    assert result.report["empty_token_row_count"] == 1
    specification = result.report["preparation_specification"]
    assert isinstance(specification, dict)
    assert specification["profile_key"] == "multilingual_business_v1"
    assert specification["ngram_max"] == 2
    assert str(dictionary.resolve()) not in report_json
    assert str(stopwords.resolve()) not in report_json
    assert "诺华臻享" not in report_json
    assert "NovaCare" not in report_json


def test_staged_text_resources_fail_closed_on_digest_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("text\nhello world\n", encoding="utf-8")
    dictionary = FIXTURE_ROOT / "custom_dictionary.csv"
    service = DataTokenizationService(_paths(tmp_path))
    request = TokenizeDatasetInput(
        source_path=str(source.resolve()),
        name="invalid-resource",
        text_column="text",
        tokenizer_profile="multilingual_business_v1",
        custom_dictionary_resources=[
            StagedTextResourceInput(
                dataset_id="dictionary-dataset",
                absolute_path=str(dictionary.resolve()),
                source_sha256="0" * 64,
            )
        ],
    )

    with pytest.raises(ValidationError, match="SHA-256 integrity"):
        service.tokenize_dataset(request)


def test_tokenization_contract_rejects_unversioned_profiles_and_ambiguous_resources() -> None:
    with pytest.raises(PydanticValidationError):
        TokenizeDatasetInput.model_validate(
            {
                "source_path": "C:/source.csv",
                "name": "unknown",
                "text_column": "text",
                "tokenizer_profile": "unversioned-profile",
            }
        )
    resource = _resource(FIXTURE_ROOT / "custom_dictionary.csv", "shared-resource")
    with pytest.raises(PydanticValidationError, match="both a custom dictionary and a stopword"):
        TextPreparationInput(
            custom_dictionary_resources=[resource],
            stopword_resources=[resource],
        )
