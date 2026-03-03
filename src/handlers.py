import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from storage import get_user_store
from ui import main_menu_markup, render_menu, render_schedule


def parse_amount(text: str):
    try:
        return float(text.strip())
    except ValueError:
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_user_store(update, context)
    await update.message.reply_text("Welcome to your Personal Finance Bot 💰\n\nUse /menu to begin.")


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Main Menu:", reply_markup=main_menu_markup())


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_user_store(update, context)
    txns = store.get("txns", [])

    today = datetime.now().date()
    income = expense = 0.0
    count = 0

    for tx in txns:
        ts = tx.get("ts")
        if not ts:
            continue
        tx_date = datetime.fromisoformat(ts).date()
        if tx_date != today:
            continue

        amt = float(tx["amount"])
        if tx["type"] == "income":
            income += amt
        else:
            expense += amt
        count += 1

    net = income - expense

    await update.message.reply_text(
        f"📊 Summary — Today\n"
        f"Income: +${income:.2f}\n"
        f"Spent: -${expense:.2f}\n"
        f"Net: ${net:.2f}\n"
        f"Transactions: {count}\n\n"
        f"Type /menu to continue."
    )


async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    # Skip note
    if choice == "SKIP_NOTE":
        store = get_user_store(update, context)

        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": "",
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        store["txns"].append(tx)

        context.user_data.pop("pending_type", None)
        context.user_data.pop("pending_amount", None)
        context.user_data["state"] = None

        sign = "-" if tx["type"] == "expense" else "+"
        await query.edit_message_text(
            f"Saved ✅ {sign}${tx['amount']:.2f}\n\nType /menu to continue."
        )
        return

    # Main menu options
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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if choice == "SCHEDULE":
        store = get_user_store(update, context)
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(query, status, store.get("daily_time", "21:00"), store.get("timezone", "Asia/Singapore"))
        return

    # Schedule actions
    if choice == "SCH_ON":
        store = get_user_store(update, context)
        store["daily_enabled"] = True
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    if choice == "SCH_OFF":
        store = get_user_store(update, context)
        store["daily_enabled"] = False
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
        store = get_user_store(update, context)
        parts = choice.replace("SET_TIME_", "").split("_")
        hh, mm = parts[0], parts[1]
        store["daily_time"] = f"{hh}:{mm}"

        await query.edit_message_text(f"✅ Nightly time set to {hh}:{mm}")
        await asyncio.sleep(1)
        await render_menu(query)
        return

    if choice == "SET_TZ_ASIA_SINGAPORE":
        store = get_user_store(update, context)
        store["timezone"] = "Asia/Singapore"
        status = "ON ✅" if store.get("daily_enabled") else "OFF ❌"
        await render_schedule(
            query,
            status,
            store.get("daily_time", "21:00"),
            store.get("timezone", "Asia/Singapore"),
        )
        return

    if choice == "SET_TZ_ASIA_SINGAPORE":
        store = get_user_store(update, context)
        store["timezone"] = "Asia/Singapore"
        await render_schedule(query, update, context)
        return

    # Summary period computations
    def _sum_for_range(txns, start_date, end_date):
        income = expense = 0.0
        count = 0
        for tx in txns:
            ts = tx.get("ts")
            if not ts:
                continue
            d = datetime.fromisoformat(ts).date()
            if not (start_date <= d <= end_date):
                continue
            amt = float(tx["amount"])
            if tx["type"] == "income":
                income += amt
            else:
                expense += amt
            count += 1
        return income, expense, count

    if choice == "SUM_TODAY":
        store = get_user_store(update, context)
        txns = store.get("txns", [])
        today = datetime.now().date()
        inc, exp, cnt = _sum_for_range(txns, today, today)
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
        store = get_user_store(update, context)
        txns = store.get("txns", [])
        today = datetime.now().date()
        start = today.fromordinal(today.toordinal() - today.weekday())  # Monday
        end = today
        inc, exp, cnt = _sum_for_range(txns, start, end)
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
        store = get_user_store(update, context)
        txns = store.get("txns", [])
        today = datetime.now().date()
        start = today.replace(day=1)
        end = today
        inc, exp, cnt = _sum_for_range(txns, start, end)
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

    # Custom time input
    if state == "AWAIT_CUSTOM_TIME":
        t = text.strip()
        try:
            hh_str, mm_str = t.split(":")
            hh = int(hh_str)
            mm = int(mm_str)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except Exception:
            await update.message.reply_text("Invalid time. Send HH:MM in 24h format (e.g. 21:35).")
            return

        store = get_user_store(update, context)
        store["daily_time"] = f"{hh:02d}:{mm:02d}"
        context.user_data["state"] = None

        await update.message.reply_text(f"✅ Nightly time set to {hh:02d}:{mm:02d}\nType /menu to continue.")
        return

    # Expense amount
    if state == "AWAIT_EXPENSE_AMOUNT":
        amt = parse_amount(text)
        if amt is None or amt <= 0:
            await update.message.reply_text("Please send a valid positive number (e.g. 6.50).")
            return

        context.user_data["pending_amount"] = amt
        context.user_data["pending_type"] = "expense"
        context.user_data["state"] = "AWAIT_NOTE"

        keyboard = [[InlineKeyboardButton("Skip", callback_data="SKIP_NOTE")]]
        await update.message.reply_text(
            "Add a note (optional), or tap Skip.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Income amount
    if state == "AWAIT_INCOME_AMOUNT":
        amt = parse_amount(text)
        if amt is None or amt <= 0:
            await update.message.reply_text("Please send a valid positive number (e.g. 120).")
            return

        context.user_data["pending_amount"] = amt
        context.user_data["pending_type"] = "income"
        context.user_data["state"] = "AWAIT_NOTE"

        keyboard = [[InlineKeyboardButton("Skip", callback_data="SKIP_NOTE")]]
        await update.message.reply_text(
            "Add a note (optional), or tap Skip.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Note step -> save transaction
    if state == "AWAIT_NOTE":
        store = get_user_store(update, context)

        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": text,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        store["txns"].append(tx)

        context.user_data.pop("pending_type", None)
        context.user_data.pop("pending_amount", None)
        context.user_data["state"] = None

        sign = "-" if tx["type"] == "expense" else "+"
        await update.message.reply_text(
            f"Saved ✅ {sign}${tx['amount']:.2f}\n"
            f"Note: {tx['note']}\n\n"
            "Type /menu to continue."
        )
