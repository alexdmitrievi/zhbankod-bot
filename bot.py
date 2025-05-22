import os
import json
import logging
import datetime
import gspread
import asyncio
from openai import OpenAI

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
from google.oauth2.service_account import Credentials

main_menu_keyboard = ReplyKeyboardMarkup([
    ["🧠 Услуги", "📂 Примеры работ"],
    ["📬 Оставить заявку", "💰 Заказать и оплатить"],
    ["🤖 Задать вопрос GPT-сотруднику"],
    ["📞 Связаться с менеджером"]
], resize_keyboard=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables")

creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
if not creds_json:
    raise ValueError("GCP_CREDENTIALS_JSON is not set in environment variables")

ADMIN_ID = 407721399
CHANNEL_ID = -1002616572459
BOT_USERNAME = "@zhbankod_bot"

logging.basicConfig(level=logging.INFO)

(ASK_NAME, ASK_PROJECT, ASK_BUDGET) = range(3)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gs_client = gspread.authorize(creds)
sheet = gs_client.open("ЖБАНКОД Заявки").worksheet("Лист1")

async def set_menu(bot):
    commands = [
        BotCommand("start", "🚀 Запустить бота — покажем магию"),
        BotCommand("menu", "🏠 Вернуться в основное меню"),
        BotCommand("help", "❓ Что умеет бот и как им пользоваться")
    ]
    if ADMIN_ID:
        commands.append(BotCommand("publish", "📢 Опубликовать пост в канал (для админа)"))
    await bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = (
        "👋 Привет! Мы — <b>ЖБАНКОД</b>, создаём Telegram-ботов, которые приносят заявки, деньги и автоматизируют ваш бизнес.\n\n"
        "⚙️ Хотите анкету, CRM, приём оплаты или кастомное решение под ваши задачи?\n"
        "👇 Просто выберите, что вас интересует — и мы покажем, как это работает:"
    )
    with open("THIS_IS_ZHBANKOD.jpg", "rb") as photo:
        if update.message:
            await update.message.reply_photo(photo=photo, caption=message_text, reply_markup=main_menu_keyboard, parse_mode="HTML")
        elif update.callback_query:
            await update.callback_query.message.reply_photo(photo=photo, caption=message_text, reply_markup=main_menu_keyboard, parse_mode="HTML")
    return ConversationHandler.END

async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 <b>Что мы сделаем для вашего бизнеса:</b>\n\n"
        "✅ Автоформы — заявки сразу в Google Sheets без потерь\n"
        "✅ Приём оплаты прямо в боте (без сайта и программиста)\n"
        "✅ Воронки, автопостинг и автоответы — работаем на автопилоте\n"
        "✅ AI, логистика, тендеры — любые задачи под ключ\n"
        "✅ GPT-сотрудники — онлайн-консультанты, которые отвечают за вас 24/7\n\n"
        "⚙️ Всё под ключ. Без шаблонов. Только то, что приносит результат.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard
    )

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 <b>Наши кейсы:</b>\n\n"
        "• @Parser_newbot — бот для логистов\n"
        "• @Capitalpay_newbot — анкета для HighRisk команд\n"
        "• @bez_otkaza_bot — бот для кредитных брокеров с GPT и таблицей\n\n"
        "Мы не просто показываем кнопки. Мы запускаем работающие решения.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard
    )

async def form_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["form_step"] = "ask_name"
    await update.message.reply_text(
        "✍️ Введите ваше имя:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
        ])
    )

async def form_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get("form_step")

    # 📍 Если пользователь только нажал кнопку "Оставить заявку"
    if "Оставить заявку" in text and not step:
        return await form_entry(update, context)

    if step == "ask_name":
        context.user_data["name"] = update.message.text
        context.user_data["form_step"] = "ask_project"
        await update.message.reply_text(
            "✍️ Расскажите, *какой бот вам нужен*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
            ])
        )
        return

    if step == "ask_project":
        context.user_data["project"] = update.message.text
        context.user_data["form_step"] = "ask_budget"
        await update.message.reply_text(
            "💸 Укажите *желаемый бюджет* проекта:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
            ])
        )
        return

    if step == "ask_budget":
        context.user_data["budget"] = update.message.text
        context.user_data["form_step"] = None

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
            await update.message.reply_text("⚠️ Ошибка при сохранении заявки. Попробуйте позже.", reply_markup=main_menu_keyboard)
            return

        text = (
            f"📥 *Новая заявка!*\n\n"
            f"👤 Имя: {data['name']}\n"
            f"🧠 Проект: {data['project']}\n"
            f"💸 Бюджет: {data['budget']}\n"
            f"🔗 Telegram: {tg_link}\n"
            f"🗓️ Дата: {date}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="Markdown")
        await update.message.reply_text("✅ Спасибо! Мы свяжемся с вами в Telegram.", reply_markup=main_menu_keyboard)
        return

    # Если ни одно условие не сработало — отправим в GPT
    return await gpt_reply(update, context)

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚧 Раздел 'Заказать и оплатить' скоро будет доступен.", reply_markup=main_menu_keyboard)

async def ask_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 Напиши свой вопрос, и наш GPT-сотрудник ответит вам прямо здесь:",
        reply_markup=main_menu_keyboard
    )
    context.user_data["awaiting_gpt"] = True

