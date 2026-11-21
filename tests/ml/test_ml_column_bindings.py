from pathlib import Path

import pytest

from xenix.config import AppPaths
from xenix.exceptions import ValidationError
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_column_bindings import ColumnBindingService, CreateColumnBindingInput
from xenix.services.storage import StorageContext


@pytest.fixture
def binding_dataset(
    storage: StorageContext, app_paths: AppPaths, tmp_path: Path
) -> tuple[ColumnBindingService, int]:
    source = tmp_path / "sales.csv"
    source.write_text("Region,Monthly Sales,Target\nNorth,120,1\nSouth,90,0\n", encoding="utf-8")
    datasets = DatasetService(storage.session_factory, app_paths)
    dataset = datasets.register_dataset(RegisterDatasetInput(source_path=str(source)))
    return ColumnBindingService(storage.session_factory, datasets), dataset.id


def test_column_indexes_bind_exact_names_in_requested_order(
    binding_dataset: tuple[ColumnBindingService, int],
) -> None:
    service, dataset_id = binding_dataset
    binding = service.create(
        CreateColumnBindingInput(
            dataset_id=dataset_id,
            model_key="classification.logistic_regression",
            role_bindings=[
                {"role": "feature", "column_indexes": [1, 0]},
                {"role": "target", "column_indexes": [2]},
            ],
        )
    )

    saved = service.get(binding.id)
    assert [(role["role"], role["columns"]) for role in saved.role_bindings] == [
        ("feature", ["Monthly Sales", "Region"]),
        ("target", ["Target"]),
    ]


def test_missing_column_suggests_its_exact_available_name(
    binding_dataset: tuple[ColumnBindingService, int],
) -> None:
    service, dataset_id = binding_dataset
    with pytest.raises(ValidationError) as caught:
        service.create(
            CreateColumnBindingInput(
                dataset_id=dataset_id,
                role_bindings=[{"role": "feature", "columns": ["monthly sale"]}],
            )
        )

    assert str(caught.value) == (
        "Bound columns must exist in the dataset.\n"
        "Missing columns for role 'feature': `monthly sale`.\n"
        "Closest available column suggestions:\n"
        "- `monthly sale` -> `Monthly Sales`\n"
        "Available columns: `Region`, `Monthly Sales`, `Target`.\n"
        "Use the exact column names returned by data.query or dataset inspection."
    )


@pytest.mark.parametrize(
    ("other_role", "other_column", "message"),
    [
        ("feature", "Monthly Sales", "Duplicate column role binding 'feature' is not allowed."),
        ("target", "Region", "Column 'Region' cannot be bound to multiple roles: 'feature' and 'target'."),
    ],
)
def test_repeated_roles_or_columns_are_rejected(
    binding_dataset: tuple[ColumnBindingService, int],
    other_role: str,
    other_column: str,
    message: str,
) -> None:
    service, dataset_id = binding_dataset
    with pytest.raises(ValidationError) as caught:
        service.create(
            CreateColumnBindingInput(
                dataset_id=dataset_id,
                role_bindings=[
                    {"role": "feature", "columns": ["Region"]},
                    {"role": other_role, "columns": [other_column]},
                ],
            )
        )

    assert str(caught.value) == message
