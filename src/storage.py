from telegram import Update
from telegram.ext import ContextTypes


def get_user_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """
    Single source of truth for each user's data.
    Stored in context.application.bot_data["users"][user_id]
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    context.application.bot_data.setdefault("users", {})
    context.application.bot_data["users"].setdefault(user_id, {
        "chat_id": chat_id,
        "txns": [],
        "daily_enabled": False,
        "daily_time": "21:00",
        "timezone": "Asia/Singapore",
        "last_sent_date": None,
    })

    # keep chat_id updated
    context.application.bot_data["users"][user_id]["chat_id"] = chat_id
    return context.application.bot_data["users"][user_id]