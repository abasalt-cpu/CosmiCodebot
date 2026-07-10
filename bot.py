# -*- coding: utf-8 -*-
"""
ربات تلگرام «عدد کیهانی»
اجرا: python3 bot.py
پیش‌نیاز: pip install -r requirements.txt

متغیرهای محیطی:
    BOT_TOKEN     (اجباری) توکن ربات از BotFather
    ADMIN_ID      (اختیاری) آیدی عددی تلگرام مدیر، برای /stats، /export، /broadcast، /ban و بکاپ روزانه
    DAILY_LIMIT   (اختیاری، پیش‌فرض ۵) سقف تعداد محاسبه در روز برای هر کاربر
    DB_PATH       (اختیاری) مسیر فایل دیتابیس (برای Volume دائمی روی Railway)
"""
import asyncio
import csv
import io
import logging
import os
import urllib.parse
from datetime import time as dt_time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.error import TelegramError
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
FIRST_NAME, FAMILY_NAME, MOTHER_NAME, BIRTH_DAY, BIRTH_MONTH, BIRTH_YEAR = range(6)

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
ADMIN_ID = os.environ.get("ADMIN_ID")
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "5"))

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

MONTH_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(PERSIAN_MONTHS[i], callback_data=f"month_{i + 1}"),
            InlineKeyboardButton(PERSIAN_MONTHS[i + 1], callback_data=f"month_{i + 2}"),
        ]
        for i in range(0, 12, 2)
    ]
)


def _is_admin(user_id: int) -> bool:
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID)


def _result_keyboard(data: dict, full_name: str) -> InlineKeyboardMarkup:
    share_text = (
        f"🌌 گزارش عدد کیهانی {full_name}\n"
        f"کد کیهانی: {data['cosmic_code']}\n"
        f"عدد سرنوشت: {data['destiny_num']} | عدد تقدیر: {data['fate_num']}"
    )
    share_url = "https://t.me/share/url?" + urllib.parse.urlencode({"url": "", "text": share_text})
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 محاسبه جدید", callback_data="new_calc"),
                InlineKeyboardButton("📜 تاریخچه من", callback_data="show_history"),
            ],
            [InlineKeyboardButton("🔗 اشتراک‌گذاری نتیجه", url=share_url)],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    target = update.callback_query.message if update.callback_query else update.message

    try:
        database.touch_user(user.id, user.username or "")
    except Exception:
        logger.exception("خطا در ثبت کاربر")

    try:
        if database.is_banned(user.id):
            await target.reply_text("⛔ دسترسی شما به این ربات مسدود شده است.")
            return ConversationHandler.END
    except Exception:
        logger.exception("خطا در بررسی وضعیت مسدودی")

    try:
        used_today = database.count_today(user.id)
    except Exception:
        logger.exception("خطا در بررسی محدودیت روزانه")
        used_today = 0

    if used_today >= DAILY_LIMIT:
        await target.reply_text(
            f"⛔ شما امروز به سقف {DAILY_LIMIT} محاسبه رسیدی. فردا دوباره امتحان کن."
        )
        return ConversationHandler.END

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
    await update.message.reply_text("روز تولدت (شمسی) رو به عدد بفرست (مثلاً 15):")
    return BIRTH_DAY


async def get_birth_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1 <= int(text) <= 31):
        await update.message.reply_text("❌ عدد روز باید بین ۱ تا ۳۱ باشه. دوباره بفرست:")
        return BIRTH_DAY
    context.user_data["jd"] = int(text)
    await update.message.reply_text("ماه تولدت رو انتخاب کن:", reply_markup=MONTH_KEYBOARD)
    return BIRTH_MONTH


async def get_birth_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    month_num = int(query.data.split("_")[1])
    context.user_data["jm"] = month_num
    await query.message.reply_text(
        f"ماه انتخابی: {PERSIAN_MONTHS[month_num - 1]} ✅\n\nسال تولدت (شمسی) رو به عدد بفرست (مثلاً 1370):"
    )
    return BIRTH_YEAR


