"""Delivery checkpoints for the business task portfolio.

Only artifacts actually linked in a settled answer are inspected. Tables and
public model facts are copied before the next user request can revise them.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations
import json
import math
from pathlib import Path
import re
from typing import Any

import polars as pl

from xenix.exceptions import NotFoundError, ValidationError
from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput
from xenix.services.dataset_inspection import detect_source_format
from xenix.services.tabular import load_tabular_frame

from .case_support import canonical_completion, sha256_file, source_dataset_ids_from_snapshot
from .contracts import BenchmarkCaseContext, BenchmarkCaseServices, BenchmarkInputError, OutcomeCheck

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "business_tasks"
_ARTIFACT_URI = re.compile(r"artifact://[A-Za-z0-9-]+(?:\?[^)\s>\]]+)?")


@dataclass(frozen=True)
class DeliveredArtifact:
    uri: str
    title: str
    kind: str
    frame: pl.DataFrame | None
    report: dict[str, Any] | None
    model_id: str | None
    model_available: bool


@dataclass(frozen=True)
class Delivery:
    final_text: str
    artifacts: tuple[DeliveredArtifact, ...]
    unavailable_links: tuple[str, ...]
    completed: bool
    sources_unchanged: bool

    def report_evidence(self, turn: int) -> tuple[str, ...]:
        # These tasks own synthetic inputs, so their complete deliveries can be
        # retained locally. Legacy cases do not inherit this content policy.
        return self.judge_evidence(turn)

    def judge_evidence(self, turn: int) -> tuple[str, ...]:
        evidence = [f"user_turn={turn}; final_answer={self.final_text}"]
        for artifact in self.artifacts:
            evidence.append(
                json.dumps(
                    {
                        "user_turn": turn,
                        "uri": artifact.uri,
                        "title": artifact.title,
                        "columns": artifact.frame.columns if artifact.frame is not None else None,
                        "rows": artifact.frame.to_dicts() if artifact.frame is not None else None,
                        "report": artifact.report,
                        "saved_model_id": artifact.model_id,
                        "saved_model_available": artifact.model_available,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
        if self.unavailable_links:
            evidence.append(f"unavailable_deliveries={self.unavailable_links}")
        return tuple(evidence)


class BusinessTask:
    """Fixed business requests; subsequent requests never contain oracle answers."""

    task: str
    attachments: tuple[tuple[str, ...], ...]

    def __init__(self, variant: str = "standard") -> None:
        self.folder = FIXTURE_ROOT / self.task / variant
        self.case_id = f"business.{self.task}.v1.{variant}"
        self._external_hashes: dict[Path, str] = {}
        self._registered_hashes: dict[str, str] = {}

    def validate_input(self) -> str:
        required = [self.folder / name for names in self.attachments for name in names]
        required.extend(self.folder / f"request_{i}.txt" for i in range(1, len(self.attachments) + 1))
        required.append(self.folder / "oracle.json")
        if any(not path.is_file() for path in required):
            raise BenchmarkInputError("missing_business_task_input")
        self._external_hashes = {path: sha256_file(path) for path in sorted(self.folder.rglob("*")) if path.is_file()}
        return (
            sha256(
                json.dumps(
                    {str(path.relative_to(self.folder)): digest for path, digest in self._external_hashes.items()},
                    sort_keys=True,
                ).encode()
            )
            .hexdigest()
            .upper()
        )

    def build_submissions(self, *, thread_id: str, fq_model_key: str) -> tuple[SubmitUserTurnInput, ...]:
        return tuple(
            SubmitUserTurnInput(
                thread_id=thread_id,
                fq_model_key=fq_model_key,
                # The product composer imports tabular files. Business notes are
                # ordinary user text; passing .txt through Dataset import would
                # measure an invalid submission rather than the business task.
                text="\n\n".join(
                    [
                        (self.folder / f"request_{index}.txt").read_text(encoding="utf-8"),
                        *((self.folder / name).read_text(encoding="utf-8") for name in names if name.endswith(".txt")),
                    ]
                ),
                source_attachments=[
                    SourceAttachmentInput(file_path=str((self.folder / name).resolve()))
                    for name in names
                    if not name.endswith(".txt")
                ],
            )
            for index, names in enumerate(self.attachments, start=1)
        )

    def capture_source_state(self, *, snapshot: Any, services: BenchmarkCaseServices) -> None:
        # The first snapshot follows attachment import, before subject sampling.
        for dataset_id in source_dataset_ids_from_snapshot(snapshot):
            if dataset_id not in self._registered_hashes:
                self._registered_hashes[dataset_id] = sha256_file(
                    Path(services.datasets.get_dataset(dataset_id).source_path)
                )

    def capture_turn(self, *, context: BenchmarkCaseContext) -> Delivery:
        messages = list(getattr(context.snapshot, "messages", ()))
        final_text = str(getattr(messages[-1], "text", "") or "") if messages else ""
        artifacts = []
        unavailable = []
        for uri in dict.fromkeys(_ARTIFACT_URI.findall(final_text)):
            try:
                artifact = context.services.artifacts.resolve_uri(uri)
            except NotFoundError, ValidationError:
                unavailable.append(uri)
                continue
            if not artifact.exists or not artifact.ready_to_open:
                unavailable.append(uri)
                continue
            path = Path(artifact.absolute_path)
            source_format = detect_source_format(path)
            frame = None
            report = None
            if source_format.value != "unknown":
                frame = load_tabular_frame(path, source_format)
            elif path.suffix.lower() == ".json":
                report = json.loads(path.read_text(encoding="utf-8"))
            model_ids = _artifact_model_ids(artifact.metadata_payload, context)
            model_id = next(iter(model_ids)) if len(model_ids) == 1 else None
            model_available = False
            if model_id and context.services.models is not None:
                model = context.services.models.get_trained_model(model_id)
                if model is not None and Path(model.artifact_path).is_file():
                    model_available = True
            artifacts.append(
                DeliveredArtifact(
                    uri=uri,
                    title=artifact.title,
                    kind=artifact.kind.value,
                    frame=frame,
                    report=report,
                    model_id=model_id,
                    model_available=model_available,
                )
            )
        unchanged = all(
            path.is_file() and sha256_file(path) == digest for path, digest in self._external_hashes.items()
        )
        unchanged = unchanged and all(
            sha256_file(Path(context.services.datasets.get_dataset(dataset_id).source_path)) == digest
            for dataset_id, digest in self._registered_hashes.items()
        )
        return Delivery(
            final_text, tuple(artifacts), tuple(unavailable), canonical_completion(context.snapshot), unchanged
        )

    def oracle(self) -> dict[str, Any]:
        return json.loads((self.folder / "oracle.json").read_text(encoding="utf-8"))

    def intent(self) -> str:
        return "\n".join(
            (self.folder / f"request_{index}.txt").read_text(encoding="utf-8")
            for index in range(1, len(self.attachments) + 1)
        )


def deliveries(context: BenchmarkCaseContext) -> tuple[Delivery, ...]:
    return tuple(turn.evidence for turn in context.turns if isinstance(turn.evidence, Delivery))


def _artifact_model_ids(metadata: dict[str, Any], context: BenchmarkCaseContext) -> set[str]:
    """Follow public provenance so formatting a prediction table stays legitimate."""
    if context.services.models is None:
        return set()
    task_ids = {metadata["ml_task_id"]} if metadata.get("ml_task_id") else set()
    dataset_id = metadata.get("dataset_id") or metadata.get("result_dataset_id")
    pending = [dataset_id] if dataset_id else []
    seen = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        dataset = context.services.datasets.get_dataset(current)
        if dataset.ml_task_id:
            task_ids.add(dataset.ml_task_id)
        else:
            audit = context.services.datasets.get_dataset_audit(current)
            if audit is not None:
                pending.extend(item.dataset_id for item in audit.inputs)
    model_ids = set()
    for task_id in task_ids:
        details = context.services.models.get_task_details(task_id)
        model_id = (details.task.result_payload or {}).get("trained_model_id")
        if model_id:
            model_ids.add(model_id)
    return model_ids


def task_integrity(context: BenchmarkCaseContext) -> tuple[OutcomeCheck, ...]:
    observed = deliveries(context)
    return (
        OutcomeCheck(
            "source_inputs_preserved",
            bool(observed) and all(item.sources_unchanged for item in observed),
            "external_inputs_and_imported_datasets",
        ),
    )


def completion_checks(delivery: Delivery | None) -> tuple[OutcomeCheck, ...]:
    return (
        OutcomeCheck("answer_completed", delivery is not None and delivery.completed, "terminal_assistant_answer"),
        OutcomeCheck(
            "deliveries_accessible",
            delivery is not None and not delivery.unavailable_links,
            "linked_artifacts_readable",
        ),
    )


def task_checks(turn_checks: tuple[tuple[OutcomeCheck, ...], ...]) -> tuple[OutcomeCheck, ...]:
    return tuple(
        OutcomeCheck(f"turn_{index}.{check.name}", check.passed, check.summary)
        for index, checks in enumerate(turn_checks, 1)
        for check in checks
    )


def keyed_columns(frame: pl.DataFrame, keys: set[str]) -> tuple[str, ...]:
    """Locate an entity column without imposing a spelling or column order."""
    if frame.height != len(keys):
        return ()
    return tuple(
        column for column in frame.columns if {str(value).strip() for value in frame[column].to_list()} == keys
    )


def monetary_mapping(frame: pl.DataFrame, expected: dict[str, float], final_text: str) -> bool:
    for key_column in frame.columns:
        # A summary can include totals alongside the requested regions. Check
        # each region once; Judge assesses the meaning and accuracy of extras.
        regional = frame.filter(pl.Series([str(value).strip() in expected for value in frame[key_column].to_list()]))
        if key_column not in keyed_columns(regional, set(expected)):
            continue
        for amount_column in frame.columns:
            if amount_column == key_column:
                continue
            multiplier = 10000 if "万元" in amount_column else 1
            if re.search(r"单位[：:\s]*万元", final_text):
                multiplier = 10000
            try:
                pairs = zip(regional[key_column].to_list(), regional[amount_column].to_list(), strict=True)
                if all(
                    math.isclose(
                        float(str(value).replace(",", "").replace("，", "")) * multiplier,
                        expected[str(key).strip()],
                        rel_tol=0,
                        abs_tol=0.005,
                    )
                    for key, value in pairs
                ):
                    return True
            except TypeError, ValueError:
                continue
    return False


@dataclass(frozen=True)
class PredictionMatch:
    accuracy: float
    prediction_column: str
    label_mapping: dict[str, str]


def prediction_projections(frame: pl.DataFrame, labels: dict[str, str]) -> tuple[PredictionMatch, ...]:
    """Measure label-equivalent predictions; Judge must confirm any new encoding.

    Existing business labels retain their meaning. For alternative labels, the
    best bijection establishes a candidate fact, not proof that the user was
    given that mapping. An unexplained or contradictory encoding still fails.
    """
    matches = []
    business_labels = set(labels.values())
    for key_column in keyed_columns(frame, set(labels)):
        for prediction_column in frame.columns:
            if prediction_column == key_column:
                continue
            predictions = [str(value).strip() for value in frame[prediction_column].to_list()]
            fixed = {value: value for value in set(predictions) & business_labels}
            unknown = sorted(set(predictions) - business_labels)
            remaining = sorted(business_labels - set(fixed.values()))
            if len(unknown) > len(remaining) and not fixed:
                continue
            encodings = permutations(remaining, len(unknown)) if len(unknown) <= len(remaining) else [()]
            alternatives = []
            for encoding in encodings:
                mapping = {**fixed, **dict(zip(unknown, encoding, strict=False))}
                correct = sum(
                    mapping.get(value) == labels[str(key).strip()]
                    for key, value in zip(frame[key_column].to_list(), predictions, strict=True)
                )
                alternatives.append(PredictionMatch(correct / len(labels), prediction_column, mapping))
            matches.append(max(alternatives, key=lambda item: item.accuracy))
    return tuple(matches)
