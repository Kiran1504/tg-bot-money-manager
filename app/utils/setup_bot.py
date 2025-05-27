from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
from app.db.crud import create_user, create_account, get_user
from app.db.session import get_db

ASK_NAME, ASK_ACCOUNT_NAME, ASK_INITIAL_BALANCE, ASK_ADD_ANOTHER = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = get_db()
    telegram_id = update.effective_user.id
    user = get_user(db, telegram_id)
    context.user_data["telegram_id"] = telegram_id

    if user:
        await update.message.reply_text(f"Welcome back, {user.name}!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Welcome! Let's set up your expense tracker. What should I call you?")
        return ASK_NAME

async def ask_account_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text.strip()
    context.user_data["accounts"] = []
    await update.message.reply_text("Name your first account (e.g., Cash, HDFC, SBI):")
    return ASK_ACCOUNT_NAME

async def ask_initial_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["current_account_name"] = update.message.text.strip()
    await update.message.reply_text(f"What’s the initial balance in {context.user_data['current_account_name']}?")
    return ASK_INITIAL_BALANCE

async def save_account_and_ask_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        balance = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return ASK_INITIAL_BALANCE

    context.user_data["accounts"].append({
        "name": context.user_data["current_account_name"],
        "balance": balance
    })

    await update.message.reply_text("Do you want to add another account? (yes/no)")
    return ASK_ADD_ANOTHER

async def ask_next_or_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text.strip().lower()
    if answer in ["yes", "y"]:
        await update.message.reply_text("Name your next account:")
        return ASK_ACCOUNT_NAME
    else:
        db = get_db()
        telegram_id = context.user_data["telegram_id"]
        name = context.user_data["name"]
        user = create_user(db, telegram_id, name)

        for acc in context.user_data["accounts"]:
            create_account(db, user.id, acc["name"], acc["balance"])

        await update.message.reply_text(f"Setup complete! Your accounts are ready, {name}.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Setup cancelled.")
    return ConversationHandler.END

def get_setup_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_account_name)],
            ASK_ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_initial_balance)],
            ASK_INITIAL_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_account_and_ask_more)],
            ASK_ADD_ANOTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_next_or_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
