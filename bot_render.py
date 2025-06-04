import os
import re
import asyncio
import json
import tkinter as tk
import subprocess
from tkinter import scrolledtext, messagebox, Label
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from collections import deque

# إعدادات البوت
BOT_TOKEN = '805884352:AAF4q3TTYtPGbXsflSmqF2gc60YsOOv4z8Q'
ADMIN_ID = 7604170763
CHANNEL_USERNAME = '@flor3a1'
ADMIN_PASSWORD = "admin123"

# ملفات البيانات
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
BANNED_FILE = 'banned.json'

# متغيرات عامة
bot_running = False
app = None
user_platforms = {}
subscribers_count = set()
download_count = 0
user_ids = set()
invalid_attempts = {}
banned_users = set()
recent_downloads = deque(maxlen=5)
is_admin_logged_in = False

def load_stats():
    global subscribers_count, download_count, user_ids, banned_users
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
            subscribers_count = set(data.get("subscribers", []))
            download_count = data.get("downloads", 0)
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            user_ids = set(data.get("users", []))
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, 'r') as f:
            banned_users.update(json.load(f))

def save_stats():
    data = {
        "subscribers": list(subscribers_count),
        "downloads": download_count
    }
    with open(STATS_FILE, 'w') as f:
        json.dump(data, f)
    with open(USERS_FILE, 'w') as f:
        json.dump({"users": list(user_ids)}, f)
    with open(BANNED_FILE, 'w') as f:
        json.dump(list(banned_users), f)

def update_stats_labels():
    subs_label.config(text=f"\U0001F465 المشتركين: {len(subscribers_count)}")
    downloads_label.config(text=f"\U0001F4E5 التنزيلات: {download_count}")

