# -*- coding: utf-8 -*-
"""
ربات تلگرام «عدد کیهانی»
اجرا: python3 bot.py
پیش‌نیاز: pip install -r requirements.txt

متغیرهای محیطی:
    BOT_TOKEN     (اجباری) توکن ربات از BotFather
    ADMIN_ID      (اختیاری) آیدی عددی تلگرام مدیر، برای /stats و بکاپ روزانه
    DAILY_LIMIT   (اختیاری، پیش‌فرض ۵) سقف تعداد محاسبه در روز برای هر کاربر
    DB_PATH       (اختیاری) مسیر فایل دیتابیس (برای Volume دائمی روی Railway)
"""
import logging
import os
from datetime import time as dt_time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from cosmic_logic import calculate_cosmic_report, format_report
import database
import image_report

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- مراحل مکالمه ---
FIRST_NAME, FAMILY_NAME, MOTHER_NAME, BIRTH_DATE = range(4)

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
ADMIN_ID = os.environ.get("ADMIN_ID")
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "5"))

RESULT_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🔄 محاسبه جدید", callback_data="new_calc"),
            InlineKeyboardButton("📜 تاریخچه من", callback_data="show_history"),
        ]
    ]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    try:
        used_today = database.count_today(user.id)
    except Exception:
        logger.exception("خطا در بررسی محدودیت روزانه")
        used_today = 0

    if used_today >= DAILY_LIMIT:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text(
            f"⛔ شما امروز به سقف {DAILY_LIMIT} محاسبه رسیدی. فردا دوباره امتحان کن."
        )
        return ConversationHandler.END

    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(
        "🌌 به ربات «عدد کیهانی» خوش اومدی!\n\n"
        "برای محاسبه چند تا سوال کوچیک می‌پرسم.\n"
        "هر وقت خواستی، با /cancel می‌تونی لغو کنی.\n\n"
        "لطفاً *نام* خودت رو بفرست:",
        parse_mode="Markdown",
    )
    return FIRST_NAME


async def start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await start(update, context)


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

    try:
        user = update.effective_user
        database.save_submission(
            telegram_id=user.id,
            telegram_username=user.username or "",
            first_name=ud["first_name"],
            family_name=ud["family_name"],
            mother_name=ud["mother_name"],
            jy=jy, jm=jm, jd=jd,
            report=data,
        )
    except Exception:
        logger.exception("خطا در ذخیره‌سازی دیتابیس")

    # تلاش برای ارسال تصویر گزارش؛ اگه فونت/کتابخونه نبود، فقط متن ارسال می‌شه
    image_sent = False
    try:
        if image_report.fonts_available():
            buf = image_report.render_report_image(full_name, data)
            await update.message.reply_photo(photo=buf)
            image_sent = True
    except Exception:
        logger.exception("خطا در ساخت/ارسال تصویر گزارش")

    await update.message.reply_text(
        format_report(full_name, data),
        parse_mode="Markdown",
        reply_markup=RESULT_KEYBOARD,
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "لغو شد. هر وقت خواستی با /start دوباره شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌌 *راهنمای ربات عدد کیهانی*\n\n"
        "/start — شروع محاسبه‌ی جدید\n"
        "/history — دیدن نتایج قبلی خودت\n"
        "/cancel — لغو مکالمه‌ی جاری\n"
        "/help — همین راهنما",
        parse_mode="Markdown",
    )


async def _send_history(target_message, telegram_id: int) -> None:
    try:
        rows = database.get_user_history(telegram_id)
    except Exception:
        logger.exception("خطا در خواندن تاریخچه")
        await target_message.reply_text("مشکلی در خواندن تاریخچه پیش اومد.")
        return

    if not rows:
        await target_message.reply_text("هنوز هیچ محاسبه‌ای ثبت نکردی. با /start شروع کن.")
        return

    lines = ["🕓 *آخرین محاسبات تو:*\n"]
    for r in rows:
        lines.append(
            f"• {r['first_name']} {r['family_name']} — کد: `{r['cosmic_code']}` "
            f"(سرنوشت {r['destiny_num']}, تقدیر {r['fate_num']}, ارتعاش {r['vibration_num']})\n"
            f"  {r['created_at'][:10]}"
        )
    await target_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_history(update.message, update.effective_user.id)


async def history_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await _send_history(update.callback_query.message, update.effective_user.id)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not ADMIN_ID or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return

    try:
        s = database.get_stats()
    except Exception:
        logger.exception("خطا در خواندن آمار")
        await update.message.reply_text("مشکلی در خواندن آمار پیش اومد.")
        return

    lines = [
        "📊 *آمار ربات*\n",
        f"👥 تعداد کاربران یکتا: {s['unique_users']}",
        f"🧮 تعداد کل محاسبات: {s['total_submissions']}\n",
        "*۵ محاسبه‌ی اخیر:*",
    ]
    for r in s["latest"]:
        lines.append(f"• {r['first_name']} {r['family_name']} — {r['created_at'][:16]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def daily_backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """هر شب فایل دیتابیس رو برای ادمین می‌فرسته (چون دیسک Railway ممکنه پایدار نباشه)."""
    if not ADMIN_ID:
        return
    try:
        with open(database.DB_PATH, "rb") as f:
            await context.bot.send_document(
                chat_id=int(ADMIN_ID),
                document=f,
                filename="cosmic_bot_backup.db",
                caption="📦 بکاپ روزانه‌ی دیتابیس ربات عدد کیهانی",
            )
    except FileNotFoundError:
        logger.warning("فایل دیتابیس برای بکاپ پیدا نشد.")
    except Exception:
        logger.exception("خطا در ارسال بکاپ روزانه")


def main() -> None:
    if TOKEN == "PUT-YOUR-TOKEN-HERE":
        raise SystemExit(
            "توکن ربات تنظیم نشده. متغیر محیطی BOT_TOKEN رو ست کن یا مستقیم توی bot.py بذار."
        )

    database.init_db()

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_from_button, pattern="^new_calc$"),
        ],
        states={
            FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            MOTHER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mother_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(history_from_button, pattern="^show_history$"))

    if application.job_queue is not None and ADMIN_ID:
        application.job_queue.run_daily(daily_backup_job, time=dt_time(hour=23, minute=55))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
