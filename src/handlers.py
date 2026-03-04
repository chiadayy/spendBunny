import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from storage import (
    get_user_store,
    set_daily_enabled,
    set_daily_time,
    set_timezone,
    add_transaction,
    get_transactions_between,
)

from ui import main_menu_markup, render_menu, render_schedule


def parse_amount(text: str):
    try:
        return float(text.strip())
    except ValueError:
        return None


def iso_start_of_day(d):
    return datetime.combine(d, datetime.min.time()).isoformat(timespec="seconds")


def iso_start_of_next_day(d):
    return datetime.combine(d + timedelta(days=1), datetime.min.time()).isoformat(timespec="seconds")


def sum_txns(txns: list[dict]):
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user_store(update, context)
    await update.message.reply_text(
        "Welcome to your Personal Finance Bot 💰\n\nUse /menu to begin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Main Menu:", reply_markup=main_menu_markup())


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Command version: Today summary from DB
    telegram_id = str(update.effective_user.id)
    today = datetime.now().date()

    txns = get_transactions_between(
        telegram_id,
        iso_start_of_day(today),
        iso_start_of_next_day(today),
    )

    inc, exp, cnt = sum_txns(txns)
    net = inc - exp

    await update.message.reply_text(
        f"📊 Summary — Today\n"
        f"Income: +${inc:.2f}\n"
        f"Spent: -${exp:.2f}\n"
        f"Net: ${net:.2f}\n"
        f"Transactions: {cnt}\n\n"
        f"Type /menu to continue."
    )


