from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


ColumnIndex = Annotated[int, Field(strict=True, ge=0)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
TokenizerProfile = Literal["zh_business_v1", "multilingual_business_v1"]
PhraseMode = Literal["unigram", "unigram_bigram"]


class StagedTextResourceInput(BaseModel):
    """A registered Dataset staged to a worker-local, integrity-checked file."""

    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str = Field(min_length=1, max_length=128)
    absolute_path: str = Field(min_length=1)
    source_sha256: Sha256


class TextPreparationInput(BaseModel):
    """Narrow preparation command accepted after Dataset references are staged."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tokenizer_profile: TokenizerProfile = "multilingual_business_v1"
    phrase_mode: PhraseMode = "unigram"
    custom_dictionary_resources: list[StagedTextResourceInput] = Field(default_factory=list, max_length=4)
    stopword_resources: list[StagedTextResourceInput] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def _resource_dataset_roles_must_be_unambiguous(self) -> Self:
        dictionary_ids = [resource.dataset_id for resource in self.custom_dictionary_resources]
        stopword_ids = [resource.dataset_id for resource in self.stopword_resources]
        if len(dictionary_ids) != len(set(dictionary_ids)) or len(stopword_ids) != len(set(stopword_ids)):
            raise ValueError("Text preparation resource Dataset IDs cannot contain duplicates.")
        if set(dictionary_ids) & set(stopword_ids):
            raise ValueError("A text resource Dataset cannot be both a custom dictionary and a stopword list.")
        return self


class TokenizeDatasetInput(TextPreparationInput):
    """Validated command passed from the Agent boundary into tokenization."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_path: str
    name: str
    text_column: str | None = None
    text_column_index: ColumnIndex | None = None
    output: Literal["token_text", "token_rows"] = "token_text"
    tokenizer_profile: TokenizerProfile = "zh_business_v1"
    id_columns: list[str] | None = None
    id_column_indexes: list[ColumnIndex] | None = None


class TokenizeDatasetResult(BaseModel):
    output_path: str
    report: dict[str, object] = Field(default_factory=dict)
