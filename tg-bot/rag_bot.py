import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Put in your .env
API_URL = "http://localhost:3000/rag"

UPLOAD_TYPE, AWAITING_INPUT = range(2)

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Welcome to the Storacha RAG Bot!\nUse /upload to add knowledge, or /ask to query it.")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📄 PDF", callback_data="pdf")],
        [InlineKeyboardButton("🔗 URL", callback_data="url")],
        [InlineKeyboardButton("📝 Text", callback_data="text")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the type of data you want to upload:", reply_markup=reply_markup)
    return UPLOAD_TYPE

async def handle_upload_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    upload_type = query.data

    user_state[query.from_user.id] = {"type": upload_type}

    if upload_type == "pdf":
        await query.edit_message_text("📎 Please upload your PDF file now.")
    elif upload_type == "url":
        await query.edit_message_text("🔗 Please send the URL now.")
    elif upload_type == "text":
        await query.edit_message_text("📝 Please type the text you want to upload.")

    return AWAITING_INPUT

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_state.get(user_id)

    if not state:
        await update.message.reply_text("❌ Unexpected input. Use /upload first.")
        return ConversationHandler.END

    upload_type = state["type"]

    try:
        msg = await update.message.reply_text("⏳ Uploading...")

        if upload_type == "text":
            res = requests.post(f"{API_URL}/upload", json={"type": "text", "content": update.message.text})
        elif upload_type == "url":
            res = requests.post(f"{API_URL}/upload", json={"type": "url", "url": update.message.text})
        elif upload_type == "pdf":
            file = await update.message.document.get_file()
            file_path = await file.download_to_drive()
            with open(file_path, "rb") as f:
                res = requests.post(f"{API_URL}/upload", files={"file": (file_path, f, "application/pdf")}, data={"type": "pdf"})

        if res.status_code == 200:
            await msg.edit_text("✅ Upload successful!")
        else:
            await msg.edit_text(f"❌ Upload failed: {res.text}")

    except Exception as e:
        logging.error(e)
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

    return ConversationHandler.END

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Send your question:")
    return AWAITING_INPUT

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    msg = await update.message.reply_text("🔍 Searching...")

    try:
        res = requests.post(f"{API_URL}/query", json={"question": question})
        if res.status_code == 200:
            answer = res.json().get("answer", "No answer received.")
            await msg.edit_text(f"🤖 Answer:\n\n{answer}")
        else:
            await msg.edit_text(f"❌ Query failed: {res.text}")
    except Exception as e:
        logging.error(e)
        await msg.edit_text(f"⚠️ Error: {str(e)}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Cancelled.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_command)],
        states={
            UPLOAD_TYPE: [CallbackQueryHandler(handle_upload_selection)],
            AWAITING_INPUT: [MessageHandler(filters.TEXT | filters.Document.PDF, handle_user_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    ask_conv = ConversationHandler(
        entry_points=[CommandHandler("ask", ask_command)],
        states={AWAITING_INPUT: [MessageHandler(filters.TEXT, handle_query)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(upload_conv)
    app.add_handler(ask_conv)

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