async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    # -------------------------
    # Skip note -> save txn to DB
    # -------------------------
    if choice == "SKIP_NOTE":
        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": "",
            "ts": datetime.now().isoformat(timespec="seconds"),
        }

        telegram_id = str(update.effective_user.id)
        add_transaction(
            telegram_id=telegram_id,
            tx_type=tx["type"],
            amount=tx["amount"],
            note="",
            ts=tx["ts"],
        )

        context.user_data.pop("pending_type", None)
        context.user_data.pop("pending_amount", None)
        context.user_data["state"] = None

        sign = "-" if tx["type"] == "expense" else "+"
        await query.edit_message_text(
            f"Saved ✅ {sign}${tx['amount']:.2f}\n\nType /menu to continue."
        )
        return

    # -------------------------
    # Main menu options
    # -------------------------
    if choice == "EXPENSE":
        context.user_data["state"] = "AWAIT_EXPENSE_AMOUNT"
        await query.edit_message_text("➕ Expense: send the amount (e.g. 6.50)")
        return

    if choice == "INCOME":
        context.user_data["state"] = "AWAIT_INCOME_AMOUNT"
        await query.edit_message_text("➕ Income: send the amount (e.g. 120)")
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

    # -------------------------
    # Schedule screen
    # -------------------------
    if choice == "SCHEDULE":
        store = get_user_store(update, context)
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    # -------------------------
    # Schedule actions (persist to SQLite)
    # -------------------------
    if choice == "SCH_ON":
        telegram_id = str(update.effective_user.id)
        set_daily_enabled(telegram_id, True)

        store = get_user_store(update, context)
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    if choice == "SCH_OFF":
        telegram_id = str(update.effective_user.id)
        set_daily_enabled(telegram_id, False)

        store = get_user_store(update, context)
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    if choice == "SCH_TIME":
        store = get_user_store(update, context)
        current = store.get("daily_time", "21:00")
        keyboard = [
            [InlineKeyboardButton("8:00 PM", callback_data="SET_TIME_20_00")],
            [InlineKeyboardButton("9:00 PM", callback_data="SET_TIME_21_00")],
            [InlineKeyboardButton("10:00 PM", callback_data="SET_TIME_22_00")],
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

    if choice.startswith("SET_TIME_"):
        parts = choice.replace("SET_TIME_", "").split("_")
        hh, mm = parts[0], parts[1]
        new_time = f"{hh}:{mm}"

        telegram_id = str(update.effective_user.id)
        set_daily_time(telegram_id, new_time)

        await query.edit_message_text(f"✅ Nightly time set to {new_time}")
        await asyncio.sleep(1)
        await render_menu(query)
        return

    if choice == "SCH_TZ":
        store = get_user_store(update, context)
        current = store.get("timezone", "Asia/Singapore")
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
        telegram_id = str(update.effective_user.id)
        set_timezone(telegram_id, "Asia/Singapore")

        store = get_user_store(update, context)
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    # -------------------------
    # Summary buttons (DB-backed)
    # -------------------------
    if choice == "SUM_TODAY":
        telegram_id = str(update.effective_user.id)
        today = datetime.now().date()

        txns = get_transactions_between(
            telegram_id,
            iso_start_of_day(today),
            iso_start_of_next_day(today),
        )

        inc, exp, cnt = sum_txns(txns)
        net = inc - exp

        await query.edit_message_text(
            f"📊 Summary — Today\n"
            f"Income: +${inc:.2f}\n"
            f"Spent: -${exp:.2f}\n"
            f"Net: ${net:.2f}\n"
            f"Transactions: {cnt}\n\n"
            f"Type /menu to continue."
        )
        return

    if choice == "SUM_WEEK":
        telegram_id = str(update.effective_user.id)
        today = datetime.now().date()
        start = today - timedelta(days=today.weekday())  # Monday
        end = today  # inclusive display; we query up to tomorrow exclusive

        txns = get_transactions_between(
            telegram_id,
            iso_start_of_day(start),
            iso_start_of_next_day(end),
        )

        inc, exp, cnt = sum_txns(txns)
        net = inc - exp

        await query.edit_message_text(
            f"📊 Summary — This Week\n"
            f"({start} to {end})\n"
            f"Income: +${inc:.2f}\n"
            f"Spent: -${exp:.2f}\n"
            f"Net: ${net:.2f}\n"
            f"Transactions: {cnt}\n\n"
            f"Type /menu to continue."
        )
        return

    if choice == "SUM_MONTH":
        telegram_id = str(update.effective_user.id)
        today = datetime.now().date()
        start = today.replace(day=1)
        end = today

        txns = get_transactions_between(
            telegram_id,
            iso_start_of_day(start),
            iso_start_of_next_day(end),
        )

        inc, exp, cnt = sum_txns(txns)
        net = inc - exp

        await query.edit_message_text(
            f"📊 Summary — This Month\n"
            f"({start} to {end})\n"
            f"Income: +${inc:.2f}\n"
            f"Spent: -${exp:.2f}\n"
            f"Net: ${net:.2f}\n"
            f"Transactions: {cnt}\n\n"
            f"Type /menu to continue."
        )
        return

    if choice == "BACK_MENU":
        await render_menu(query)
        return


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if not state:
        return

    text = (update.message.text or "").strip()

    # -------------------------
    # Custom time input (persist to SQLite)
    # -------------------------
    if state == "AWAIT_CUSTOM_TIME":
        t = text.strip()
        try:
            hh_str, mm_str = t.split(":")
            hh = int(hh_str)
            mm = int(mm_str)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except Exception:
            await update.message.reply_text(
                "Invalid time. Send HH:MM in 24h format (e.g. 21:35)."
            )
            return

        new_time = f"{hh:02d}:{mm:02d}"
        telegram_id = str(update.effective_user.id)
        set_daily_time(telegram_id, new_time)

        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ Nightly time set to {new_time}\nType /menu to continue."
        )
        return

    # -------------------------
    # Expense amount
    # -------------------------
    if state == "AWAIT_EXPENSE_AMOUNT":
        amt = parse_amount(text)
        if amt is None or amt <= 0:
            await update.message.reply_text(
                "Please send a valid positive number (e.g. 6.50)."
            )
            return

        context.user_data["pending_amount"] = amt
        context.user_data["pending_type"] = "expense"
        context.user_data["state"] = "AWAIT_NOTE"

        keyboard = [[InlineKeyboardButton("Skip", callback_data="SKIP_NOTE")]]
        await update.message.reply_text(
            "Add a note (optional), or tap Skip.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # -------------------------
    # Income amount
    # -------------------------
    if state == "AWAIT_INCOME_AMOUNT":
        amt = parse_amount(text)
        if amt is None or amt <= 0:
            await update.message.reply_text(
                "Please send a valid positive number (e.g. 120)."
            )
            return

        context.user_data["pending_amount"] = amt
        context.user_data["pending_type"] = "income"
        context.user_data["state"] = "AWAIT_NOTE"

        keyboard = [[InlineKeyboardButton("Skip", callback_data="SKIP_NOTE")]]
        await update.message.reply_text(
            "Add a note (optional), or tap Skip.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # -------------------------
    # Note step -> save transaction to DB
    # -------------------------
    if state == "AWAIT_NOTE":
        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": text,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }

        telegram_id = str(update.effective_user.id)
        add_transaction(
            telegram_id=telegram_id,
            tx_type=tx["type"],
            amount=tx["amount"],
            note=tx["note"],
            ts=tx["ts"],
        )

        context.user_data.pop("pending_type", None)
        context.user_data.pop("pending_amount", None)
        context.user_data["state"] = None

        sign = "-" if tx["type"] == "expense" else "+"
        await update.message.reply_text(
            f"Saved ✅ {sign}${tx['amount']:.2f}\n"
            f"Note: {tx['note']}\n\n"
            "Type /menu to continue."
        )
        return