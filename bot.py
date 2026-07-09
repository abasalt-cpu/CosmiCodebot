# -*- coding: utf-8 -*-
"""
ربات تلگرام «عدد کیهانی»
اجرا: python3 bot.py
پیش‌نیاز: pip install python-telegram-bot --upgrade
توکن ربات را در متغیر محیطی BOT_TOKEN قرار بده یا مستقیم پایین جایگزین کن.
"""
import logging
import os

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from cosmic_logic import calculate_cosmic_report, format_report

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- مراحل مکالمه ---
FIRST_NAME, FAMILY_NAME, MOTHER_NAME, BIRTH_DATE = range(4)

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🌌 به ربات «عدد کیهانی» خوش اومدی!\n\n"
        "برای محاسبه چند تا سوال کوچیک می‌پرسم.\n"
        "هر وقت خواستی، با /cancel می‌تونی لغو کنی.\n\n"
        "لطفاً *نام* خودت رو بفرست:",
        parse_mode="Markdown",
    )
    return FIRST_NAME


async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["first_name"] = update.message.text.strip()
    await update.message.reply_text("نام خانوادگی‌ت چیه؟")
    return FAMILY_NAME


async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["family_name"] = update.message.text.strip()
    await update.message.reply_text("نام مادرت چیه؟")
    return MOTHER_NAME


async def get_mother_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["mother_name"] = update.message.text.strip()
    await update.message.reply_text(
        "تاریخ تولدت (شمسی) رو به فرمت روز/ماه/سال بفرست.\n"
        "مثال: 15/5/1370"
    )
    return BIRTH_DATE


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        parts = text.replace("-", "/").split("/")
        jd, jm, jy = int(parts[0]), int(parts[1]), int(parts[2])
        if not (1 <= jd <= 31 and 1 <= jm <= 12 and 1300 <= jy <= 1420):
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ فرمت تاریخ درست نیست. دوباره به شکل روز/ماه/سال بفرست (مثلاً 15/5/1370):"
        )
        return BIRTH_DATE

    ud = context.user_data
    data = calculate_cosmic_report(
        ud["first_name"], ud["family_name"], ud["mother_name"], jy, jm, jd
    )
    full_name = f"{ud['first_name']} {ud['family_name']}"
    await update.message.reply_text(
        format_report(full_name, data),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text("برای محاسبه‌ی دوباره، دستور /start رو بزن.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "لغو شد. هر وقت خواستی با /start دوباره شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    if TOKEN == "PUT-YOUR-TOKEN-HERE":
        raise SystemExit(
            "توکن ربات تنظیم نشده. متغیر محیطی BOT_TOKEN رو ست کن یا مستقیم توی bot.py بذار."
        )

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            MOTHER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mother_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
