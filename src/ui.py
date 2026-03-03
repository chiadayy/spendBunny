from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_markup():
    keyboard = [
        [InlineKeyboardButton("➕ Expense", callback_data="EXPENSE")],
        [InlineKeyboardButton("➕ Income", callback_data="INCOME")],
        [InlineKeyboardButton("📊 Summary", callback_data="SUMMARY")],
        [InlineKeyboardButton("⏰ Schedule", callback_data="SCHEDULE")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def render_menu(query):
    await query.edit_message_text(
        "Main Menu:",
        reply_markup=main_menu_markup(),
    )


async def render_schedule(query, status: str, daily_time: str, timezone: str):
    keyboard = [
        [
            InlineKeyboardButton("Turn ON", callback_data="SCH_ON"),
            InlineKeyboardButton("Turn OFF", callback_data="SCH_OFF"),
        ],
        [InlineKeyboardButton("Set Time", callback_data="SCH_TIME")],
        [InlineKeyboardButton("Set Timezone", callback_data="SCH_TZ")],
        [InlineKeyboardButton("Back", callback_data="BACK_MENU")],
    ]

    await query.edit_message_text(
        f"⏰ Nightly Report Settings\n\n"
        f"Status: {status}\n"
        f"Time: {daily_time}\n"
        f"Timezone: {timezone}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )