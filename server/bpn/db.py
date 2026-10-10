"""SQLite access + numbered migrations (schema_version table)."""
import sqlite3

MIGRATIONS = [
    # 1: accounts, consoles, refresh tokens
    """
    CREATE TABLE accounts (
        account_id TEXT PRIMARY KEY,
        online_id  TEXT NOT NULL UNIQUE,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE consoles (
        console_id   TEXT PRIMARY KEY,
        secret_hash  TEXT NOT NULL,
        salt         TEXT NOT NULL,
        platform     TEXT NOT NULL DEFAULT 'ps5',
        label        TEXT,
        enabled      INTEGER NOT NULL DEFAULT 1,
        created_at   INTEGER NOT NULL
    );
    CREATE TABLE refresh_tokens (
        token_hash  TEXT PRIMARY KEY,
        account_id  TEXT NOT NULL REFERENCES accounts(account_id),
        console_id  TEXT NOT NULL REFERENCES consoles(console_id),
        expires_at  INTEGER NOT NULL,
        revoked     INTEGER NOT NULL DEFAULT 0
    );
    """,
    # 2: trophy mirroring + presence
    """
    CREATE TABLE titles (
        account_id TEXT NOT NULL REFERENCES accounts(account_id),
        title_id   TEXT NOT NULL,
        title_name TEXT NOT NULL,
        playtime_minutes INTEGER NOT NULL DEFAULT 0,
        last_synced_at   INTEGER NOT NULL,
        PRIMARY KEY (account_id, title_id)
    );
    CREATE TABLE trophies (
        account_id  TEXT NOT NULL,
        title_id    TEXT NOT NULL,
        trophy_id   INTEGER NOT NULL,
        name        TEXT NOT NULL,
        grade       TEXT NOT NULL,
        unlocked_at TEXT NOT NULL,
        console_id  TEXT NOT NULL,
        PRIMARY KEY (account_id, title_id, trophy_id)
    );
    CREATE TABLE presence (
        account_id TEXT PRIMARY KEY REFERENCES accounts(account_id),
        console_id TEXT NOT NULL,
        title_id   TEXT,
        title_name TEXT,
        status     TEXT,
        updated_at INTEGER NOT NULL
    );
    """,
]


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current = row[0] or 0
    for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.execute("BEGIN")
        try:
            for stmt in [s for s in sql.split(";") if s.strip()]:
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (i,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        current = i
    return current
