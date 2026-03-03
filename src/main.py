import os
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from handlers import start, menu, summary, on_menu_click, on_text
from scheduler import send_nightly_summary

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
scheduler = AsyncIOScheduler()


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("summary", summary))

    # Buttons + free text
    app.add_handler(CallbackQueryHandler(on_menu_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # Nightly checker: runs every minute, sends only when time matches
    scheduler.add_job(
        send_nightly_summary,
        "cron",
        minute="*",
        args=[app],
    )
    scheduler.start()

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()