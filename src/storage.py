from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from db import connect


def _update_user_field(telegram_id: str, field: str, value) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE users SET {field} = ? WHERE telegram_id = ?",
        (value, telegram_id),
    )
    conn.commit()
    conn.close()


def get_user_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """
    Ensures the user exists in SQLite, then returns user settings as a dict.
    """
    telegram_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (telegram_id, chat_id, timezone, daily_enabled, daily_time, last_sent_date, created_at)
        VALUES (?, ?, 'Asia/Singapore', 0, '21:00', NULL, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET chat_id = excluded.chat_id
        """,
        (telegram_id, chat_id, datetime.now().isoformat(timespec="seconds")),
    )

    cur.execute(
        """
        SELECT id, telegram_id, chat_id, timezone, daily_enabled, daily_time, last_sent_date
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    )
    row = cur.fetchone()

    conn.commit()
    conn.close()

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
    _update_user_field(telegram_id, "daily_enabled", 1 if enabled else 0)


def set_daily_time(telegram_id: str, daily_time: str) -> None:
    _update_user_field(telegram_id, "daily_time", daily_time)


def set_timezone(telegram_id: str, timezone: str) -> None:
    _update_user_field(telegram_id, "timezone", timezone)


def set_last_sent_date(telegram_id: str, last_sent_date: str) -> None:
    _update_user_field(telegram_id, "last_sent_date", last_sent_date)


def add_transaction(telegram_id: str, tx_type: str, amount: float, note: str, ts: str) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions (user_id, type, amount, note, ts)
        SELECT id, ?, ?, ?, ?
        FROM users
        WHERE telegram_id = ?
        """,
        (tx_type, float(amount), note, ts, telegram_id),
    )

    if cur.rowcount == 0:
        conn.close()
        raise ValueError("User not found in DB. Call get_user_store() on /start first.")

    conn.commit()
    conn.close()


def get_transactions_between(telegram_id: str, start_iso: str, end_iso: str) -> list[dict]:
    """
    Returns transactions where ts is between [start_iso, end_iso).
    ISO format strings, e.g. '2026-03-04T00:00:00'
    """
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.type, t.amount, t.note, t.ts
        FROM transactions t
        JOIN users u ON u.id = t.user_id
        WHERE u.telegram_id = ?
          AND t.ts >= ?
          AND t.ts < ?
        ORDER BY t.ts ASC
        """,
        (telegram_id, start_iso, end_iso),
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