async def check_subscription(user_id, bot, context):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            if user_id not in subscribers_count:
                subscribers_count.add(user_id)
                save_stats()
                update_stats_labels()
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
        keyboard = [[InlineKeyboardButton("\U0001F4E2 انضم إلى القناة", url=f'https://t.me/{CHANNEL_USERNAME[1:]}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"\u26A0\uFE0F يجب عليك الاشتراك في القناة @{CHANNEL_USERNAME[1:]} أولًا.", reply_markup=reply_markup)
        return
    keyboard = [
        [InlineKeyboardButton("\U0001F3A5 TikTok", callback_data='tiktok')],
        [InlineKeyboardButton("\U0001F3B5 YouTube", callback_data='youtube')],
        [InlineKeyboardButton("\U0001F4F8 Instagram", callback_data='instagram')]
    ]
    await update.message.reply_text('مرحبًا! اختر الموقع الذي تريد تنزيل الفيديو منه:', reply_markup=InlineKeyboardMarkup(keyboard))

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
        await update.message.reply_text("\U0001F6AB تم حظرك مؤقتًا.")
        return
    if not await check_subscription(user_id, context.bot, context):
        await update.message.reply_text(f"\u26A0\uFE0F اشترك في القناة أولًا @{CHANNEL_USERNAME[1:]}")
        return
    if user_id not in user_platforms:
        await update.message.reply_text("❗ استخدم /start لاختيار المنصة.")
        return
    platform = user_platforms[user_id]
    patterns = {"tiktok": r'tiktok\.com', "youtube": r'youtube\.com|youtu\.be', "instagram": r'instagram\.com'}
    if not re.search(patterns[platform], url):
        invalid_attempts[user_id] = invalid_attempts.get(user_id, 0) + 1
        if invalid_attempts[user_id] >= 3:
            banned_users.add(user_id)
            save_stats()
            await update.message.reply_text("\U0001F6AB تم حظرك بسبب الاستخدام الخاطئ.")
        else:
            await update.message.reply_text("❌ الرابط غير صالح.")
        return
    log_message(f"\U0001F517 استقبال رابط ({platform}): {url}")
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
            await update.message.reply_text("⚠️ الملف أكبر من 50 ميجا.")
            os.remove(file_path)
            return
        await context.bot.send_video(chat_id=update.effective_chat.id, video=open(file_path, 'rb'))
        os.remove(file_path)
        download_count += 1
        save_stats()
        update_stats_labels()
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

def log_message(msg):
    console.insert(tk.END, msg + "\n")
    console.see(tk.END)
    if "http" in msg:
        link_log.config(state='normal')
        link_log.insert(tk.END, msg + "\n")
        link_log.config(state='disabled')
        link_log.see(tk.END)
        with open("links.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def open_links_file():
    filepath = "links.txt"
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("")
    try:
        os.startfile(filepath)
    except AttributeError:
        subprocess.call(["xdg-open", filepath])

def run_bot():
    global bot_running, app
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler, pattern="^(tiktok|youtube|instagram)$"))
        app.add_handler(MessageHandler(filters.Regex(re.compile(r'https?://', re.IGNORECASE)), download_video))
        bot_running = True
        log_message("✅ البوت يعمل الآن...")
        loop.run_until_complete(app.run_polling())
    except Exception as e:
        log_message(f"❌ خطأ: {e}")
        bot_running = False

def start_bot():
    global bot_running
    if not bot_running:
        Thread(target=run_bot, daemon=True).start()
    else:
        messagebox.showinfo("تشغيل", "البوت يعمل مسبقًا.")

def stop_bot():
    global bot_running
    bot_running = False
    log_message("🛑 تم الإيقاف.")

def admin_login():
    def verify():
        entered = password_entry.get()
        if entered == ADMIN_PASSWORD:
            global is_admin_logged_in
            is_admin_logged_in = True
            messagebox.showinfo("نجاح", "✅ تم تسجيل دخول الأدمن بنجاح.")
            login_window.destroy()
        else:
            messagebox.showerror("خطأ", "❌ كلمة المرور غير صحيحة.")

    login_window = tk.Toplevel(root)
    login_window.title("تسجيل دخول الأدمن")
    login_window.geometry("300x150")
    tk.Label(login_window, text="أدخل كلمة مرور الأدمن:", font=("Arial", 12)).pack(pady=10)
    password_entry = tk.Entry(login_window, show="*", font=("Arial", 12))
    password_entry.pack(pady=5)
    tk.Button(login_window, text="تسجيل الدخول", command=verify).pack(pady=10)

def show_user_status():
    if not is_admin_logged_in:
        messagebox.showerror("مرفوض", "❌ يجب تسجيل دخول الأدمن أولًا.")
        return
    status_window = tk.Toplevel(root)
    status_window.title("حالة المستخدمين")
    status_window.geometry("500x400")
    tk.Label(status_window, text="📊 حالة المستخدمين", font=("Arial", 14, "bold")).pack(pady=10)
    text_area = scrolledtext.ScrolledText(status_window, width=60, height=20, font=("Courier", 10))
    text_area.pack(padx=10, pady=5)
    for user in user_ids:
        banned = "✅" if user in banned_users else "❌"
        attempts = invalid_attempts.get(user, 0)
        text_area.insert(tk.END, f"معرّف: {user} | محاولات خاطئة: {attempts} | محظور: {banned}\n")

def unblock_user():
    if not is_admin_logged_in:
        messagebox.showerror("مرفوض", "❌ يجب تسجيل دخول الأدمن أولًا.")
        return
    def do_unblock():
        try:
            uid = int(entry.get())
            if uid in banned_users:
                banned_users.remove(uid)
                invalid_attempts[uid] = 0
                save_stats()
                messagebox.showinfo("نجاح", f"✅ تم إلغاء الحظر عن المستخدم: {uid}")
                unblock_window.destroy()
            else:
                messagebox.showwarning("غير محظور", "⚠️ هذا المستخدم غير محظور.")
        except:
            messagebox.showerror("خطأ", "❌ أدخل رقم معرف صحيح.")

    unblock_window = tk.Toplevel(root)
    unblock_window.title("إلغاء الحظر")
    unblock_window.geometry("300x150")
    tk.Label(unblock_window, text="أدخل معرف المستخدم:", font=("Arial", 12)).pack(pady=10)
    entry = tk.Entry(unblock_window, font=("Arial", 12))
    entry.pack(pady=5)
    tk.Button(unblock_window, text="إلغاء الحظر", command=do_unblock).pack(pady=10)

# واجهة Tkinter
root = tk.Tk()
root.title("بوت تحميل الفيديو")
root.geometry("700x600")
root.resizable(False, False)

tk.Label(root, text="بوت تحميل الفيديو مع سجل الروابط", font=("Arial", 16, "bold")).pack(pady=10)
stats_frame = tk.Frame(root)
stats_frame.pack(pady=5)
subs_label = Label(stats_frame, text="\U0001F465 المشتركين: 0", font=("Arial", 12))
subs_label.pack(side=tk.LEFT, padx=20)
downloads_label = Label(stats_frame, text="\U0001F4E5 التنزيلات: 0", font=("Arial", 12))
downloads_label.pack(side=tk.LEFT, padx=20)

control_frame = tk.Frame(root)
control_frame.pack(pady=5)
tk.Button(control_frame, text="\U0001F7E2 تشغيل البوت", width=15, command=start_bot).pack(side=tk.LEFT, padx=5)
tk.Button(control_frame, text="\U0001F534 إيقاف البوت", width=15, command=stop_bot).pack(side=tk.LEFT, padx=5)
tk.Button(control_frame, text="\U0001F512 دخول الأدمن", width=15, command=admin_login).pack(side=tk.LEFT, padx=5)
tk.Button(control_frame, text="\U0001F4CB حالة المستخدمين", width=15, command=show_user_status).pack(side=tk.LEFT, padx=5)
tk.Button(control_frame, text="\U0001F6D1 إلغاء الحظر", width=15, command=unblock_user).pack(side=tk.LEFT, padx=5)

console = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=10, font=("Courier", 10))
console.pack(padx=10, pady=10)

tk.Label(root, text="\U0001F4DC سجل الروابط:", font=("Arial", 12, "bold")).pack()
link_log = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=5, font=("Courier", 10), state='disabled')
link_log.pack(padx=10, pady=5)

tk.Button(root, text="\U0001F4C2 فتح سجل الروابط", command=open_links_file).pack(pady=5)

load_stats()
update_stats_labels()
log_message("ℹ️ الواجهة جاهزة. اضغط 'تشغيل البوت'.")

root.mainloop()
