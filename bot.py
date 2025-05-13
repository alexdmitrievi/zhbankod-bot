from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler, ConversationHandler
)
import logging
import datetime
import gspread
from google.oauth2.service_account import Credentials

TOKEN = "YOUR_TOKEN_HERE"
ADMIN_ID = 407721399

logging.basicConfig(level=logging.INFO)

(ASK_NAME, ASK_PROJECT, ASK_BUDGET) = range(3)

# Google Sheets Setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("zhbankod_gsheets_credentials.json", scopes=SCOPES)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("ЖБАНКОД Заявки").sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 Услуги", callback_data="services")],
        [InlineKeyboardButton("📂 Примеры работ", callback_data="portfolio")],
        [InlineKeyboardButton("📬 Оставить заявку", callback_data="form")],
        [InlineKeyboardButton("💰 Заказать и оплатить", callback_data="order")],
        [InlineKeyboardButton("📞 Связаться", url="https://t.me/zhbankov_alex")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Добро пожаловать в ЖБАНКОД — разработка Telegram-ботов под ключ!", reply_markup=reply_markup)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "services":
        await query.edit_message_text(
            "🧠 *Услуги ЖБАНКОД:*

"
            "• Анкетные боты с Google Sheets
"
            "• Боты с оплатой и интеграциями
"
            "• Воронки + постинг в канал
",
            parse_mode="Markdown"
        )
    elif data == "portfolio":
        await query.edit_message_text(
            "📂 *Примеры проектов:*

"
            "• @Parser_newbot — бот для логистики с документами
"
            "• @Capitalpay_newbot — HighRisk анкета с автоворонкой
",
            parse_mode="Markdown"
        )
    elif data == "form":
        await query.edit_message_text("📬 Введите ваше имя и Telegram (или ник):")
        return ASK_NAME
    elif data == "order":
        await query.edit_message_text("💰 Чтобы получить расчёт, просто нажмите 'Оставить заявку'.")
    else:
        await query.edit_message_text("❓ Неизвестная команда.")

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📝 Опишите, какой бот вам нужен:")
    return ASK_PROJECT

async def ask_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project"] = update.message.text
    await update.message.reply_text("💸 Укажите желаемый бюджет:")
    return ASK_BUDGET

async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["budget"] = update.message.text
    user = update.message.from_user
    data = context.user_data

    date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    tg_link = f"@{user.username}" if user.username else f"https://t.me/user?id={user.id}"

    # Запись в Google Sheets
    sheet.append_row([
        data['name'],
        data['project'],
        data['budget'],
        tg_link,
        date
    ])

    # Отправка админу
    text = (
        f"📥 *Новая заявка!*

"
        f"👤 Имя: {data['name']}
"
        f"🧠 Проект: {data['project']}
"
        f"💸 Бюджет: {data['budget']}
"
        f"🔗 Telegram: {tg_link}
"
        f"📅 Дата: {date}"
    )

    await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Спасибо! Мы свяжемся с вами в Telegram.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Заявка отменена.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^form$")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_project)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
