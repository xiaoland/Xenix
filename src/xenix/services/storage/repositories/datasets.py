from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import and_, exists, or_
from sqlmodel import Session, select

from ..models import (
    DatasetColumnBindingRow,
    DatasetDerivationInputRow,
    DatasetDerivationRow,
    DatasetImportRow,
    DatasetRow,
    DatasetWorkbookRow,
    MLTaskRow,
    TrainedModelRow,
)


class DatasetRepository:
    def create(self, session: Session, row: DatasetRow) -> DatasetRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get(self, session: Session, dataset_id: str) -> DatasetRow | None:
        return session.get(DatasetRow, dataset_id)

    def list_by_project(self, session: Session, project_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(DatasetRow.project_id == project_id)
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_all(self, session: Session) -> list[DatasetRow]:
        statement = select(DatasetRow).order_by(DatasetRow.created_at)
        return list(session.exec(statement))

    # Source datasets carry no provenance marker (copied_from,
    # derived_from_dataset_id, and ml_task_id all NULL, and no derivation row);
    # copies carry copied_from; generated datasets carry derived_from_dataset_id,
    # ml_task_id, or a derivation row. The list families must partition rows.
    def list_source_by_project(self, session: Session, project_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(
                and_(
                    DatasetRow.project_id == project_id,
                    DatasetRow.copied_from.is_(None),
                    DatasetRow.derived_from_dataset_id.is_(None),
                    DatasetRow.ml_task_id.is_(None),
                    ~exists().where(DatasetDerivationRow.dataset_id == DatasetRow.id),
                )
            )
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_sources(self, session: Session) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(
                and_(
                    DatasetRow.copied_from.is_(None),
                    DatasetRow.derived_from_dataset_id.is_(None),
                    DatasetRow.ml_task_id.is_(None),
                    ~exists().where(DatasetDerivationRow.dataset_id == DatasetRow.id),
                )
            )
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_generated_by_project(self, session: Session, project_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(
                and_(
                    DatasetRow.project_id == project_id,
                    or_(
                        DatasetRow.ml_task_id.is_not(None),
                        DatasetRow.derived_from_dataset_id.is_not(None),
                        exists().where(DatasetDerivationRow.dataset_id == DatasetRow.id),
                    ),
                )
            )
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_generated(self, session: Session) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(
                or_(
                    DatasetRow.ml_task_id.is_not(None),
                    DatasetRow.derived_from_dataset_id.is_not(None),
                    exists().where(DatasetDerivationRow.dataset_id == DatasetRow.id),
                )
            )
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_copies_by_source(self, session: Session, source_dataset_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(DatasetRow.copied_from == source_dataset_id)
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def list_derived_by_source(self, session: Session, source_dataset_id: str) -> list[DatasetRow]:
        statement = (
            select(DatasetRow)
            .where(
                or_(
                    DatasetRow.derived_from_dataset_id == source_dataset_id,
                    DatasetRow.id.in_(
                        select(DatasetDerivationInputRow.derivation_dataset_id).where(
                            DatasetDerivationInputRow.input_dataset_id == source_dataset_id
                        )
                    ),
                )
            )
            .order_by(DatasetRow.created_at)
        )
        return list(session.exec(statement))

    def get_by_ml_task(self, session: Session, ml_task_id: str) -> DatasetRow | None:
        statement = select(DatasetRow).where(DatasetRow.ml_task_id == ml_task_id)
        return session.exec(statement).first()

    def rename(self, session: Session, dataset_id: str, new_name: str, now: datetime) -> DatasetRow | None:
        row = self.get(session, dataset_id)
        if row is None:
            return None

        row.name = new_name
        row.updated_at = now
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def delete(self, session: Session, row: DatasetRow) -> None:
        session.delete(row)
        session.flush()

    # ------------------------------------------------------------------
    # Import provenance
    # ------------------------------------------------------------------

    def create_import(self, session: Session, row: DatasetImportRow) -> DatasetImportRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def create_workbook(self, session: Session, row: DatasetWorkbookRow) -> DatasetWorkbookRow:
        session.add(row)
        session.flush()
        session.refresh(row)
        return row

    def get_import(self, session: Session, import_id: str) -> DatasetImportRow | None:
        return session.get(DatasetImportRow, import_id)

    # ------------------------------------------------------------------
    # Derivation provenance
    # ------------------------------------------------------------------

    def get_derivation(self, session: Session, dataset_id: str) -> DatasetDerivationRow | None:
        return session.get(DatasetDerivationRow, dataset_id)

    def list_derivations_by_tool_calls(
        self, session: Session, tool_call_message_ids: Collection[str],
    ) -> list[DatasetDerivationRow]:
        statement = (
            select(DatasetDerivationRow)
            .where(DatasetDerivationRow.tool_call_message_id.in_(tool_call_message_ids))
            .order_by(DatasetDerivationRow.created_at, DatasetDerivationRow.dataset_id)
        )
        return list(session.exec(statement))

    def list_derivation_inputs(
        self, session: Session, dataset_id: str,
    ) -> list[DatasetDerivationInputRow]:
        statement = (
            select(DatasetDerivationInputRow)
            .where(DatasetDerivationInputRow.derivation_dataset_id == dataset_id)
            .order_by(DatasetDerivationInputRow.input_position)
        )
        return list(session.exec(statement))

    def list_derivation_input_ids(
        self, session: Session, dataset_id: str,
    ) -> list[str]:
        statement = select(DatasetDerivationInputRow.input_dataset_id).where(
            DatasetDerivationInputRow.derivation_dataset_id == dataset_id,
        )
        return [row for row in session.exec(statement)]

    def create_derivation(
        self,
        session: Session,
        *,
        derivation: DatasetDerivationRow,
        inputs: list[DatasetDerivationInputRow],
    ) -> None:
        session.add(derivation)
        session.flush()
        for input_row in inputs:
            session.add(input_row)
        session.flush()

    def has_references(self, session: Session, dataset_id: str) -> bool:
        reference_statements = [
            select(DatasetRow.id).where(DatasetRow.copied_from == dataset_id),
            select(DatasetRow.id).where(DatasetRow.derived_from_dataset_id == dataset_id),
            select(DatasetDerivationInputRow.id).where(
                DatasetDerivationInputRow.input_dataset_id == dataset_id,
            ),
            select(DatasetColumnBindingRow.id).where(
                DatasetColumnBindingRow.dataset_id == dataset_id,
            ),
            select(MLTaskRow.id).where(MLTaskRow.dataset_id == dataset_id),
            select(TrainedModelRow.id).where(TrainedModelRow.dataset_id == dataset_id),
        ]
        return any(session.exec(statement).first() is not None for statement in reference_statements)

    def delete_derivation(self, session: Session, dataset_id: str) -> None:
        input_rows = session.exec(
            select(DatasetDerivationInputRow).where(
                DatasetDerivationInputRow.derivation_dataset_id == dataset_id,
            ),
        )
        for row in input_rows:
            session.delete(row)
        derivation = session.get(DatasetDerivationRow, dataset_id)
        if derivation is not None:
            session.delete(derivation)
        session.flush()
