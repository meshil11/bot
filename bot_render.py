import os
import re
import asyncio
import json
from collections import deque
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# إعدادات البوت
BOT_TOKEN = '8058484352:AAF4q3TTYtPGbXsflSmqF2gc60YsOOv4z8Q'
ADMIN_ID = 7604170763
CHANNEL_USERNAME = '@flor3a1'

# ملفات البيانات
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
BANNED_FILE = 'banned.json'

# متغيرات
user_platforms = {}
subscribers_count = set()
download_count = 0
user_ids = set()
invalid_attempts = {}
banned_users = set()
recent_downloads = deque(maxlen=5)

def load_stats():
    global subscribers_count, download_count, user_ids, banned_users
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
            subscribers_count.update(data.get("subscribers", []))
            download_count = data.get("downloads", 0)
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            user_ids.update(json.load(f).get("users", []))
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, 'r') as f:
            banned_users.update(json.load(f))

def save_stats():
    with open(STATS_FILE, 'w') as f:
        json.dump({"subscribers": list(subscribers_count), "downloads": download_count}, f)
    with open(USERS_FILE, 'w') as f:
        json.dump({"users": list(user_ids)}, f)
    with open(BANNED_FILE, 'w') as f:
        json.dump(list(banned_users), f)

async def check_subscription(user_id, bot, context):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            if user_id not in subscribers_count:
                subscribers_count.add(user_id)
                save_stats()
            return True
        return False
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_ids:
        user_ids.add(user_id)
        save_stats()
    is_subscribed = await check_subscription(user_id, context.bot, context)
    if not is_subscribed:
        keyboard = [[InlineKeyboardButton("🔔 انضم للقناة", url=f'https://t.me/{CHANNEL_USERNAME[1:]}')]]
        await update.message.reply_text(f"⚠️ يجب الاشتراك في القناة أولاً: {CHANNEL_USERNAME}", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    keyboard = [
        [InlineKeyboardButton("🎥 TikTok", callback_data='tiktok')],
        [InlineKeyboardButton("🎬 YouTube", callback_data='youtube')],
        [InlineKeyboardButton("📸 Instagram", callback_data='instagram')]
    ]
    await update.message.reply_text("اختر المنصة التي تريد التنزيل منها:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data
    user_platforms[query.from_user.id] = platform
    await query.edit_message_text(text=f"✅ تم اختيار {platform.capitalize()} كمصدر للتحميل.")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global download_count
    url = update.message.text.strip()
    user_id = update.effective_user.id

    if user_id in banned_users:
        await update.message.reply_text("🚫 تم حظرك.")
        return

    if not await check_subscription(user_id, context.bot, context):
        await update.message.reply_text("⚠️ اشترك في القناة أولًا.")
        return

    if user_id not in user_platforms:
        await update.message.reply_text("❗ استخدم /start لاختيار المنصة.")
        return

    platform = user_platforms[user_id]
    patterns = {
        "tiktok": r'tiktok\.com',
        "youtube": r'youtube\.com|youtu\.be|youtube\.com/shorts',
        "instagram": r'instagram\.com/(reel|p|tv)'
    }

    if not re.search(patterns[platform], url):
        invalid_attempts[user_id] = invalid_attempts.get(user_id, 0) + 1
        if invalid_attempts[user_id] >= 3:
            banned_users.add(user_id)
            save_stats()
            await update.message.reply_text("🚫 تم حظرك بسبب تكرار الأخطاء.")
        else:
            await update.message.reply_text("❌ الرابط غير صحيح.")
        return

    await update.message.reply_text("⏳ جاري التحميل...")
    try:
        from yt_dlp import YoutubeDL
        ydl_opts = {
            'outtmpl': '%(title)s.%(ext)s',
            'format': 'best[ext=mp4]',
            'quiet': True
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            await update.message.reply_text("⚠️ الفيديو أكبر من 50MB ولا يمكن رفعه.")
            os.remove(file_path)
            return

        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(file_path, 'rb'))
        os.remove(file_path)
        download_count += 1
        save_stats()

        with open("links.txt", "a", encoding="utf-8") as f:
            f.write(f"{platform}: {url}\n")

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def main():
    load_stats()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(tiktok|youtube|instagram)$"))
    app.add_handler(MessageHandler(filters.Regex(re.compile(r'https?://', re.IGNORECASE)), download_video))
    print("✅ البوت يعمل الآن...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())