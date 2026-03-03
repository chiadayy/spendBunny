from datetime import datetime
from zoneinfo import ZoneInfo


async def send_nightly_summary(app):
    """
    Runs every minute.
    Sends a nightly recap only when:
    - daily_enabled is True
    - current time matches user's daily_time (HH:MM) in their timezone
    - hasn't already sent today (last_sent_date)
    """
    users = app.bot_data.get("users", {})

    for _, data in users.items():
        if not data.get("daily_enabled"):
            continue

        tz_name = data.get("timezone", "Asia/Singapore")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Singapore")

        now = datetime.now(tz)
        today_str = now.date().isoformat()

        # prevent duplicates
        if data.get("last_sent_date") == today_str:
            continue

        # check if scheduled minute matches
        daily_time = data.get("daily_time", "21:00")
        try:
            hh, mm = daily_time.split(":")
            hh_i, mm_i = int(hh), int(mm)
        except Exception:
            hh_i, mm_i = 21, 0

        if not (now.hour == hh_i and now.minute == mm_i):
            continue

        chat_id = data.get("chat_id")
        txns = data.get("txns", [])

        income = expense = count = 0
        for tx in txns:
            ts = tx.get("ts")
            if not ts:
                continue
            d = datetime.fromisoformat(ts).date()
            if d != now.date():
                continue

            amt = float(tx["amount"])
            if tx["type"] == "income":
                income += amt
            else:
                expense += amt
            count += 1

        net = income - expense

        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🌙 Daily Money Recap\n\n"
                f"Income: +${income:.2f}\n"
                f"Spent: -${expense:.2f}\n"
                f"Net: ${net:.2f}\n"
                f"Transactions: {count}"
            ),
        )

        data["last_sent_date"] = today_str