import discord
from discord.ext import commands
import yt_dlp
import asyncio
from dotenv import load_dotenv
import os

# ------------------ LOAD TOKEN ------------------

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

if not token:
    raise ValueError("DISCORD_TOKEN is missing from .env")

# ------------------ INTENTS ------------------

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------ QUEUE ------------------

queues = {}

# ------------------ HELPERS ------------------

async def auto_disconnect(ctx, timeout=300):
    await asyncio.sleep(timeout)

    voice = ctx.voice_client
    guild_id = ctx.guild.id

    if not voice:
        return

    if voice.is_playing():
        return

    if guild_id in queues and queues[guild_id]:
        return

    await ctx.send("⏳ No activity. Leaving voice channel.")
    await voice.disconnect()


async def play_next(ctx):
    guild_id = ctx.guild.id
    voice = ctx.voice_client

    if not voice:
        return

    if guild_id not in queues or not queues[guild_id]:
        asyncio.create_task(auto_disconnect(ctx))
        return

    item = queues[guild_id].pop(0)
    url = item["url"]

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'skip_download': True,
        'cookiefile': 'cookie.txt'
    }

    loop = asyncio.get_running_loop()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        if 'entries' in info:
            info = info['entries'][0]

        formats = info.get('formats', [])
        audio_formats = [f for f in formats if f.get('acodec') != 'none']

        if not audio_formats:
            raise Exception("No audio formats found")

        best_audio = max(audio_formats, key=lambda x: x.get('abr') or 0)
        audio_url = best_audio['url']

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)

    def after_play(err):
        if err:
            print(err)

        fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(e)

    voice.play(source, after=after_play)


# ------------------ EVENTS ------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_voice_state_update(member, before, after):
    for voice in bot.voice_clients:
        if not voice.channel:
            continue

        if member == bot.user:
            continue

        humans = [m for m in voice.channel.members if not m.bot]

        if len(humans) == 0:
            print("Channel empty, leaving...")
            await voice.disconnect()


# ------------------ COMMANDS ------------------

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first.")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I'm not in a voice channel.")


@bot.command()
async def play(ctx, url):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Join a voice channel first.")
            return

    guild_id = ctx.guild.id

    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append({
        "url": url,
        "title": "Song"
    })

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
    else:
        await ctx.send("Nothing is paused.")


@bot.command()
async def stop(ctx):
    guild_id = ctx.guild.id

    if ctx.voice_client:
        ctx.voice_client.stop()

    if guild_id in queues:
        queues[guild_id].clear()


@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id

    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("Queue is empty.")
        return

    msg = "\n".join(
        [f"{i+1}. {item['title']}" for i, item in enumerate(queues[guild_id])]
    )

    await ctx.send(f"Queue:\n{msg}")


@bot.command()
async def clearqueue(ctx):
    guild_id = ctx.guild.id

    if guild_id in queues:
        queues[guild_id].clear()

    await ctx.send("🧹 Queue cleared.")


@bot.command()
async def remove(ctx, index: int):
    guild_id = ctx.guild.id

    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("Queue is empty.")
        return

    queue = queues[guild_id]

    if index < 1 or index > len(queue):
        await ctx.send("❌ Invalid index.")
        return

    removed = queue.pop(index - 1)

    await ctx.send(f"🗑️ Removed:\n{removed['title']}")


# ------------------ RUN ------------------

bot.run(token)