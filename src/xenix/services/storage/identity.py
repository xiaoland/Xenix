"""Database-owned object numbers shared by every business table.

Ordinary inserts allocate in their transaction. Reserve numbers before
publishing an identity that must survive a later object transaction failing.
Reservations commit immediately, so abandoned numbers leave gaps.
"""

from sqlalchemy import Column, Integer, Table
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel


object_id_sequence = Table(
    "object_id_sequence", SQLModel.metadata,
    Column("singleton", Integer, primary_key=True),
    Column("last_id", Integer, nullable=False),
)


def allocate_ids(connection: Connection, count: int = 1) -> range:
    """Allocate in the caller's transaction; commit determines durability."""
    if count < 1:
        raise ValueError("An identity allocation must contain at least one number.")
    connection.exec_driver_sql(
        "INSERT OR IGNORE INTO object_id_sequence (singleton, last_id) VALUES (1, 0)"
    )
    last = connection.exec_driver_sql(
        "UPDATE object_id_sequence SET last_id = last_id + ? "
        "WHERE singleton = 1 RETURNING last_id", (count,),
    ).scalar_one()
    return range(last - count + 1, last + 1)


def reserve_ids(session_factory: sessionmaker, count: int = 1) -> range:
    """Commit a reservation before starting file work, tools or object writes."""
    with session_factory() as session:
        numbers = allocate_ids(session.connection(), count)
        session.commit()
        return numbers


def next_identity(context: ExecutionContext) -> int:
    return allocate_ids(context.connection)[0]


def identity_column(*, primary_key: bool = False, index: bool = False) -> Column:
    """Assign the integer on flush, using the object's actual storage connection."""
    return Column(
        Integer, primary_key=primary_key, index=index, nullable=False,
        autoincrement=False, default=next_identity,
    )
