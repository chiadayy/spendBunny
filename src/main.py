import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to your Personal Finance Bot 💰\n\n"
        "Use /menu to begin."
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Main Menu:\n"
        "➕ Expense\n"
        "➕ Income\n"
        "📊 Summary\n"
        "⏰ Schedule\n\n"
        "(We’ll wire buttons next)"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()