# import asyncio
import base64
import contextlib
import logging
import os
import re
from asyncio import sleep
from datetime import datetime, timedelta
from random import choice, randint
from typing import List

import coloredlogs
import discord
import feedparser
import pytz
import wavelink
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ollama import AsyncClient

from db import DB
from ui.musik import AddBack, RestoreQueue
from ui.todolist import Todolist

load_dotenv()

bert = commands.Bot(
    command_prefix="bert ",
    intents=discord.Intents.all(),
    # debug_guilds=[870973430114181141, 1072785326168346706, 1182803938517455008],
)

nl_tz = pytz.timezone("Europe/Amsterdam")

ollama = AsyncClient(host=os.getenv("OLLAMA_URL") or "http://ai:11434")


class LogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        regexs = [
            r"^Shard ID (%s) has sent the (\w+) payload\.$",
            r"^Got a request to (%s) the websocket\.$",
            r"^Shard ID (%s) has connected to Gateway: (%s) \(Session ID: (%s)\)\.$",
            r"^Shard ID (%s) has successfully (\w+) session (%s) under trace %s\.$",
            r"^Websocket closed with (%s), attempting a reconnect\.$",
        ]
        # 0 means block, anything else (e.g. 1) means allow
        return next((0 for regex in regexs if re.match(regex, str(record.msg))), 1)


TEXT_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
handler.setFormatter(logging.Formatter(TEXT_FORMAT))

logger = logging.getLogger("bert")
logger.addHandler(handler)
coloredlogs.install(
    level=logging.DEBUG,
    logger=logger,
    fmt=TEXT_FORMAT,
)

pycord_logger = logging.getLogger("discord")
pycord_logger.addHandler(handler)
coloredlogs.install(
    level=logging.INFO,
    logger=pycord_logger,
    fmt=TEXT_FORMAT,
)

for pycord_handler in pycord_logger.handlers:
    pycord_handler.addFilter(LogFilter())


async def download_ai_models(models: List[str]):
    for model in models:
        await ollama.pull(model=model)


async def connect_nodes():
    """Connect to our Lavalink nodes."""
    await bert.wait_until_ready()

    nodes = [
        wavelink.Node(
            uri=os.getenv("LAVALINK_URL") or "http://lavalink:2333",
            password=os.getenv("LAVALINK_PASSWORD"),
        )
    ]
    await wavelink.Pool.connect(nodes=nodes, client=bert)


@tasks.loop(hours=1)
async def send_news_rss():
    current_time = datetime.now(nl_tz)
    past_hour = current_time - timedelta(hours=1)

    overheid_data = feedparser.parse("https://feeds.rijksoverheid.nl/nieuws.rss")
    data = overheid_data["entries"]
    news_items_as_embeds = []
    for entry in data:
        published_datetime = nl_tz.localize(datetime(*entry["published_parsed"][:6]))

        if published_datetime >= past_hour:
            title = entry["title"]
            description = entry["summary"]
            url = entry["link"]

            news_items_as_embeds.append(
                discord.Embed(
                    title=title,
                    description=description,
                    url=url,
                    timestamp=published_datetime,
                )
            )
            logger.debug("Found new news item: %s", title)
    if news_items_as_embeds:
        news_items_as_embeds.sort(key=lambda embed: embed.timestamp)
        channels = [
            channel
            for channel in bert.get_all_channels()
            if isinstance(channel, discord.TextChannel)
            and channel.topic
            and "bert-news" in channel.topic.lower()
        ]
        for channel in channels:
            await channel.send(embeds=news_items_as_embeds)
            await sleep(0.1)


@bert.event
async def on_ready():
    logger.info("%s is ready to hurt your brain", bert.user.name)

    logger.info("Connecting to Lavalink nodes")
    await connect_nodes()

    logger.info("Adding persistent views")
    for view in (Todolist(),):
        bert.add_view(view)

    if not send_news_rss.is_running():
        logger.info("Starting RSS feed task")
        send_news_rss.start()


@bert.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        if message.content:
            await message.channel.send(message.content)
        return

    if message.channel.name == "bert-ai":
        if message.attachments:
            base64_images = [
                await attachment.read()
                for attachment in message.attachments
                if attachment.content_type.startswith("image")
            ]
            ai_reply = await ollama.generate(
                model="llava",
                prompt="Describe the following image(s):",
                images=base64_images,
            )
        else:
            ai_reply = await ollama.generate(
                model="llama2-uncensored", prompt=message.content
            )

        await message.channel.send(ai_reply["response"])


@bert.event
async def on_member_join(member: discord.Member):
    if not member.bot:
        await member.guild.system_channel.send(f"bonjour {member.mention}")
        with contextlib.suppress(discord.Forbidden):
            await member.send(f"bonjour {member.mention}")
    elif bot_role := discord.utils.find(
        lambda role: role.name.lower() in ("bot", "bots"), member.guild.roles
    ):
        with contextlib.suppress(discord.Forbidden):
            await member.add_roles(bot_role)


@bert.event
async def on_member_remove(member: discord.Member):
    if not member.bot:
        await member.guild.system_channel.send(f"doeidoei {member.name}")
        with contextlib.suppress(discord.Forbidden):
            await member.send(f"doeidoei {member.name}")


