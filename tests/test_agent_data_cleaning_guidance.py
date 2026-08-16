from __future__ import annotations

from unittest.mock import Mock

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent.skill_catalog import AgentSkillCatalog
from xenix.services.agent.tools import AgentToolRegistry


def test_cleaning_provider_contract_declares_order_and_filter_authority(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    registry = AgentToolRegistry(
        paths=paths,
        dataset_service=Mock(),
        data_cleaning_service=Mock(),
        data_transform_service=Mock(),
        ml_service=Mock(),
        artifact_service=Mock(),
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    clean_spec = specs["data.clean"]
    transform_spec = specs["data.transform"]
    operations_schema = clean_spec.parameters_schema["properties"]["operations"]
    operation_schema = operations_schema["items"]["properties"]

    assert "strictly left-to-right" in operations_schema["description"]
    assert "current intermediate dataset" in operation_schema["operation"]["description"]
    assert "current intermediate dataset" in operation_schema["params"]["description"]
    assert "When an operation selects columns" in operation_schema["params"]["description"]
    assert "validation operations for supported row checks" in clean_spec.description
    assert "Use data.transform for a filter only when no atomic data.clean operation" in clean_spec.description
    assert "use an advertised atomic data.clean validation operation" in transform_spec.description
    assert "unsupported predicates" in transform_spec.description


def test_preprocessing_skill_catalog_owns_routine_cleaning_route() -> None:
    catalog = AgentSkillCatalog.from_default_catalog()
    skill = next(
        skill
        for skill in catalog.list_skills()
        if skill.name == "xenix-data-preprocessing"
    )

    assert skill.metadata["metadata"]["version"] == "0.6.0"
    assert "strictly left-to-right" in skill.body
    assert "validation.non_negative" in skill.body
    assert "text.lowercase" in skill.body
    assert "reimplement these rules in `data.transform`" in skill.body
    reference = skill.resources["references"]["references/preprocessing-tools.md"]
    assert "validation row\nrejection before median fill" in reference
    assert "unsupported predicates" in reference
    assert "do not run\na broad source-row query" in reference
    assert "SELECT * FROM input LIMIT 50" not in reference
    assert "Start with `analysis.profile`" in reference
    assert "start with one compact schema/sample query" not in reference
