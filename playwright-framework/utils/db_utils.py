import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from config.config import Config

logger = logging.getLogger(__name__)

_MAX_RETRIES = Config.MAX_RETRIES
_RETRY_DELAY = Config.RETRY_DELAY


class DatabaseUtils:
    """
    Database utility class built on SQLAlchemy.
    Supports SQLite (default), PostgreSQL, and MySQL via connection URL.
    Every operation retries up to MAX_RETRIES times.
    """

    def __init__(self, db_url: str = Config.DB_URL):
        self.db_url = db_url
        self._engine = None
        self._SessionFactory = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        try:
            self._engine = create_engine(self.db_url, echo=False, pool_pre_ping=True)
            self._SessionFactory = sessionmaker(bind=self._engine)
            logger.info("Database connected: %s", self.db_url)
        except SQLAlchemyError as exc:
            logger.error("Database connection failed: %s", exc)
            raise

    @contextmanager
    def _session(self):
        session: Session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("Session error — rolled back: %s", exc)
            raise
        finally:
            session.close()

    def close(self) -> None:
        if self._engine:
            self._engine.dispose()
            logger.info("Database connection closed")

    # ------------------------------------------------------------------
    # Retry engine
    # ------------------------------------------------------------------

    def _with_retry(self, operation_name: str, func, *args, **kwargs) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info("[DB Attempt %d/%d] %s", attempt, _MAX_RETRIES, operation_name)
                result = func(*args, **kwargs)
                logger.info("[DB SUCCESS] %s", operation_name)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning("[DB Attempt %d FAILED] %s — %s", attempt, operation_name, exc)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        raise RuntimeError(
            f"DB operation '{operation_name}' failed after {_MAX_RETRIES} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_table(self, ddl: str) -> None:
        def _action():
            with self._engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()

        self._with_retry("create_table", _action)
        logger.info("Table created/verified")

    def drop_table(self, table: str) -> None:
        def _action():
            with self._engine.connect() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                conn.commit()

        self._with_retry(f"drop_table({table})", _action)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def execute_query(self, query: str, params: Dict = None) -> None:
        def _action():
            with self._session() as session:
                session.execute(text(query), params or {})

        self._with_retry("execute_query", _action)

    def fetch_all(self, query: str, params: Dict = None) -> List[Dict]:
        def _action():
            with self._session() as session:
                result = session.execute(text(query), params or {})
                columns = list(result.keys())
                return [dict(zip(columns, row)) for row in result.fetchall()]

        return self._with_retry("fetch_all", _action)

    def fetch_one(self, query: str, params: Dict = None) -> Optional[Dict]:
        def _action():
            with self._session() as session:
                result = session.execute(text(query), params or {})
                columns = list(result.keys())
                row = result.fetchone()
                return dict(zip(columns, row)) if row else None

        return self._with_retry("fetch_one", _action)

    def fetch_scalar(self, query: str, params: Dict = None) -> Any:
        def _action():
            with self._session() as session:
                return session.execute(text(query), params or {}).scalar()

        return self._with_retry("fetch_scalar", _action)

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def insert(self, table: str, data: Dict) -> None:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

        def _action():
            with self._session() as session:
                session.execute(text(query), data)

        self._with_retry(f"insert({table})", _action)
        logger.info("Inserted into %s: %s", table, data)

    def insert_many(self, table: str, rows: List[Dict]) -> None:
        if not rows:
            return
        cols = ", ".join(rows[0].keys())
        placeholders = ", ".join(f":{k}" for k in rows[0].keys())
        query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

        def _action():
            with self._session() as session:
                session.execute(text(query), rows)

        self._with_retry(f"insert_many({table})", _action)
        logger.info("Inserted %d rows into %s", len(rows), table)

    def update(self, table: str, data: Dict, condition: str, condition_params: Dict = None) -> None:
        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        query = f"UPDATE {table} SET {set_clause} WHERE {condition}"
        params = {**data, **(condition_params or {})}

        def _action():
            with self._session() as session:
                session.execute(text(query), params)

        self._with_retry(f"update({table})", _action)

    def delete(self, table: str, condition: str, params: Dict = None) -> None:
        query = f"DELETE FROM {table} WHERE {condition}"

        def _action():
            with self._session() as session:
                session.execute(text(query), params or {})

        self._with_retry(f"delete({table})", _action)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def table_exists(self, table: str) -> bool:
        try:
            from sqlalchemy import inspect
            inspector = inspect(self._engine)
            return table in inspector.get_table_names()
        except Exception:
            return False

    def row_count(self, table: str) -> int:
        result = self.fetch_scalar(f"SELECT COUNT(*) FROM {table}")
        return int(result) if result is not None else 0