@bert.event
async def on_guild_join(guild: discord.Guild):
    await guild.system_channel.send("bonjour me bert")


@bert.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if before.channel or not after.channel:
        # If the user is the last one to leave the voice channel, disconnect the bot
        if len(before.channel.members) == 1:
            if player := member.guild.voice_client:
                await player.disconnect()
        return

    if member.bot:
        if member != bert.user:
            return

        if after.mute:
            # Can't mute the bot hehehe
            await member.edit(mute=False)


@bert.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    if not payload.player:
        return

    if not payload.player.queue:
        await payload.player.disconnect()


@bert.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logger.info("Lavalink node %s is ready", payload.node.identifier)


@bert.slash_command(name="bert")
async def _bert(interaction: discord.Interaction):
    """bert"""
    await interaction.response.send_message(interaction.user.mention)


@bert.slash_command()
async def todo(interaction: discord.Interaction):
    """done"""
    result = DB.execute(
        "SELECT * FROM todos WHERE guild = %s", (interaction.guild.id,)
    ).fetchall()

    if result is None:
        await interaction.response.send_message("No todo items")
        return

    embed = discord.Embed(title="Todo List")
    for row in result:
        embed.add_field(name=row[1], value=row[2])
    await interaction.response.send_message(embed=embed, view=Todolist())


@bert.slash_command()
async def rapidlysendmessages(
    interaction: discord.Interaction, user: discord.Member, message: str, amount: int
):
    """fuck that guy"""
    we_should_follow_up = False
    snitch = randint(0, 1) == 1

    if not 0 < amount <= 25:
        await interaction.response.send_message(
            "Please choose a number between 1 and 25", ephemeral=snitch
        )
        return

    if user == bert.user:
        user = choice(
            [member for member in interaction.guild.members if not member.bot]
        )
        await interaction.response.send_message(
            f"im not gonna message myself lets do {user.mention} instead",
            ephemeral=snitch,
        )
        we_should_follow_up = True
    elif user == interaction.user:
        await interaction.response.send_message("sounds like suicide", ephemeral=snitch)
        we_should_follow_up = True

    if not we_should_follow_up:
        await interaction.response.send_message(
            f"Sending {amount} message{'s' if amount > 1 else ''} to {user.mention}...",
            ephemeral=snitch,
        )
    else:
        await interaction.followup.send(
            f"Sending {amount} message{'s' if amount > 1 else ''} to {user.mention}...",
            ephemeral=snitch,
        )

    try:
        for _ in range(amount):
            await user.send(message)
        await interaction.followup.send("Done!", ephemeral=snitch)
    except discord.Forbidden:
        await interaction.followup.send(
            "Could not send messages, most likely because"
            "the user has DM's from Bert blocked\n||stupid bitch||",
            ephemeral=snitch,
        )


@bert.slash_command()
async def play(
    interaction: discord.Interaction, query: str, channel: discord.VoiceChannel = None
):
    """Play a song or playlist"""
    if not interaction.user.voice and not channel:
        await interaction.response.send_message(
            "You are not in a voice channel", ephemeral=True
        )
        return

    if channel and not [member for member in channel.members if not member.bot]:
        await interaction.response.send_message(
            "That's an empty voice channel (or it only has bots)!", ephemeral=True
        )
        return

    tracks = await wavelink.Playable.search(query)
    if not tracks:
        await interaction.response.send_message("No tracks found")
        return

    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        try:
            if channel:
                player = await channel.connect(cls=wavelink.Player)
            else:
                player = await interaction.user.voice.channel.connect(
                    cls=wavelink.Player
                )
        except AttributeError:
            await interaction.response.send_message(
                "Please join a voice channel first before using this command.",
                ephemeral=True,
            )
            return
        except discord.ClientException:
            await interaction.response.send_message(
                "I was unable to join this voice channel. Please try again."
            )
            return

    player.autoplay = wavelink.AutoPlayMode.partial

    if isinstance(tracks, wavelink.Playlist):
        added = await player.queue.put_wait(tracks)
        await interaction.response.send_message(
            f"Added the playlist **`{tracks.name}`** ({added} songs) to the queue"
        )
    else:
        track = tracks[0]
        await player.queue.put_wait(track)
        await interaction.response.send_message(f"Added `{track.title}` to the queue")

    if not player.playing:
        await player.play(player.queue.get(), volume=30)


@bert.slash_command()
async def skip(interaction: discord.Interaction):
    """Skip the current song"""
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message("Not playing anything")
        return

    current_track = player.current

    await player.skip()
    await interaction.response.send_message(
        "Skipped the current song", view=AddBack(current_track)
    )


@bert.slash_command()
async def stop(interaction: discord.Interaction):
    """Stop playing"""
    player: wavelink.Player = interaction.guild.voice_client

    if not player:
        await interaction.response.send_message("Not playing anything")
        return

    current_queue = wavelink.Queue()
    await current_queue.put_wait(player.current)
    for track in player.queue:
        await current_queue.put_wait(track)

    await player.stop()
    await player.disconnect()
    await interaction.response.send_message(
        "Stopped playing", view=RestoreQueue(current_queue)
    )


# asyncio.run(download_ai_models(["llama2-uncensored", "llava"]))
bert.run(os.getenv("BOT_TOKEN"))