async def get_birth_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not (text.isdigit() and 1300 <= int(text) <= 1420):
        await update.message.reply_text("❌ سال باید بین ۱۳۰۰ تا ۱۴۲۰ باشه. دوباره بفرست:")
        return BIRTH_YEAR

    ud = context.user_data
    jy = int(text)
    jm = ud["jm"]
    jd = ud["jd"]

    data = calculate_cosmic_report(ud["first_name"], ud["family_name"], ud["mother_name"], jy, jm, jd)
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

    try:
        if image_report.fonts_available():
            buf = image_report.render_report_image(full_name, data)
            await update.message.reply_photo(photo=buf)
    except Exception:
        logger.exception("خطا در ساخت/ارسال تصویر گزارش")

    await update.message.reply_text(
        format_report(full_name, data),
        parse_mode="Markdown",
        reply_markup=_result_keyboard(data, full_name),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "لغو شد. هر وقت خواستی با /start دوباره شروع کن.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🌌 *راهنمای ربات عدد کیهانی*\n\n"
        "/start — شروع محاسبه‌ی جدید\n"
        "/history — دیدن نتایج قبلی خودت\n"
        "/cancel — لغو مکالمه‌ی جاری\n"
        "/help — همین راهنما"
    )
    if _is_admin(update.effective_user.id):
        text += (
            "\n\n👑 *دستورهای مدیر:*\n"
            "/stats — آمار کلی\n"
            "/export — خروجی CSV همه‌ی کاربران\n"
            "/broadcast <متن> — ارسال پیام همگانی\n"
            "/ban <آیدی> — مسدودکردن کاربر\n"
            "/unban <آیدی> — رفع مسدودی"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


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
    if not _is_admin(update.effective_user.id):
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


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return

    try:
        rows = database.get_all_submissions()
    except Exception:
        logger.exception("خطا در خواندن اطلاعات برای خروجی")
        await update.message.reply_text("مشکلی در ساخت خروجی پیش اومد.")
        return

    if not rows:
        await update.message.reply_text("هنوز هیچ رکوردی ثبت نشده.")
        return

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    csv_bytes.name = "cosmic_bot_users.csv"

    await update.message.reply_document(
        document=csv_bytes,
        filename="cosmic_bot_users.csv",
        caption=f"📋 لیست کامل کاربران ({len(rows)} رکورد)",
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return

    message_text = " ".join(context.args) if context.args else ""
    if not message_text:
        await update.message.reply_text("استفاده: /broadcast متن پیام همگانی")
        return

    try:
        user_ids = database.get_all_user_ids()
    except Exception:
        logger.exception("خطا در خواندن لیست کاربران")
        await update.message.reply_text("مشکلی در خواندن لیست کاربران پیش اومد.")
        return

    await update.message.reply_text(f"⏳ در حال ارسال پیام به {len(user_ids)} کاربر...")

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message_text)
            sent += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)  # جلوگیری از محدودیت نرخ تلگرام

    await update.message.reply_text(f"✅ ارسال شد به {sent} نفر. ناموفق: {failed}")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: /ban آیدی_عددی_تلگرام")
        return
    target_id = int(context.args[0])
    ok = database.ban_user(target_id)
    await update.message.reply_text("✅ مسدود شد." if ok else "کاربری با این آیدی پیدا نشد.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای مدیر ربات در دسترسه.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("استفاده: /unban آیدی_عددی_تلگرام")
        return
    target_id = int(context.args[0])
    ok = database.unban_user(target_id)
    await update.message.reply_text("✅ رفع مسدودی شد." if ok else "کاربری با این آیدی پیدا نشد.")


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
            BIRTH_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_day)],
            BIRTH_MONTH: [CallbackQueryHandler(get_birth_month, pattern="^month_")],
            BIRTH_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_year)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CallbackQueryHandler(history_from_button, pattern="^show_history$"))

    if application.job_queue is not None and ADMIN_ID:
        application.job_queue.run_daily(daily_backup_job, time=dt_time(hour=23, minute=55))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
