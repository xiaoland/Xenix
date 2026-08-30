from __future__ import annotations

import unicodedata

from docling_core.types.doc import DocItemLabel, DoclingDocument

from xenix.services.knowledge_derivation_service import _knowledge_units
from xenix.services.knowledge_service import (
    KNOWLEDGE_UNIT_OVERLAP_CHARS,
    MAX_KNOWLEDGE_UNIT_CHARS,
    KnowledgeUnitInput,
    bound_knowledge_units,
)


def test_derivation_carries_heading_hierarchy_into_units() -> None:
    document = DoclingDocument(name="handbook")
    document.add_heading("Operations", level=1)
    document.add_heading("Escalation", level=2)
    document.add_text(DocItemLabel.PARAGRAPH, "Call the duty manager.")
    document.add_heading("Recovery", level=2)
    document.add_text(DocItemLabel.PARAGRAPH, "Restore from the verified snapshot.")

    units = _knowledge_units(document)

    assert units[0].locator["heading_path"] == ["Operations", "Escalation"]
    assert units[0].text.startswith("Operations > Escalation\n\n")
    assert units[1].locator["heading_path"] == ["Operations", "Recovery"]
    assert "Escalation" not in units[1].text


def test_long_units_use_bounded_sentence_aware_overlap() -> None:
    sentence = "A reliable operational sentence has enough detail to be useful. "
    source = sentence * 180
    chunks = bound_knowledge_units([KnowledgeUnitInput(source)])

    assert len(chunks) > 1
    assert all(len(unicodedata.normalize("NFKC", chunk.text)) <= MAX_KNOWLEDGE_UNIT_CHARS for chunk in chunks)
    shared = set(chunks[0].text.split()).intersection(chunks[1].text.split())
    assert shared
    assert len(chunks[0].text) - chunks[1].text.find(sentence.strip()) >= 0


def test_overlap_never_stalls_on_unbroken_text() -> None:
    source = "x" * (MAX_KNOWLEDGE_UNIT_CHARS * 3 + 17)

    chunks = bound_knowledge_units([KnowledgeUnitInput(source)])

    assert len(chunks) >= 3
    assert all(chunk.text for chunk in chunks)
    assert all(len(chunk.text) <= MAX_KNOWLEDGE_UNIT_CHARS for chunk in chunks)


def test_nfkc_expansion_respects_normalized_budget() -> None:
    source = "\ufb03" * (MAX_KNOWLEDGE_UNIT_CHARS + 100)

    chunks = bound_knowledge_units([KnowledgeUnitInput(source)])

    assert len(chunks) > 1
    assert all(
        len(unicodedata.normalize("NFKC", chunk.text)) <= MAX_KNOWLEDGE_UNIT_CHARS
        for chunk in chunks
    )


def test_overlap_is_bounded() -> None:
    source = ("alpha beta gamma delta. " * 400).strip()
    chunks = bound_knowledge_units([KnowledgeUnitInput(source)])

    for previous, current in zip(chunks, chunks[1:], strict=False):
        maximum_probe = current.text[: KNOWLEDGE_UNIT_OVERLAP_CHARS + 80]
        assert maximum_probe
        assert any(word in previous.text for word in maximum_probe.split())
