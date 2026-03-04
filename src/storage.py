from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from db import connect


def get_user_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """
    Ensures the user exists in SQLite, returns user settings as a dict.
    (Transactions remain in-memory for now.)
    """
    telegram_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    conn = connect()
    cur = conn.cursor()

    # create user if not exists
    cur.execute(
        """
        INSERT OR IGNORE INTO users (telegram_id, chat_id, timezone, daily_enabled, daily_time, last_sent_date, created_at)
        VALUES (?, ?, 'Asia/Singapore', 0, '21:00', NULL, ?)
        """,
        (telegram_id, chat_id, datetime.now().isoformat(timespec="seconds")),
    )

    # always keep chat_id updated
    cur.execute(
        "UPDATE users SET chat_id = ? WHERE telegram_id = ?",
        (chat_id, telegram_id),
    )

    # fetch row
    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    # return a dict with the same keys you used before
    return {
        "db_user_id": row["id"],
        "telegram_id": row["telegram_id"],
        "chat_id": row["chat_id"],
        "timezone": row["timezone"],
        "daily_enabled": bool(row["daily_enabled"]),
        "daily_time": row["daily_time"],
        "last_sent_date": row["last_sent_date"],
    }
def set_daily_enabled(telegram_id: str, enabled: bool) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET daily_enabled = ? WHERE telegram_id = ?",
        (1 if enabled else 0, telegram_id),
    )
    conn.commit()
    conn.close()


def set_daily_time(telegram_id: str, daily_time: str) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET daily_time = ? WHERE telegram_id = ?",
        (daily_time, telegram_id),
    )
    conn.commit()
    conn.close()


def set_timezone(telegram_id: str, timezone: str) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET timezone = ? WHERE telegram_id = ?",
        (timezone, telegram_id),
    )
    conn.commit()
    conn.close()


def set_last_sent_date(telegram_id: str, last_sent_date: str) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET last_sent_date = ? WHERE telegram_id = ?",
        (last_sent_date, telegram_id),
    )
    conn.commit()
    conn.close()

from datetime import datetime, date


def _get_db_user_id(telegram_id: str) -> int:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise ValueError("User not found in DB. Call get_user_store() on /start first.")
    return int(row["id"])


def add_transaction(telegram_id: str, tx_type: str, amount: float, note: str, ts: str) -> None:
    user_id = _get_db_user_id(telegram_id)

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions (user_id, type, amount, note, ts)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, tx_type, float(amount), note, ts),
    )
    conn.commit()
    conn.close()


def get_transactions_between(telegram_id: str, start_iso: str, end_iso: str) -> list[dict]:
    """
    Returns transactions where ts is between [start_iso, end_iso).
    ISO format strings, e.g. '2026-03-04T00:00:00'
    """
    user_id = _get_db_user_id(telegram_id)

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT type, amount, note, ts
        FROM transactions
        WHERE user_id = ?
          AND ts >= ?
          AND ts < ?
        ORDER BY ts ASC
        """,
        (user_id, start_iso, end_iso),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {"type": r["type"], "amount": r["amount"], "note": r["note"] or "", "ts": r["ts"]}
        for r in rows
    ]

def get_all_users() -> list[dict]:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT telegram_id, chat_id, timezone, daily_enabled, daily_time, last_sent_date
        FROM users
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "telegram_id": r["telegram_id"],
            "chat_id": r["chat_id"],
            "timezone": r["timezone"],
            "daily_enabled": bool(r["daily_enabled"]),
            "daily_time": r["daily_time"],
            "last_sent_date": r["last_sent_date"],
        }
        for r in rows
    ]