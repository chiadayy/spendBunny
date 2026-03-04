from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from finance import iso_start_of_day, iso_start_of_next_day, parse_time_24h, sum_txns
from storage import (
    add_transaction,
    get_transactions_between,
    get_user_store,
    set_daily_enabled,
    set_daily_time,
    set_timezone,
)
from ui import main_menu_markup, render_menu, render_schedule


SUMMARY_PERIOD_LABELS = {
    "TODAY": "Today",
    "WEEK": "This Week",
    "MONTH": "This Month",
}


def parse_amount(text: str):
    try:
        return float(text.strip())
    except ValueError:
        return None


def get_period_dates(period_key: str):
    today = datetime.now().date()

    if period_key == "TODAY":
        return today, today
    if period_key == "WEEK":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period_key == "MONTH":
        return today.replace(day=1), today

    raise ValueError(f"Unsupported period key: {period_key}")


def build_summary_text(telegram_id: str, period_key: str) -> str:
    start, end = get_period_dates(period_key)
    txns = get_transactions_between(
        telegram_id,
        iso_start_of_day(start),
        iso_start_of_next_day(end),
    )

    inc, exp, cnt = sum_txns(txns)
    net = inc - exp

    header = f"📊 Summary — {SUMMARY_PERIOD_LABELS[period_key]}"
    date_line = f"({start} to {end})\n" if period_key != "TODAY" else ""

    return (
        f"{header}\n"
        f"{date_line}"
        f"Income: +${inc:.2f}\n"
        f"Spent: -${exp:.2f}\n"
        f"Net: ${net:.2f}\n"
        f"Transactions: {cnt}\n\n"
        "Type /menu to continue."
    )


def save_pending_transaction(telegram_id: str, context: ContextTypes.DEFAULT_TYPE, note: str) -> tuple[str, float, str]:
    tx_type = context.user_data.get("pending_type")
    amount = context.user_data.get("pending_amount")
    ts = datetime.now().isoformat(timespec="seconds")

    add_transaction(
        telegram_id=telegram_id,
        tx_type=tx_type,
        amount=amount,
        note=note,
        ts=ts,
    )

    context.user_data.pop("pending_type", None)
    context.user_data.pop("pending_amount", None)
    context.user_data["state"] = None

    return tx_type, amount, note


async def render_user_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, query) -> None:
    store = get_user_store(update, context)
    status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
    await render_schedule(
        query,
        status,
        store.get("daily_time", "21:00"),
        store.get("timezone", "Asia/Singapore"),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user_store(update, context)
    await update.message.reply_text(
        "Welcome to your Personal Finance Bot 💰\n\nUse /menu to begin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose an option:", reply_markup=main_menu_markup())


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    await update.message.reply_text(build_summary_text(telegram_id, "TODAY"))


async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    telegram_id = str(update.effective_user.id)

    if choice == "SKIP_NOTE":
        tx_type, amount, _ = save_pending_transaction(telegram_id, context, "")
        sign = "-" if tx_type == "expense" else "+"
        await query.edit_message_text(
            f"Saved ✅ {sign}${amount:.2f}",
            reply_markup=main_menu_markup(),
        )
        return

    if choice == "EXPENSE":
        context.user_data["state"] = "AWAIT_EXPENSE_AMOUNT"
        await query.edit_message_text("Expense: send the amount (e.g. 6.50)")
        return

    if choice == "INCOME":
        context.user_data["state"] = "AWAIT_INCOME_AMOUNT"
        await query.edit_message_text("Income: send the amount (e.g. 120)")
        return

    if choice == "SUMMARY":
        keyboard = [
            [InlineKeyboardButton("Today", callback_data="SUM_TODAY")],
            [InlineKeyboardButton("This Week", callback_data="SUM_WEEK")],
            [InlineKeyboardButton("This Month", callback_data="SUM_MONTH")],
            [InlineKeyboardButton("Back", callback_data="BACK_MENU")],
        ]
        await query.edit_message_text(
            "📊 Choose a period:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if choice == "SCHEDULE":
        await render_user_schedule(update, context, query)
        return

    if choice in {"SCH_ON", "SCH_OFF"}:
        set_daily_enabled(telegram_id, choice == "SCH_ON")
        await render_user_schedule(update, context, query)
        return

    if choice == "SCH_TIME":
        current = get_user_store(update, context).get("daily_time", "21:00")
        keyboard = [
            [InlineKeyboardButton("Custom (HH:MM)", callback_data="SCH_TIME_CUSTOM")],
            [InlineKeyboardButton("Back", callback_data="SCHEDULE")],
        ]
        await query.edit_message_text(
            f"🕘 Set nightly time (current: {current})",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if choice == "SCH_TIME_CUSTOM":
        context.user_data["state"] = "AWAIT_CUSTOM_TIME"
        await query.edit_message_text("🕘 Send time in 24h format HH:MM (e.g. 21:35)")
        return

    if choice == "SCH_TZ":
        current = get_user_store(update, context).get("timezone", "Asia/Singapore")
        keyboard = [
            [InlineKeyboardButton("Singapore (Asia/Singapore)", callback_data="SET_TZ_ASIA_SINGAPORE")],
            [InlineKeyboardButton("Back", callback_data="SCHEDULE")],
        ]
        await query.edit_message_text(
            f"🌍 Set timezone (current: {current})",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if choice == "SET_TZ_ASIA_SINGAPORE":
        set_timezone(telegram_id, "Asia/Singapore")
        await render_user_schedule(update, context, query)
        return

    summary_choice_map = {
        "SUM_TODAY": "TODAY",
        "SUM_WEEK": "WEEK",
        "SUM_MONTH": "MONTH",
    }
    period_key = summary_choice_map.get(choice)
    if period_key:
        await query.edit_message_text(build_summary_text(telegram_id, period_key))
        return

    if choice == "BACK_MENU":
        await render_menu(query)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if not state:
        return

    text = (update.message.text or "").strip()
    telegram_id = str(update.effective_user.id)

    if state == "AWAIT_CUSTOM_TIME":
        new_time = parse_time_24h(text)
        if not new_time:
            await update.message.reply_text(
                "Invalid time. Send HH:MM in 24h format (e.g. 21:35)."
            )
            return

        set_daily_time(telegram_id, new_time)
        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ Nightly time set to {new_time}\nType /menu to continue."
        )
        return

    if state in {"AWAIT_EXPENSE_AMOUNT", "AWAIT_INCOME_AMOUNT"}:
        amt = parse_amount(text)
        if amt is None or amt <= 0:
            example = "6.50" if state == "AWAIT_EXPENSE_AMOUNT" else "120"
            await update.message.reply_text(
                f"Please send a valid positive number (e.g. {example})."
            )
            return

        context.user_data["pending_amount"] = amt
        context.user_data["pending_type"] = "expense" if state == "AWAIT_EXPENSE_AMOUNT" else "income"
        context.user_data["state"] = "AWAIT_NOTE"

        keyboard = [[InlineKeyboardButton("Skip", callback_data="SKIP_NOTE")]]
        await update.message.reply_text(
            "Add a note (optional), or tap Skip.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if state == "AWAIT_NOTE":
        tx_type, amount, note = save_pending_transaction(telegram_id, context, text)
        sign = "-" if tx_type == "expense" else "+"
        await update.message.reply_text(
            f"Saved ✅ {sign}${amount:.2f}\n"
            f"Note: {note}",
            reply_markup=main_menu_markup(),
        )
