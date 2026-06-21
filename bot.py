import os
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8985933873:AAEgD6x_wNaOQbmnQadJzbWaH0bwiRd139c"

user_urls = {}
queue = asyncio.Queue()

progress_msg = {}

# ---------- ПРОГРЕСС БАР ----------
def bar(percent):
    filled = int(percent // 10)
    return "█" * filled + "░" * (10 - filled) + f" {percent:.1f}%"

async def edit_progress(chat_id, context, percent):
    text = f"📥 Скачивание...\n{bar(percent)}"

    if chat_id not in progress_msg:
        msg = await context.bot.send_message(chat_id, text)
        progress_msg[chat_id] = msg.message_id
    else:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg[chat_id],
            text=text
        )

# ---------- PROGRESS HOOK ----------
def hook_factory(chat_id, context):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)

            if total:
                percent = downloaded / total * 100
                asyncio.create_task(edit_progress(chat_id, context, percent))
    return hook

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 Отправь ссылку YouTube / TikTok"
    )

# ---------- ПОЛУЧЕНИЕ ССЫЛКИ ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_urls[chat_id] = update.message.text

    keyboard = [
        [InlineKeyboardButton("🎬 Видео (авто качество)", callback_data="video")],
        [InlineKeyboardButton("🎧 Аудио", callback_data="audio")]
    ]

    await update.message.reply_text(
        "Выбери формат:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- СКАЧИВАНИЕ ----------
async def download(chat_id, context, mode):
    url = user_urls.get(chat_id)

    if not url:
        return

    progress_msg.pop(chat_id, None)

    if mode == "audio":
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": f"{chat_id}.audio.%(ext)s"
        }
    else:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": f"{chat_id}.video.%(ext)s",
            "progress_hooks": [hook_factory(chat_id, context)]
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    file = None
    for f in os.listdir():
        if str(chat_id) in f:
            file = f
            break

    if mode == "audio":
        await context.bot.send_audio(chat_id, open(file, "rb"))
    else:
        await context.bot.send_message(chat_id, "📤 Отправляю видео...")
        await context.bot.send_video(chat_id, open(file, "rb"))

    os.remove(file)

# ---------- ОЧЕРЕДЬ ----------
async def worker(context):
    while True:
        chat_id, mode = await queue.get()
        await download(chat_id, context, mode)
        queue.task_done()

# ---------- КНОПКИ ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    mode = query.data

    await query.message.reply_text("⏳ Добавлено в очередь")
    await queue.put((chat_id, mode))

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button))

    loop = asyncio.get_event_loop()
    loop.create_task(worker(app.bot))

    print("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
