import os
from dotenv import load_dotenv
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


# -------------------------
# Helpers
# -------------------------

def parse_amount(text: str):
    try:
        return float(text.strip())
    except ValueError:
        return None


# -------------------------
# Command Handlers
# -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to your Personal Finance Bot 💰\n\n"
        "Use /menu to begin."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Expense", callback_data="EXPENSE")],
        [InlineKeyboardButton("➕ Income", callback_data="INCOME")],
        [InlineKeyboardButton("📊 Summary", callback_data="SUMMARY")],
        [InlineKeyboardButton("⏰ Schedule", callback_data="SCHEDULE")],
    ]

    await update.message.reply_text(
        "Main Menu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -------------------------
# Callback Handler
# -------------------------

async def on_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data

    # Handle Skip Note
    if choice == "SKIP_NOTE":
        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": note,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }

        context.user_data.setdefault("txns", []).append(tx)

        context.user_data.pop("pending_type", None)
        context.user_data.pop("pending_amount", None)
        context.user_data["state"] = None

        sign = "-" if tx["type"] == "expense" else "+"
        await query.edit_message_text(
            f"Saved ✅ {sign}${tx['amount']:.2f}\n\nType /menu to continue."
        )
        return

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
        enabled = context.user_data.get("daily_enabled", False)
        daily_time = context.user_data.get("daily_time", "21:00")
        tz = context.user_data.get("timezone", "Asia/Singapore")

        status = "ON ✅" if enabled else "OFF ❌"

        keyboard = [
            [InlineKeyboardButton("Turn ON", callback_data="SCH_ON"),
            InlineKeyboardButton("Turn OFF", callback_data="SCH_OFF")],
            [InlineKeyboardButton("Set Time", callback_data="SCH_TIME")],
            [InlineKeyboardButton("Set Timezone", callback_data="SCH_TZ")],
            [InlineKeyboardButton("Back", callback_data="BACK_MENU")],
        ]

        await query.edit_message_text(
            f"⏰ Nightly Report Settings\n\n"
            f"Status: {status}\n"
            f"Time: {daily_time}\n"
            f"Timezone: {tz}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    if choice == "SCH_ON":
        context.user_data["daily_enabled"] = True
        await query.edit_message_text("✅ Nightly report turned ON.\n\nGo back to ⏰ Schedule to view settings.")
        return

    if choice == "SCH_OFF":
        context.user_data["daily_enabled"] = False
        await query.edit_message_text("❌ Nightly report turned OFF.\n\nGo back to ⏰ Schedule to view settings.")
        return

    if choice == "SCH_TIME":
        keyboard = [
            [InlineKeyboardButton("8:00 PM", callback_data="SET_TIME_20_00")],
            [InlineKeyboardButton("9:00 PM", callback_data="SET_TIME_21_00")],
            [InlineKeyboardButton("10:00 PM", callback_data="SET_TIME_22_00")],
            [InlineKeyboardButton("Back", callback_data="SCHEDULE")],
        ]
        await query.edit_message_text("Pick a time:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if choice.startswith("SET_TIME_"):
        # format like SET_TIME_21_00
        parts = choice.replace("SET_TIME_", "").split("_")
        hh = parts[0]
        mm = parts[1]
        context.user_data["daily_time"] = f"{hh}:{mm}"
        await query.edit_message_text(f"✅ Time set to {hh}:{mm}.\n\nGo back to ⏰ Schedule.")
        return

    if choice == "SCH_TZ":
        keyboard = [
            [InlineKeyboardButton("Singapore (Asia/Singapore)", callback_data="SET_TZ_ASIA_SINGAPORE")],
            [InlineKeyboardButton("Back", callback_data="SCHEDULE")],
        ]
        await query.edit_message_text("Pick a timezone:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if choice == "SET_TZ_ASIA_SINGAPORE":
        context.user_data["timezone"] = "Asia/Singapore"
        await query.edit_message_text("✅ Timezone set to Asia/Singapore.\n\nGo back to ⏰ Schedule.")
        return    
    
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
        txns = context.user_data.get("txns", [])
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
        txns = context.user_data.get("txns", [])
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
        txns = context.user_data.get("txns", [])
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
        keyboard = [
            [InlineKeyboardButton("➕ Expense", callback_data="EXPENSE")],
            [InlineKeyboardButton("➕ Income", callback_data="INCOME")],
            [InlineKeyboardButton("📊 Summary", callback_data="SUMMARY")],
            [InlineKeyboardButton("⏰ Schedule", callback_data="SCHEDULE")],
        ]
        await query.edit_message_text(
            "Main Menu:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


# -------------------------
# Text Message Handler
# -------------------------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if not state:
        return

    text = (update.message.text or "").strip()

    context.user_data.setdefault("txns", [])

    # -------- Expense Amount --------
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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # -------- Income Amount --------
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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # -------- Note Step --------
    if state == "AWAIT_NOTE":
        note = text

        tx = {
            "type": context.user_data.get("pending_type"),
            "amount": context.user_data.get("pending_amount"),
            "note": note,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }

        context.user_data["txns"].append(tx)

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


# -------------------------
# Main
# -------------------------
from datetime import datetime, date

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txns = context.user_data.get("txns", [])
    
    from datetime import date
    today = date.today()
    income = 0.0
    expense = 0.0
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

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(on_menu_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CommandHandler("summary", summary))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()