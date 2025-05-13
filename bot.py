import os
import json
import logging
import datetime
import gspread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler, ConversationHandler
)
from google.oauth2.service_account import Credentials

# Переменные окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables")

creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
if not creds_json:
    raise ValueError("GCP_CREDENTIALS_JSON is not set in environment variables")

ADMIN_ID = 407721399

# Логирование
logging.basicConfig(level=logging.INFO)

# Состояния анкеты
(ASK_NAME, ASK_PROJECT, ASK_BUDGET) = range(3)

# Настройка Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("ЖБАНКОД Заявки").worksheet("Лист1")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 Услуги", callback_data="services")],
        [InlineKeyboardButton("📂 Примеры работ", callback_data="portfolio")],
        [InlineKeyboardButton("📬 Оставить заявку", callback_data="form")],
        [InlineKeyboardButton("💰 Заказать и оплатить", callback_data="order")],
        [InlineKeyboardButton("📞 Связаться", url="https://t.me/zhbankov_alex")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Добро пожаловать в ЖБАНКОД — разработка Telegram-ботов под ключ!",
        reply_markup=reply_markup
    )

# Обработка кнопок меню
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "services":
        await query.edit_message_text(
            "🧠 *Услуги ЖБАНКОД:*\n\n"
            "• Анкетные боты с Google Sheets\n"
            "• Боты с оплатой и интеграциями\n"
            "• Воронки + постинг в канал\n"
            "• И множество других решений под ваши задачи — от логистики до AI-ботов 🤖",
            parse_mode="Markdown"
        )
    elif data == "portfolio":
        await query.edit_message_text(
            "📂 *Примеры проектов:*\n\n"
            "• @Parser_newbot — бот для логистики с документами\n"
            "• @Capitalpay_newbot — HighRisk анкета с автоворонкой",
            parse_mode="Markdown"
        )
    elif data == "form":
        await query.edit_message_text("📬 Введите ваше имя и Telegram (или ник):")
        return ASK_NAME
    elif data == "order":
        await query.edit_message_text("💰 Чтобы получить расчёт, просто нажмите 'Оставить заявку'.")
    else:
        await query.edit_message_text("❓ Неизвестная команда.")

# Шаги анкеты
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
    try:
        sheet.append_row([
            data['name'],
            data['project'],
            data['budget'],
            tg_link,
            date
        ])
    except Exception as e:
        logging.error(f"Ошибка при записи в Google Sheets: {e}")
        await update.message.reply_text("⚠️ Ошибка при сохранении заявки. Попробуйте позже.")
        return ConversationHandler.END

    # Отправка админу
    text = (
        f"📥 *Новая заявка!*\n\n"
        f"👤 Имя: {data['name']}\n"
        f"🧠 Проект: {data['project']}\n"
        f"💸 Бюджет: {data['budget']}\n"
        f"🔗 Telegram: {tg_link}\n"
        f"📅 Дата: {date}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Спасибо! Мы свяжемся с вами в Telegram.")
    return ConversationHandler.END

# Отмена анкеты
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Заявка отменена.")
    return ConversationHandler.END

# Запуск бота
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
        allow_reentry=True
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
