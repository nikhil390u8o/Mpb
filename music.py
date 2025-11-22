# musicbot.py - Telegram VC Music Bot for Google Cloud Shell
# Works with Pyrogram + pytgcalls (latest 2025)

import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputAudioStream
from pytgcalls.types.input_stream.quality import HighQualityAudio
from youtube_search import YoutubeSearch
import yt_dlp as youtube_dl

# ================= CONFIG =================
API_ID = "20898349"          # Change this
API_HASH = "9fdb830d1e435b785f536247f49e7d87"      # Change this
BOT_TOKEN = "7850782505:AAFVrhfJHMU1arp0CHTrpDdez70B0mZwHIc"    # Change this
SESSION_NAME = "musicbot_session"

# Replace with your values
# API_ID = 1234567
# API_HASH = "abcd1234efgh5678ijkl9012mnop3456"
# BOT_TOKEN = "7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

app = Client("musicbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call = PyTgCalls(app)

queue = []
current_song = None

# ================= YTDL OPTIONS =================
ytdl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'prefer_ffmpeg': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
}

# ================= COMMANDS =================

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text(
        "🎵 **Telegram VC Music Player Bot**\n\n"
        "Commands:\n"
        "/play <song name or youtube link> - Play music\n"
        "/pause - Pause stream\n"
        "/resume - Resume stream\n"
        "/skip - Skip current song\n"
        "/queue - Show queue\n"
        "/join - Join voice chat\n"
        "/leave - Leave voice chat\n\n"
        "Made with ❤️ for Google Cloud Shell",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Source Code", url="https://github.com/its-romeo/TG-VC-Bot")]
        ])
    )

@app.on_message(filters.command("join"))
async def join_vc(client, message: Message):
    chat_id = message.chat.id
    if await call.get_call(chat_id):
        return await message.reply("Already in voice chat!")
    
    try:
        await call.start()
        await call.join_group_call(chat_id, InputAudioStream("http://ngchn.audio:8000/stream"))  # silence until play
        await message.reply("✅ Joined voice chat!")
    except Exception as e:
        await message.reply(f"Error: {e}")

@app.on_message(filters.command("leave"))
async def leave_vc(client, message: Message):
    chat_id = message.chat.id
    try:
        await call.leave_group_call(chat_id)
        queue.clear()
        await message.reply("✅ Left voice chat and cleared queue.")
    except:
        await message.reply("Not in voice chat.")

@app.on_message(filters.command("play") & filters.group)
async def play_music(client, message: Message):
    chat_id = message.chat.id
    if len(message.command) == 1:
        return await message.reply("Usage: /play <song name or YouTube link>")

    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 Searching...")

    # Search or direct link
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            return await msg.edit("No results found!")
        url = f"https://youtube.com{results[0]['url_suffix']}"
        title = results[0]['title']

    await msg.edit(f"📥 Downloading: {title if 'title' in locals() else 'Song'}...")

    try:
        ydl = youtube_dl.YoutubeDL(ytdl_opts)
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        file_path = f"downloads/{info['id']}.mp3"
    except Exception as e:
        return await msg.edit(f"Download failed: {str(e)}")

    # Add to queue
    queue.append({"title": title, "file": file_path, "duration": duration, "requested_by": message.from_user.first_name})

    if len(queue) == 1:
        await msg.edit(f"▶️ Now Playing: **{title}**")
        await stream(chat_id, file_path)
    else:
        await msg.edit(f"Added to queue: **{title}** [{len(queue)-1} in queue]")

async def stream(chat_id, file_path):
    global current_song
    current_song = file_path

    try:
        await call.change_stream(
            chat_id,
            InputAudioStream(
                file_path,
                HighQualityAudio()
            )
        )
    except Exception as e:
        print(f"Stream error: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        if queue:
            queue.pop(0)
        if queue:
            next_song = queue[0]
            await stream(chat_id, next_song["file"])

# Auto skip when song ends
@call.on_stream_end()
async def on_stream_end(client, update):
    if queue:
        queue.pop(0)
    if queue:
        next_song = queue[0]
        await stream(update.chat_id, next_song["file"])
    else:
        global current_song
        current_song = None

@app.on_message(filters.command("skip"))
async def skip(client, message: Message):
    chat_id = message.chat.id
    if queue:
        queue.pop(0)
        await message.reply("⏩ Skipped!")
        if queue:
            next_song = queue[0]
            await stream(chat_id, next_song["file"])
    else:
        await message.reply("Queue is empty!")

@app.on_message(filters.command("pause"))
async def pause(client, message: Message):
    chat_id = message.chat.id
    await call.pause_stream(chat_id)
    await message.reply("⏸ Paused")

@app.on_message(filters.command("resume"))
async def resume(client, message: Message):
    chat_id = message.chat.id
    await call.resume_stream(chat_id)
    await message.reply("▶️ Resumed")

@app.on_message(filters.command("queue"))
async def show_queue(client, message: Message):
    if not queue:
        return await message.reply("Queue is empty!")
    
    text = "🎵 **Queue:**\n\n"
    for i, song in enumerate(queue[:10], 1):
        text += f"{i}. {song['title']} - {song['requested_by']}\n"
    if len(queue) > 10:
        text += f"\n... and {len(queue)-10} more."
    await message.reply(text)

# ================ RUN BOT =================
if not os.path.exists("downloads"):
    os.mkdir("downloads")

async def main():
    await app.start()
    await call.start()
    print("Bot is running... Press Ctrl+C to stop")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
