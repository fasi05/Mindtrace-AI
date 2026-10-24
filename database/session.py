"""Engine creation and schema initialisation (documented strategy: create_all + schema_info version row)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from database.models import SCHEMA_VERSION, Base, SchemaInfo


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _):  # enforce foreign keys on SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def init_schema(engine: Engine) -> None:
    """Idempotent: creates missing tables and records the schema version."""
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as s:
        row = s.scalars(select(SchemaInfo)).first()
        if row is None:
            s.add(SchemaInfo(id=1, version=SCHEMA_VERSION))


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
