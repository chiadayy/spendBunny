from datetime import datetime, timedelta


def parse_time_24h(value: str):
    try:
        hh_str, mm_str = value.split(":")
        hh = int(hh_str)
        mm = int(mm_str)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
    except Exception:
        return None
    return None


def iso_start_of_day(d):
    return datetime.combine(d, datetime.min.time()).isoformat(timespec="seconds")


def iso_start_of_next_day(d):
    return datetime.combine(d + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")


def sum_txns(txns: list[dict]):
    income = expense = 0.0
    for tx in txns:
        amt = float(tx["amount"])
        if tx["type"] == "income":
            income += amt
        else:
            expense += amt
    return income, expense, len(txns)
