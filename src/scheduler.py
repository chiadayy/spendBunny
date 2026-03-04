from datetime import datetime
from zoneinfo import ZoneInfo

from storage import get_all_users, get_transactions_between, set_last_sent_date


def _start_of_day_iso(d):
    return datetime.combine(d, datetime.min.time()).isoformat(timespec="seconds")


def _start_of_next_day_iso(d):
    from datetime import timedelta
    return datetime.combine(d + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")


def _sum_txns(txns):
    income = expense = 0.0
    count = 0
    for tx in txns:
        amt = float(tx["amount"])
        if tx["type"] == "income":
            income += amt
        else:
            expense += amt
        count += 1
    return income, expense, count


async def send_nightly_summary(app):
    """
    Runs every minute.
    DB-backed: loads users from SQLite, computes summary from SQLite,
    and updates last_sent_date in SQLite to avoid duplicates.
    """
    users = get_all_users()

    for u in users:
        if not u.get("daily_enabled"):
            continue

        tz_name = u.get("timezone") or "Asia/Singapore"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Singapore")

        now = datetime.now(tz)
        today_str = now.date().isoformat()

        # prevent duplicates
        if u.get("last_sent_date") == today_str:
            continue

        # check scheduled minute
        daily_time = u.get("daily_time") or "21:00"
        try:
            hh, mm = daily_time.split(":")
            hh_i, mm_i = int(hh), int(mm)
        except Exception:
            hh_i, mm_i = 21, 0

        if not (now.hour == hh_i and now.minute == mm_i):
            continue

        telegram_id = u["telegram_id"]
        chat_id = u["chat_id"]

        # compute today's summary from DB
        txns = get_transactions_between(
            telegram_id,
            _start_of_day_iso(now.date()),
            _start_of_next_day_iso(now.date()),
        )
        inc, exp, cnt = _sum_txns(txns)
        net = inc - exp

        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🌙 Daily Money Recap\n\n"
                f"Income: +${inc:.2f}\n"
                f"Spent: -${exp:.2f}\n"
                f"Net: ${net:.2f}\n"
                f"Transactions: {cnt}"
            ),
        )

        # mark sent in DB
        set_last_sent_date(telegram_id, today_str)