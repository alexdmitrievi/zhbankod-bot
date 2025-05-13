import os
import json
import logging
import datetime
import gspread
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
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
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("ЖБАНКОД Заявки").worksheet("Лист1")

# Установка команды меню
async def set_menu(bot):
    await bot.set_my_commands([
        BotCommand("start", "🚀 Запустить бота — покажем магию"),
        BotCommand("menu", "🏠 Вернуться в основное меню"),
        BotCommand("help", "❓ Что умеет бот и как им пользоваться")
    ])

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
    return ConversationHandler.END

# Обработка кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "services":
        await query.edit_message_text(
            "🧠 *Что мы делаем в ЖБАНКОД:*\n\n"
            "• Боты-анкеты с Google Sheets — заявки прямо в таблицу\n"
            "• Боты с онлайн-оплатой, CRM и аналитикой\n"
            "• Воронки + автопостинг в каналы\n"
            "• Логистика, тендеры, AI — делаем под ключ, под задачу\n\n"
            "⚡️ Всё под ключ. Без шаблонов. Только работающие решения.",
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
        await query.edit_message_text("📬 Введите ваше *имя* и Telegram (или ник):",
                                      parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup([
                                          [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
                                      ]))
        return ASK_NAME
    elif data == "order":
        await query.edit_message_text("💰 Чтобы получить расчёт, просто нажмите 'Оставить заявку'.")
    elif data == "cancel":
        await start(update, context)
    else:
        await query.edit_message_text("❓ Неизвестная команда.")

# Анкета с кнопками меню
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("✍️ Расскажите, *какой бот вам нужен*:",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
                                    ]))
    return ASK_PROJECT

async def ask_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project"] = update.message.text
    await update.message.reply_text("💸 Укажите *желаемый бюджет* проекта:",
                                    parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
                                    ]))
    return ASK_BUDGET

async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["budget"] = update.message.text
    user = update.message.from_user
    data = context.user_data
    date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    tg_link = f"@{user.username}" if user.username else f"https://t.me/user?id={user.id}"

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

    text = (
        f"📥 *Новая заявка!*\n\n"
        f"👤 Имя: {data['name']}\n"
        f"🧠 Проект: {data['project']}\n"
        f"💸 Бюджет: {data['budget']}\n"
        f"🔗 Telegram: {tg_link}\n"
        f"🗓️ Дата: {date}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Спасибо! Мы свяжемся с вами в Telegram.")
    return ConversationHandler.END

# /help команда
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❓ *Как пользоваться ботом ЖБАНКОД:*\n\n"
        "🚀 Нажмите `/start` или `/menu`, чтобы открыть главное меню.\n\n"
        "📬 В разделе *«Оставить заявку»* вы можете отправить нам запрос на разработку:\n"
        "• Напишите ваше имя и Telegram\n"
        "• Опишите идею бота\n"
        "• Укажите бюджет\n\n"
        "📞 Если хотите задать вопрос напрямую — просто напишите @zhbankov_alex",
        parse_mode="Markdown"
    )

    return ConversationHandler.END  # ← Вот сюда

# Отмена анкеты
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Заявка отменена.")
    return ConversationHandler.END

# Главная функция
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_menu(app.bot))

    # Глобальные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Анкетный сценарий с fallback для /help
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(callback_handler, pattern="^form$")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_project)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
        },
        fallbacks=[
            CallbackQueryHandler(callback_handler, pattern="^cancel$"),
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command)
        ],
        allow_reentry=True,
        per_message=True  # 👈 Обязательно
    )
    app.add_handler(conv_handler)

    logging.info("Бот запущен 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()


