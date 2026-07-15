from __future__ import annotations

import logging
import threading
from pathlib import Path

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import AgentHarnessService, DatasetAttachmentInput, SubmitUserTurnInput
from xenix.services.llm import (
    AppendUserMessageInput,
    LLMConversationService,
    ProviderResponse,
    SourceAttachmentBlock,
    TextBlock,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import ConversationMessageKind, ConversationMessageRow


class _PrimaryTextProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def complete(self, messages, tools) -> ProviderResponse:
        self.calls.append((messages, tools))
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": "Done."}])


class _TitleModelGateway:
    def __init__(
        self,
        *,
        fq_model_key: str | None = "titles/compact",
        output: str | None = "Generated title",
        failure: Exception | None = None,
        started: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self._fq_model_key = fq_model_key
        self._output = output
        self._failure = failure
        self._started = started
        self._release = release
        self.calls: list[dict[str, object]] = []

    def thread_title_fq_model_key(self) -> str | None:
        return self._fq_model_key

    def complete(self, *, fq_model_key, messages, tools, retry_callback=None) -> ProviderResponse:
        self.calls.append(
            {
                "fq_model_key": fq_model_key,
                "messages": messages,
                "tools": tools,
                "retry_callback": retry_callback,
            }
        )
        if self._started is not None:
            self._started.set()
        if self._release is not None and not self._release.wait(timeout=5):
            raise AssertionError("Title-model test barrier timed out.")
        if self._failure is not None:
            raise self._failure
        if self._output is None:
            return ProviderResponse()
        return ProviderResponse(assistant_content_blocks=[{"type": "text", "text": self._output}])


def _harness(monkeypatch, tmp_path: Path, title_gateway: _TitleModelGateway):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    context = StorageBootstrapService().initialize(ensure_app_dirs(get_app_paths()))
    conversation = LLMConversationService(
        session_factory=context.session_factory,
        llm_service=title_gateway,  # type: ignore[arg-type]
    )
    primary = _PrimaryTextProvider()
    return AgentHarnessService(conversation_service=conversation, provider=primary), conversation, primary


def test_precreated_empty_thread_uses_independent_title_model_after_canonical_append(monkeypatch, tmp_path: Path) -> None:
    title_gateway = _TitleModelGateway(output='"Customer segmentation."')
    harness, _conversation, primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = harness.create_thread(fq_model_key="primary/conversation")

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread.thread.id,
            text="Group customers into practical market segments.",
            dataset_attachments=[
                DatasetAttachmentInput(
                    dataset_id="dataset-1",
                    name="Customer accounts",
                    file_name="customers.csv",
                    source_format="csv",
                    row_count=24,
                    column_count=4,
                )
            ],
        )
    )

    assert snapshot.thread.title == "Customer segmentation"
    assert snapshot.thread.selected_fq_model_key == "primary/conversation"
    assert [message.kind for message in snapshot.messages] == [
        ConversationMessageKind.USER,
        ConversationMessageKind.ASSISTANT,
    ]
    assert len(title_gateway.calls) == 1
    title_call = title_gateway.calls[0]
    assert title_call["fq_model_key"] == "titles/compact"
    assert title_call["tools"] == []
    title_prompt = title_call["messages"][1].content
    assert "Group customers into practical market segments." in title_prompt
    assert "Attached dataset (Customer accounts" in title_prompt
    assert len(primary.calls) == 1


def test_implicit_thread_uses_the_same_post_append_auto_title_flow(monkeypatch, tmp_path: Path) -> None:
    title_gateway = _TitleModelGateway(output="Churn risk review")
    harness, _conversation, _primary = _harness(monkeypatch, tmp_path, title_gateway)

    snapshot = harness.submit_user_turn(SubmitUserTurnInput(text="Why did churn increase last month?"))

    assert snapshot.thread.title == "Churn risk review"
    assert len(title_gateway.calls) == 1
    assert "Why did churn increase last month?" in title_gateway.calls[0]["messages"][1].content


def test_initial_title_falls_back_from_canonical_attachment_when_title_model_is_unconfigured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    title_gateway = _TitleModelGateway(fq_model_key=None)
    harness, _conversation, primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = harness.create_thread()

    snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(
            thread_id=thread.thread.id,
            text="",
            dataset_attachments=[
                DatasetAttachmentInput(
                    dataset_id="dataset-1",
                    name="Orders",
                    file_name="orders.csv",
                    source_format="csv",
                    row_count=12,
                    column_count=3,
                )
            ],
        )
    )

    assert snapshot.thread.title == "Orders"
    assert title_gateway.calls == []
    assert len(primary.calls) == 1


def test_initial_title_source_attachment_fallback_uses_only_safe_canonical_metadata(monkeypatch, tmp_path: Path) -> None:
    title_gateway = _TitleModelGateway(fq_model_key=None)
    _harness_service, conversation, _primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = conversation.create_thread()
    claim = conversation.claim_user_submission(
        thread_id=thread.thread.id,
        expected_frontier_id=None,
        client_submission_id="source-attachment-title",
    )
    try:
        # SourceAttachmentBlock is a legacy persisted projection.  Seed the
        # historical row directly so this test exercises the read/title path,
        # while new append commands remain structurally rejected.
        with conversation._session_factory() as session:  # type: ignore[union-attr]
            conversation._repository.append_message(
                session,
                ConversationMessageRow(
                    thread_id=thread.thread.id,
                    sequence_index=0,
                    kind=ConversationMessageKind.USER,
                    client_submission_id=claim.client_submission_id,
                    content_payload={
                        "blocks": [
                            {
                                "type": "source_attachment",
                                "artifact_id": "artifact-1",
                                "file_name": r"C:\private\sales-report.xlsx",
                                "source_format": "xlsx",
                            }
                        ]
                    },
                ),
            )
            session.commit()
        appended = conversation.get_thread_snapshot(thread.thread.id)
    finally:
        conversation.release_user_submission_claim(claim)

    snapshot = conversation.auto_title_initial_thread(
        claim=claim,
        first_user_message_id=appended.messages[-1].id,
    )

    assert snapshot.thread.title == "sales-report"
    assert title_gateway.calls == []


