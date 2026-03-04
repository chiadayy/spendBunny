import os
import sqlite3

# DB file will live in your repo root by default
DB_PATH = os.getenv("DB_PATH", "spendbunny.db")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # nice dict-like rows
    # good defaults
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    conn = connect()
    cur = conn.cursor()

    # users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT NOT NULL UNIQUE,
            chat_id TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'Asia/Singapore',
            daily_enabled INTEGER NOT NULL DEFAULT 0,
            daily_time TEXT NOT NULL DEFAULT '21:00',
            last_sent_date TEXT,
            created_at TEXT NOT NULL
        );
        """
    )

    # transactions table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            amount REAL NOT NULL,
            note TEXT,
            ts TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # helpful index for summary queries later
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_user_ts
        ON transactions(user_id, ts);
        """
    )

    conn.commit()
    conn.close()