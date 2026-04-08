import discord
from discord.ext import commands
import yt_dlp
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Queue per guild
queues = {}


# ------------------ HELPERS ------------------

async def play_next(ctx):
    guild_id = ctx.guild.id
    voice = ctx.voice_client

    if guild_id not in queues or not queues[guild_id]:
        return

    url = queues[guild_id].pop(0)

    ydl_opts = {'format': 'bestaudio/best', 'quiet': True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']

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

    await ctx.send(f"Joined {channel}")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected.")
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

    queue = queues[guild_id]

    queue.append(url)

    if not ctx.voice_client.is_playing():
        await ctx.send("Playing...")
        await play_next(ctx)
    else:
        await ctx.send("Added to queue.")


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped.")
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused.")
    else:
        await ctx.send("Nothing is playing.")


@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed.")
    else:
        await ctx.send("Nothing is paused.")


@bot.command()
async def stop(ctx):
    guild_id = ctx.guild.id

    if ctx.voice_client:
        ctx.voice_client.stop()

    if guild_id in queues:
        queues[guild_id].clear()

    await ctx.send("Stopped and cleared queue.")


@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id

    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("Queue is empty.")
        return

    q = queues[guild_id]
    msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(q)])

    await ctx.send(f"Queue:\n{msg}")

@bot.command()
async def clearqueue(ctx):
    guild_id = ctx.guild.id

    if guild_id in queues:
        queues[guild_id].clear()
        await ctx.send("🧹 Queue cleared.")
    else:
        await ctx.send("Queue is already empty.")

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

    await ctx.send(f"🗑️ Removed from queue:\n{removed}")


# ------------------ RUN BOT ------------------

bot.run(token)