import os
import sqlite3
from urllib.parse import quote_plus
from flask import g
import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


def get_database_url():
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    
    # SQLite fallback support: file:path/to/db or sqlite:///path/to/db
    if database_url and database_url.startswith("file:"):
        return database_url[5:]  # Return just the path
    if database_url and database_url.startswith("sqlite://"):
        return database_url[9]  # Remove sqlite:// prefix
    
    if database_url:
        return database_url

    host = os.environ.get("POSTGRES_HOST")
    if not host:
        # Fallback to SQLite if no PostgreSQL config
        return os.path.join(BASE_DIR, "school.db").replace("\\", "/")

    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "school")
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{dbname}"


def _prepare_query(query, is_sqlite=False):
    # SQLite uses ? placeholders, PostgreSQL uses %s
    if not is_sqlite:
        return query.replace("?", "%s") if "?" in query else query
    return query  # Keep SQLite ? placeholders as-is


class DBCursor:
    def __init__(self, cursor, is_sqlite=False):
        self._cursor = cursor
        self._returning_row = None
        self._is_sqlite = is_sqlite

    def execute(self, query, args=None):
        if args is None:
            args = ()
        query_text = _prepare_query(query, self._is_sqlite)
        try:
            self._cursor.execute(query_text, args)
            if "RETURNING" in query_text.upper() and not self._is_sqlite:
                self._returning_row = self._cursor.fetchone()
            return self
        except Exception:
            self._cursor.connection.rollback()
            raise

    def executemany(self, query, seq_of_params):
        query_text = _prepare_query(query, self._is_sqlite)
        try:
            self._cursor.executemany(query_text, seq_of_params)
            return self
        except Exception:
            self._cursor.connection.rollback()
            raise

    def fetchone(self):
        if self._returning_row is not None:
            return self._returning_row
        return self._cursor.fetchone()

    def fetchall(self):
        if self._returning_row is not None:
            row = self._returning_row
            self._returning_row = None
            return [row]
        try:
            return self._cursor.fetchall()
        except Exception:
            # No results to fetch (e.g., INSERT/UPDATE/DELETE without RETURNING)
            return []

    def close(self):
        self._cursor.close()

    @property
    def lastrowid(self):
        if self._is_sqlite:
            return self._cursor.lastrowid
        if self._returning_row is not None:
            return self._returning_row[0]
        return None

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class DBConnection:
    def __init__(self, conn, is_sqlite=False):
        self._conn = conn
        self._is_sqlite = is_sqlite

    def cursor(self):
        if self._is_sqlite:
            return DBCursor(self._conn.cursor(), is_sqlite=True)
        return DBCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def execute(self, query, args=None):
        cur = self.cursor()
        cur.execute(query, args)
        return cur

    def executemany(self, query, seq_of_params):
        cur = self.cursor()
        cur.executemany(query, seq_of_params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    @property
    def row_factory(self):
        return self._conn.row_factory if self._is_sqlite else None

    @row_factory.setter
    def row_factory(self, value):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _make_sqlite_dict_row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def connect_db():
    database_url = get_database_url()
    
    # SQLite connection
    is_sqlite = os.path.isabs(database_url) or database_url.endswith('.db') or database_url.endswith('.sqlite') or database_url.endswith('.sqlite3')
    if is_sqlite:
        conn = sqlite3.connect(database_url)
        conn.row_factory = _make_sqlite_dict_row_factory
        return DBConnection(conn, is_sqlite=True)
    
    # PostgreSQL connection
    conn = psycopg2.connect(database_url)
    return DBConnection(conn, is_sqlite=False)


def get_db():
    db = getattr(g, "_database", None)
    if db is not None:
        try:
            if hasattr(db._conn, 'closed') and db._conn.closed:
                db.close()
                db = None
        except Exception:
            db = None
    if db is None:
        db = g._database = connect_db()
    return db


def add_column_if_not_exists(db, table_name, column_name, column_type):
    """Add a column to a table if it doesn't exist, works with both SQLite and PostgreSQL."""
    is_sqlite = hasattr(db, '_is_sqlite') and db._is_sqlite
    cur = db.cursor()
    try:
        if is_sqlite:
            # SQLite: Check pragma_table_info first
            cur.execute(f"PRAGMA table_info({table_name})")
            existing = {row["name"] for row in cur.fetchall()}
            if column_name not in existing:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                db.commit()
        else:
            # PostgreSQL: Use IF NOT EXISTS
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
    except Exception:
        pass


def has_table_columns(table_name, column_names):
    """Check which columns exist in a table, works with both SQLite and PostgreSQL."""
    db = get_db()
    cur = db.cursor()
    try:
        is_sqlite = hasattr(db, '_is_sqlite') and db._is_sqlite
        
        if is_sqlite:
            cur.execute(f"PRAGMA table_info({table_name})")
            available = {row["name"] for row in cur.fetchall()}
            return {col for col in column_names if col in available}
        else:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                  AND column_name = ANY(%s)
                """,
                (table_name, list(column_names)),
            )
            return {row["column_name"] for row in cur.fetchall()}
    finally:
        cur.close()
