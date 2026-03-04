from datetime import datetime
from zoneinfo import ZoneInfo

from finance import iso_start_of_day, iso_start_of_next_day, parse_time_24h, sum_txns
from storage import get_all_users, get_transactions_between, set_last_sent_date


async def send_nightly_summary(app):
    """
    Runs every minute.
    DB-backed: loads users from SQLite, computes summary from SQLite,
    and updates last_sent_date in SQLite to avoid duplicates.
    """
    users = get_all_users()

    for user in users:
        if not user.get("daily_enabled"):
            continue

        tz_name = user.get("timezone") or "Asia/Singapore"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Singapore")

        now = datetime.now(tz)
        today_str = now.date().isoformat()

        if user.get("last_sent_date") == today_str:
            continue

        scheduled_time = parse_time_24h(user.get("daily_time") or "21:00") or "21:00"
        if scheduled_time != f"{now.hour:02d}:{now.minute:02d}":
            continue

        telegram_id = user["telegram_id"]
        txns = get_transactions_between(
            telegram_id,
            iso_start_of_day(now.date()),
            iso_start_of_next_day(now.date()),
        )
        inc, exp, cnt = sum_txns(txns)

        await app.bot.send_message(
            chat_id=user["chat_id"],
            text=(
                f"🌙 Daily Money Recap\n\n"
                f"Income: +${inc:.2f}\n"
                f"Spent: -${exp:.2f}\n"
                f"Net: ${inc - exp:.2f}\n"
                f"Transactions: {cnt}"
            ),
        )

        set_last_sent_date(telegram_id, today_str)
