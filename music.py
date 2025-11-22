# musicbot.py - Telegram VC Music Bot (PyTgCalls v2 compatible)

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
API_ID = "20898349"           # Change this
API_HASH = "9fdb830d1e435b785f536247f49e7d87"  # Change this
BOT_TOKEN = "7850782505:AAFVrhfJHMU1arp0CHTrpDdez70B0mZwHIc" # Change this

app = Client("musicbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
call = PyTgCalls(app)

queue = []
current_song = None
playing_chat_id = None

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
        "🎵 Telegram VC Music Player Bot\n\n"
        "Commands:\n"
        "/play <song name or youtube link> - Play music\n"
        "/pause - Pause stream\n"
        "/resume - Resume stream\n"
        "/skip - Skip current song\n"
        "/queue - Show queue\n"
        "/join - Prepare bot\n"
        "/leave - Leave voice chat\n\n"
        "Made with ❤️ for Google Cloud Shell",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Source Code", url="https://github.com/its-romeo/TG-VC-Bot")]
        ])
    )

@app.on_message(filters.command("join"))
async def join_vc(client, message: Message):
    await call.start()
    await message.reply("✅ Bot is ready. Use /play <song> to start streaming.")

@app.on_message(filters.command("leave"))
async def leave_vc(client, message: Message):
    global queue, current_song, playing_chat_id
    chat_id = message.chat.id
    try:
        await call.leave_group_call(chat_id)
        queue.clear()
        current_song = None
        playing_chat_id = None
        await message.reply("✅ Left voice chat and cleared queue.")
    except Exception as e:
        await message.reply(f"Error: {e}")

@app.on_message(filters.command("play") & filters.group)
async def play_music(client, message: Message):
    global queue, current_song, playing_chat_id
    chat_id = message.chat.id
    if len(message.command) == 1:
        return await message.reply("Usage: /play <song name or YouTube link>")

    query = " ".join(message.command[1:])
    msg = await message.reply("🔍 Searching...")

    # Search or direct link
    if "youtube.com" in query or "youtu.be" in query:
        url = query
        title = None
    else:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if not results:
            return await msg.edit("No results found!")
        url = f"https://youtube.com{results[0]['url_suffix']}"
        title = results[0]['title']

    await msg.edit(f"📥 Downloading: {title if title else 'Song'}...")

    try:
        ydl = youtube_dl.YoutubeDL(ytdl_opts)
        info = ydl.extract_info(url, download=True)
        title = info.get('title', title or 'Unknown')
        duration = info.get('duration', 0)
        file_path = f"downloads/{info['id']}.mp3"
    except Exception as e:
        return await msg.edit(f"Download failed: {str(e)}")

    queue.append({"title": title, "file": file_path, "duration": duration, "requested_by": message.from_user.first_name, "chat_id": chat_id})

    if len(queue) == 1 and (current_song is None):
        await msg.edit(f"▶️ Now Playing: **{title}**")
        playing_chat_id = chat_id
        await stream(chat_id, file_path)
    else:
        await msg.edit(f"Added to queue: **{title}** [{len(queue)-1} in queue]")

async def stream(chat_id, file_path):
    global current_song, queue, playing_chat_id
    current_song = file_path
    playing_chat_id = chat_id

    try:
        in_call = False
        try:
            call_info = await call.get_call(chat_id)
            in_call = bool(call_info)
        except:
            in_call = False

        if not in_call:
            await call.join_group_call(chat_id, InputAudioStream(file_path, HighQualityAudio()))
        else:
            await call.change_stream(chat_id, InputAudioStream(file_path, HighQualityAudio()))

    except Exception as e:
        print(f"Stream error: {e}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        if queue:
            queue.pop(0)
        if queue:
            next_song = queue[0]
            await stream(chat_id, next_song["file"])
        else:
            current_song = None
            playing_chat_id = None

@call.on_stream_end()
async def on_stream_end(update):
    global queue, current_song, playing_chat_id
    if queue:
        queue.pop(0)
    if queue:
        next_song = queue[0]
        await stream(next_song["chat_id"], next_song["file"])
    else:
        current_song = None
        playing_chat_id = None

@app.on_message(filters.command("skip"))
async def skip(client, message: Message):
    global queue, current_song, playing_chat_id
    chat_id = message.chat.id
    if queue:
        queue.pop(0)
        await message.reply("⏩ Skipped!")
        if queue:
            next_song = queue[0]
            await stream(next_song["chat_id"], next_song["file"])
        else:
            try:
                await call.leave_group_call(chat_id)
            except:
                pass
            current_song = None
            playing_chat_id = None
    else:
        await message.reply("Queue is empty!")

@app.on_message(filters.command("pause"))
async def pause(client, message: Message):
    chat_id = message.chat.id
    try:
        await call.pause_stream(chat_id)
        await message.reply("⏸ Paused")
    except Exception as e:
        await message.reply(f"Unable to pause: {e}")

@app.on_message(filters.command("resume"))
async def resume(client, message: Message):
    chat_id = message.chat.id
    try:
        await call.resume_stream(chat_id)
        await message.reply("▶️ Resumed")
    except Exception as e:
        await message.reply(f"Unable to resume: {e}")

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