async def gpt_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_gpt"):
        return

    question = update.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты — эксперт по созданию Telegram-ботов для бизнеса. "
                        "Отвечай только на вопросы, связанные с чат-ботами в Telegram: "
                        "автоматизация, воронки, CRM, приём заявок и оплат, интеграции и т.п.\n\n"
                        "Если вопрос не по теме Telegram-ботов, мягко уточни и направь клиента к кнопке «Связаться с менеджером»."
                    )
                },
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=600
        )

        answer = response.choices[0].message.content.strip()
        await update.message.reply_text(answer, reply_markup=main_menu_keyboard)
        await update.message.reply_text("✍️ Можете задать следующий вопрос или нажмите /menu для возврата в главное меню.", reply_markup=main_menu_keyboard)
        context.user_data["awaiting_gpt"] = False

    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка при обращении к GPT. Попробуйте позже.", reply_markup=main_menu_keyboard)
        logging.error(f"GPT Error: {e}")
        context.user_data["awaiting_gpt"] = False

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "✍️ Расскажите, *какой бот вам нужен*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
        ])
    )
    return ASK_PROJECT

async def ask_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["project"] = update.message.text
    await update.message.reply_text(
        "💸 Укажите *желаемый бюджет* проекта:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="cancel")]
        ])
    )
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
        await update.message.reply_text("⚠️ Ошибка при сохранении заявки. Попробуйте позже.", reply_markup=main_menu_keyboard)
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
    await update.message.reply_text("✅ Спасибо! Мы свяжемся с вами в Telegram.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Заявка отменена.", reply_markup=main_menu_keyboard)
    return ConversationHandler.END

async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👨‍💼 Напишите @zhbankov_alex — он поможет с любыми вопросами.", reply_markup=main_menu_keyboard)

async def publish_welcome_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Команда доступна только администратору.", reply_markup=main_menu_keyboard)
        return

    text = (
        "<b>📌 💔 Ты не вернулся к бывшей. Не возвращайся и к ручной работе.</b>\n"
        "<b>ЖБАНКОД</b> — создаём Telegram-ботов, которые делают всё за тебя.\n\n"
        "🤖 Заявки, оплаты, воронки, документы и даже переписку с клиентами — бот берёт на себя рутину, пока ты занимаешься бизнесом.\n\n"
        "✅ Заявки — сразу в таблицу\n"
        "✅ Оплаты — прямо в Telegram, без сайтов и программистов\n"
        "✅ Воронки, автоответы, автопостинг — всё на автопилоте\n"
        "✅ Онлайн-сотрудники на базе ChatGPT — отвечают, обучаются, закрывают рутину\n"
        "✅ Подходит для агентств, команд, логистов, ВЭД, трафика и не только\n\n"
        "📂 <b>Даём все документы</b> — можно списать в расходы\n\n"
        "📚 В этом канале — кейсы, шаблоны и автоматизации, которые приносят результат\n\n"
        "📝 <b>Хочешь такого же бота под свой бизнес?</b>\n"
        "📎 <a href='https://docs.google.com/spreadsheets/d/1eI1SkiA37tWKz9S5HCBl1XV8flODGOBL/edit?usp=sharing'>Скачать короткий бриф (2–3 минуты)</a>\n\n"
        f"👇 Или просто нажми кнопку, чтобы оставить заявку:\n{BOT_USERNAME}\n\n"
        "💬 Есть вопросы или хочешь обсудить? Пиши в наш чат:\n"
        "<a href='https://t.me/+bAejsng5mFRmMWZi'>ЖБАНКОД | Обсуждение</a>\n\n"
        "#жбанкод #ботдлябизнеса #лидогенерация #автоматизация #чатбот #ботдлялогистики"
    )

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📬 Оставить заявку", url=f"https://t.me/{BOT_USERNAME.replace('@', '')}")]
    ])
    with open("THIS_IS_ZHBANKOD.jpg", "rb") as photo:
        message = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo,
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        await context.bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=message.message_id)
        await update.message.reply_text("✅ Пост с картинкой опубликован и закреплён.", reply_markup=main_menu_keyboard)

# Осталась главная функция main()

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "cancel":
        await start(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❓ <b>Как пользоваться ботом ЖБАНКОД:</b>\n\n"
        "🚀 Нажмите <code>/start</code> или <code>/menu</code>, чтобы открыть главное меню.\n\n"
        "📬 В разделе <b>«Оставить заявку»</b> вы можете отправить нам запрос:\n"
        "• Напишите ваше имя и Telegram\n"
        "• Опишите идею бота\n"
        "• Укажите бюджет\n\n"
        "📞 Или сразу пишите <a href='https://t.me/zhbankov_alex'>@zhbankov_alex</a>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard
    )
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_menu(app.bot))

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("publish", publish_welcome_post))

    # Обработка inline-кнопки "Вернуться в меню"
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^cancel$"))

    # Reply-кнопки
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🧠 Услуги$"), services))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📂 Примеры работ$"), portfolio))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^💰 Заказать и оплатить$"), order))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📞 Связаться с менеджером$"), contact_manager))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🤖 Задать вопрос GPT-сотруднику$"), ask_gpt))

    # Универсальный роутер по анкете и GPT
    app.add_handler(MessageHandler(filters.TEXT, form_router))

    logging.info("Бот запущен 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()

