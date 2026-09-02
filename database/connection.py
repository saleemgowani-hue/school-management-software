"""
database/connection.py — the ONLY module in this codebase that talks to
psycopg2 directly. Every other module (services, auth) goes through the
helpers here (`fetch_one`, `fetch_all`, `execute`, `df`) so there is exactly
one place that knows how to open a connection, and exactly one style of
query parameterization (`%s`) used everywhere.

Uses a small connection pool (psycopg2.pool.ThreadedConnectionPool) — cheap
enough for Streamlit Cloud's single-process model, and avoids re-connecting
on every query within a session. ThreadedConnectionPool (not
SimpleConnectionPool) is required because Streamlit serves each session on
its own thread, and SimpleConnectionPool's getconn/putconn bookkeeping is
not thread-safe.
"""

from contextlib import contextmanager

import pandas as pd
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from sqlalchemy import create_engine

import config

_pool = None
_engine = None


def _build_dsn():
    if config.DATABASE_URL:
        return config.DATABASE_URL
    return (
        f"host={config.PGHOST} port={config.PGPORT} "
        f"dbname={config.PGDATABASE} user={config.PGUSER} password={config.PGPASSWORD}"
    )


def _build_sqlalchemy_url():
    if config.DATABASE_URL:
        url = config.DATABASE_URL
        # normalize postgres:// -> postgresql:// for SQLAlchemy
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return (
        f"postgresql://{config.PGUSER}:{config.PGPASSWORD}"
        f"@{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
    )


def get_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(1, 10, dsn=_build_dsn())
    return _pool


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_build_sqlalchemy_url(), pool_pre_ping=True)
    return _engine


@contextmanager
def get_conn():
    conn = get_pool().getconn()
    try:
        yield conn
    finally:
        get_pool().putconn(conn)


def execute(query, params=()):
    """INSERT/UPDATE/DELETE. Returns the first column of RETURNING if present, else None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            result = None
            if cur.description:  # a RETURNING clause was used
                row = cur.fetchone()
                result = row[0] if row else None
            conn.commit()
            return result


def executemany(query, seq_of_params):
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, query, seq_of_params)
            conn.commit()


def fetch_one(query, params=()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_all(query, params=()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def df(query, params=()):
    return pd.read_sql_query(query, get_engine(), params=params)


def health_check():
    """Used by app.py to show a friendly error instead of a stack trace if the DB is down."""
    try:
        fetch_one("SELECT 1 AS ok")
        return True, None
    except Exception as e:
        return False, str(e)