@pytest.mark.parametrize(
    ("output", "failure"),
    [
        ("", None),
        (None, RuntimeError("title endpoint unavailable")),
    ],
)
def test_initial_title_model_error_or_empty_output_uses_fallback_without_blocking_sampling(
    monkeypatch,
    tmp_path: Path,
    caplog,
    output: str | None,
    failure: Exception | None,
) -> None:
    title_gateway = _TitleModelGateway(output=output, failure=failure)
    harness, _conversation, primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = harness.create_thread()

    with caplog.at_level(logging.WARNING, logger="xenix.services.llm.conversation"):
        snapshot = harness.submit_user_turn(
            SubmitUserTurnInput(
                thread_id=thread.thread.id,
                text="Analyze weekly revenue by region and product.",
            )
        )

    assert snapshot.thread.title == "Analyze weekly revenue by region and product"
    assert len(title_gateway.calls) == 1
    assert len(primary.calls) == 1
    assert "Initial Thread title model failed" in caplog.text
    assert [message.kind for message in snapshot.messages] == [
        ConversationMessageKind.USER,
        ConversationMessageKind.ASSISTANT,
    ]


def test_existing_manual_or_historical_thread_is_never_auto_titled(monkeypatch, tmp_path: Path) -> None:
    title_gateway = _TitleModelGateway(failure=AssertionError("title model must not be called"))
    harness, conversation, primary = _harness(monkeypatch, tmp_path, title_gateway)

    manually_named = harness.create_thread(title="Manual title")
    manual_snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(thread_id=manually_named.thread.id, text="Do not replace my title.")
    )

    historical = conversation.create_thread()
    first = conversation.append_user_message(
        AppendUserMessageInput(
            thread_id=historical.thread.id,
            client_submission_id="historic-first",
            content_blocks=[TextBlock("Persisted before automatic naming existed.")],
        )
    )
    pending = conversation.sample_existing_frontier(
        thread_id=historical.thread.id,
        expected_frontier_id=first.messages[-1].id,
        provider=primary,
    )
    conversation.finalize_pending_assistant(pending.pending_message_id)
    historical_snapshot = harness.submit_user_turn(
        SubmitUserTurnInput(thread_id=historical.thread.id, text="Continue the existing conversation.")
    )

    assert manual_snapshot.thread.title == "Manual title"
    assert historical_snapshot.thread.title is None
    assert title_gateway.calls == []


def test_manual_title_generation_remains_a_non_persisting_model_proposal(monkeypatch, tmp_path: Path) -> None:
    title_gateway = _TitleModelGateway(output="Quarterly revenue review")
    harness, conversation, primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = conversation.create_thread()
    first = conversation.append_user_message(
        AppendUserMessageInput(
            thread_id=thread.thread.id,
            client_submission_id="manual-proposal-first",
            content_blocks=[TextBlock("Summarize this quarter's revenue.")],
        )
    )
    pending = conversation.sample_existing_frontier(
        thread_id=thread.thread.id,
        expected_frontier_id=first.messages[-1].id,
        provider=primary,
    )
    conversation.finalize_pending_assistant(pending.pending_message_id)

    proposal = harness.generate_thread_title(thread.thread.id)

    assert proposal == "Quarterly revenue review"
    assert conversation.get_thread_snapshot(thread.thread.id).thread.title is None
    assert len(title_gateway.calls) == 1
    assert "Summarize this quarter's revenue." in title_gateway.calls[0]["messages"][1].content


def test_manual_rename_wins_while_title_model_is_running(monkeypatch, tmp_path: Path) -> None:
    title_started = threading.Event()
    release_title = threading.Event()
    title_gateway = _TitleModelGateway(
        output="Automatic title",
        started=title_started,
        release=release_title,
    )
    harness, _conversation, _primary = _harness(monkeypatch, tmp_path, title_gateway)
    thread = harness.create_thread()
    submitted: list[object] = []
    errors: list[Exception] = []

    def submit() -> None:
        try:
            submitted.append(
                harness.submit_user_turn(
                    SubmitUserTurnInput(thread_id=thread.thread.id, text="Draft a quarterly review.")
                )
            )
        except Exception as exc:  # Surface worker failures in the test thread.
            errors.append(exc)

    submission_thread = threading.Thread(target=submit, daemon=True)
    submission_thread.start()
    assert title_started.wait(timeout=2)

    renamed: list[object] = []
    rename_done = threading.Event()

    def rename() -> None:
        try:
            renamed.append(harness.rename_thread(thread.thread.id, "Manual title"))
        finally:
            rename_done.set()

    rename_thread = threading.Thread(target=rename, daemon=True)
    rename_thread.start()
    try:
        assert rename_done.wait(timeout=2), "Manual rename must not wait for title-model I/O."
    finally:
        release_title.set()

    submission_thread.join(timeout=3)
    rename_thread.join(timeout=3)

    assert not submission_thread.is_alive()
    assert not rename_thread.is_alive()
    assert errors == []
    assert renamed[0].thread.title == "Manual title"
    assert submitted[0].thread.title == "Manual title"
    assert harness.get_thread_snapshot(thread.thread.id).thread.title == "Manual title"
