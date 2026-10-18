"""In-memory SQLite stand-in for MySQL — for smoke tests and offline demos ONLY.

It replaces `create_connection` inside every database/*.py module with a shim
that speaks just enough of the mysql.connector API (cursor(dictionary=True),
%s placeholders, lastrowid, rowcount, is_connected) for the existing queries
to run unchanged. Real deployments must use MySQL (the default).
"""
import datetime as _dt
import re
import sqlite3
import threading
from pathlib import Path

from mysql.connector import Error as MySQLError

_ROOT = Path(__file__).resolve().parent.parent
_lock = threading.RLock()
_conn = None


def _translate(sql: str) -> str:
    s = sql.strip()
    if re.match(r"(?i)^SHOW\s+COLUMNS\s+FROM\s+(\w+)\s+LIKE\s+'(\w+)'", s):
        table, col = re.match(r"(?i)^SHOW\s+COLUMNS\s+FROM\s+(\w+)\s+LIKE\s+'(\w+)'", s).groups()
        return f"SELECT name FROM pragma_table_info('{table}') WHERE name = '{col}'"
    if re.match(r"(?i)^SHOW\s+TABLES", s):
        return "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    if re.match(r"(?i)^SELECT\s+DATABASE\(\)", s):
        return "SELECT 'fake_in_memory_db'"
    s = re.sub(r"(?i)INT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY", "INTEGER PRIMARY KEY AUTOINCREMENT", s)
    s = re.sub(r"(?i)\bIF\(", "IIF(", s)
    s = re.sub(r"(?i)\bNOW\(\)", "strftime('%Y-%m-%dT%H:%M:%f+00:00','now')", s)
    s = s.replace("%s", "?")
    return s


def _adapt(value):
    if isinstance(value, (_dt.datetime,)):
        return value.astimezone().isoformat()  # keep the offset so "x ago" is right in demo mode
    return value


class _Cursor:
    def __init__(self, conn: sqlite3.Connection, dictionary: bool):
        self._cur = conn.cursor()
        self._dictionary = dictionary

    def execute(self, query, params=()):
        with _lock:
            try:
                self._cur.execute(_translate(query), tuple(_adapt(p) for p in (params or ())))
            except sqlite3.Error as error:
                raise MySQLError(msg=f"[fake-db] {error}")

    def _row(self, row):
        if row is None or not self._dictionary:
            return row
        cols = [d[0] for d in self._cur.description]
        return dict(zip(cols, row))

    def fetchone(self):
        return self._row(self._cur.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        pass


class _Connection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary: bool = False):
        return _Cursor(self._conn, dictionary)

    def commit(self):
        with _lock:
            self._conn.commit()

    def is_connected(self):
        return True

    def close(self):
        pass  # keep the shared in-memory DB alive


def fake_create_connection(*_args, **_kwargs):
    return _Connection(_conn)


def _bootstrap_schema():
    """Create users / profiles / resume_data from the project's own schema.sql.
    career_predictions, skill_gap and roadmaps are created by the project's
    create_*_table_if_missing() functions, exactly like the app does."""
    sql = (_ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    for statement in sql.split(";"):
        st = statement.strip()
        m = re.search(r"(?i)CREATE TABLE IF NOT EXISTS (\w+)", st)
        if m and m.group(1) in {"users", "profiles", "resume_data"}:
            body = "\n".join(line for line in st.splitlines() if not line.strip().startswith("--"))
            _conn.execute(_translate(body))
    _conn.commit()


def install_fake_db(seed_admin: bool = True):
    """Patch every database module to use the in-memory DB. Idempotent."""
    global _conn
    import database.admin_db as admin_db
    import database.career_db as career_db
    import database.db_connection as db_connection
    import database.db_utils as db_utils
    import database.resume_db as resume_db
    import database.roadmap_db as roadmap_db
    import database.skill_gap_db as skill_gap_db

    if _conn is None:
        _conn = sqlite3.connect(":memory:", check_same_thread=False)
        _bootstrap_schema()

    for module in (db_connection, db_utils, admin_db, career_db, resume_db, roadmap_db, skill_gap_db):
        module.create_connection = fake_create_connection

    career_db.create_career_predictions_table_if_missing()
    skill_gap_db.create_skill_gap_table_if_missing()
    roadmap_db.create_roadmap_table_if_missing()

    if seed_admin and not db_utils.get_user_by_email("admin@careerforge.local"):
        from utils.auth import hash_password

        db_utils.create_user("Demo Admin", "admin@careerforge.local", hash_password("admin12345"), role="admin")


def reset_fake_db():
    global _conn
    _conn = None
