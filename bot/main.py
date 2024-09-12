import asyncio
import base64
import binascii
import contextlib
import logging
import os
import re
import string
import sys
from asyncio import sleep
from datetime import UTC, datetime, time, timedelta
from random import choice, randint
from zoneinfo import ZoneInfo

import coloredlogs
import discord
import feedparser
import requests
import wavelink
from discord.commands import option
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pb import PB, pb_login
from pocketbase import PocketbaseError  # type: ignore
from ui.message import StoreMessage
from ui.musik import AddBack, RestoreQueue

load_dotenv()

bert = commands.Bot(
    command_prefix="bert ",
    intents=discord.Intents.all(),
    # debug_guilds=[870973430114181141, 1182803938517455008],
)

TZ = ZoneInfo(os.getenv("TZ") or "Europe/Amsterdam")


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

events = []
CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"
CALENDAR_HOLIDAY = r"nl.dutch%23holiday@group.v.calendar.google.com"
try:
    res = requests.get(
        f"{CALENDAR_BASE_URL}/{CALENDAR_HOLIDAY}/events?key={os.getenv('GOOGLE_API_KEY')}",
        timeout=10,
    )
    res.raise_for_status()
    events = res.json()["items"]
except requests.exceptions.RequestException as error:
    logger.error("Failed to fetch holidays: %s", error)
holidays = []
for event in events:
    start_date = datetime.strptime(event["start"]["date"], r"%Y-%m-%d").date()
    if start_date >= datetime.now().date():
        holidays.append(
            {
                "url": event["htmlLink"],
                "summary": event["summary"],
                "description": event["description"].split("\n")[0],
                "start": event["start"]["date"],
            }
        )
logger.info("Found %s upcoming holidays", len(holidays))


async def connect_nodes():
    """Connect to our Lavalink nodes."""
    await bert.wait_until_ready()

    nodes = [
        wavelink.Node(
            uri="http://lavalink:2333", password=os.getenv("LAVALINK_PASSWORD")
        )
    ]
    await wavelink.Pool.connect(nodes=nodes, client=bert)


@tasks.loop(hours=1)
async def send_news_rss():
    past_hour = datetime.now(TZ) - timedelta(hours=1)

    overheid_data = feedparser.parse("https://feeds.rijksoverheid.nl/nieuws.rss")
    data = overheid_data["entries"]
    news_items_as_embeds = []
    for entry in data:
        published = datetime(*entry["published_parsed"][:6], tzinfo=UTC)
        if published >= past_hour:
            title = entry["title"]
            description = entry["summary"]
            url = entry["link"]

            logger.debug("Found new news item: %s", title)
            news_items_as_embeds.append(
                discord.Embed(
                    title=title,
                    description=description,
                    url=url,
                    timestamp=published,
                )
            )
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


@tasks.loop(time=time(hour=12, minute=00, tzinfo=TZ))
async def send_holiday():
    today = datetime.now().date()
    for holiday in holidays.copy():
        holidate = datetime.strptime(holiday["start"], r"%Y-%m-%d").date()
        if holidate > today:
            break
        if holidate == today:
            embed = discord.Embed(
                title=holiday["summary"],
                description=holiday["description"],
                url=holiday["url"],
            )
            for guild in bert.guilds:
                if guild.system_channel:
                    await guild.system_channel.send(embed=embed)
            holidays.remove(holiday)


async def clean_db():
    channels = await PB.collection("vcmaker").get_full_list()
    deleted = 0
    for channel in channels:
        if not bert.get_channel(int(channel["channel"])):
            await PB.collection("vcmaker").delete(channel["id"])
            deleted += 1
    logger.info("Cleaned database (%s rows affected)", deleted)


@bert.event
async def on_ready():
    logger.info("%s is ready to hurt your brain", bert.user.name)

    logger.info("Connecting to Lavalink nodes")
    await connect_nodes()

    if not send_news_rss.is_running():
        logger.info("Starting RSS feed task")
        send_news_rss.start()

    if not send_holiday.is_running():
        logger.info("Starting holiday task")
        send_holiday.start()
    await clean_db()


@bert.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        if message.content:
            await message.channel.send(message.content)
        return

    if message.channel.name == "silence":
        await message.delete()
        return


@bert.event
async def on_member_join(member: discord.Member):
    if not member.bot:
        bonjour_msgs = (
            "bonjour",
            "hallo",
            "ghello",
            "goedendag",
            "goeiemorgen",
            "sinds wanneer ben jij hier",
            "oh god daar is",
            "d'r is er een jarig hoera hoera dat kun je wel zien dat is",
        )
        app_info = await bert.application_info()
        if member in app_info.team.members:
            await member.guild.system_channel.send(
                f"Ladies and gentlemen, please welcome {app_info.team.name} member **{member.display_name}**"
            )
        else:
            await member.guild.system_channel.send(
                f"{choice(bonjour_msgs)} {member.display_name}"
            )
        with contextlib.suppress(discord.Forbidden):
            await member.send(f"{choice(bonjour_msgs)} {member.display_name}")
    elif bot_role := discord.utils.find(
        lambda role: role.name.lower() in ("bot", "bots"), member.guild.roles
    ):
        with contextlib.suppress(discord.Forbidden):
            await member.add_roles(bot_role)


@bert.event
async def on_member_remove(member: discord.Member):
    if not member.bot:
        byebye_msgs = (
            "doeidoei",
            "byebye",
            "adios",
            "auf wiedersehen",
            "ciao",
            "tyf op",
            "krijg de tyfus",
            "kanker op",
            "krijg kanker",
            "krijg de tering",
            "pleur op",
            "stel je bent weg",
        )
        await member.guild.system_channel.send(
            f"{choice(byebye_msgs)} {member.display_name}"
        )
        with contextlib.suppress(discord.Forbidden):
            await member.send(f"{choice(byebye_msgs)} {member.display_name}")


@bert.event
async def on_guild_join(guild: discord.Guild):
    await guild.system_channel.send("bonjour me bert")


def get_most_playing_game(vc: discord.VoiceChannel):
    """returns the game that is played the most in a voice channel"""
    games = [
        activity.name
        for member in vc.members
        for activity in member.activities
        if activity.type == discord.ActivityType.playing
    ]
    return max(set(games), key=games.count) if games else None


async def determine_temp_vc_name(vc: discord.VoiceChannel) -> str:
    game = get_most_playing_game(vc)
    if game and len([member for member in vc.members if not member.bot]) > 1:
        return game
    result = await PB.collection("vcmaker").get_first(
        {"filter": f"channel='{str(vc.id)}'"}
    )
    owner = await bert.get_or_fetch_user(int(result["owner"]))
    return f"{owner.display_name}'s VC"


async def edit_vc_name(vc: discord.VoiceChannel, name: str) -> bool:
    """
    Edit the name of a voice channel if it's different from the desired name

    This is necessary because Discord has a ratelimit
    on editing channel names of 2 requests per 10 minutes

    Returns True if the name was changed, False if it wasn't
    """
    if vc.name != name:
        await vc.edit(name=name)
        return True
    return False


@bert.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if member.voice and member == bert.user and member.voice.mute:
        # Can't mute bert hehehe
        await member.edit(mute=False)
        return
    #mute command
    if before.mute and not after.mute and member.id in muted_users:
            await member.edit(mute=True)
            return
    if before.channel != after.channel:  # User moved channels
        if before.channel:
            if not [
                member for member in before.channel.members if not member.bot
            ]:  # No users are in the previous VC
                if player := member.guild.voice_client:
                    await player.disconnect()

                with contextlib.suppress(PocketbaseError):
                    row = await PB.collection("vcmaker").get_first(
                        {
                            "filter": f"channel='{str(before.channel.id)}' && type='TEMPORARY'"
                        }
                    )

                    with contextlib.suppress(
                        discord.errors.HTTPException
                    ):  # This event might have triggered again
                        await before.channel.delete()
                    await PB.collection("vcmaker").delete(row["id"])
            else:
                with contextlib.suppress(PocketbaseError):
                    await PB.collection("vcmaker").get_first(
                        {
                            "filter": f"channel='{str(before.channel.id)}' && type='TEMPORARY'"
                        }
                    )
                    vc_name = await determine_temp_vc_name(before.channel)
                    await edit_vc_name(before.channel, vc_name)

        if after.channel:
            with contextlib.suppress(PocketbaseError):
                result = await PB.collection("vcmaker").get_first(
                    {"filter": f"channel='{str(after.channel.id)}'"}
                )
                if result["type"] == "PERMANENT":
                    vc = await after.channel.guild.create_voice_channel(
                        f"{member.display_name}'s VC",
                        category=after.channel.category,
                    )
                    await member.move_to(vc)
                    await PB.collection("vcmaker").create(
                        {
                            "channel": str(vc.id),
                            "type": "TEMPORARY",
                            "owner": str(member.id),
                        }
                    )
                elif result["type"] == "TEMPORARY":
                    vc_name = await determine_temp_vc_name(after.channel)
                    await edit_vc_name(after.channel, vc_name)


@bert.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if before.activity == after.activity:
        return

    if after.voice:
        vc_name = await determine_temp_vc_name(after.voice.channel)
        await edit_vc_name(after.voice.channel, vc_name)


@bert.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    if not payload.player:
        return

    if not payload.player.queue:
        try:
            sounds = os.listdir("sounds")
        except FileNotFoundError:
            sounds = []
        if payload.track.source != "local" and sounds:
            bye_sound = await wavelink.Playable.search(
                f"sounds/{choice(sounds)}", source=None
            )
            await payload.player.play(bye_sound[0])
        else:
            await payload.player.disconnect()


@bert.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    logger.info("Lavalink node %s is ready", payload.node.identifier)


message_group = bert.create_group(
    "message",
    "message storage",
    integration_types={discord.IntegrationType.user_install},
)


@message_group.command()
async def store(interaction: discord.Interaction):
    """Store a message that can be retrieved later"""
    await interaction.response.send_modal(StoreMessage())


@message_group.command()
@option("key", description="The key of the message to retrieve")
async def load(interaction: discord.Interaction, key: str):
    """Retrieve a stored message"""
    try:
        row = await PB.collection("messages").get_first({"filter": f"id='{key}'"})
        await interaction.response.send_message(row["message"], ephemeral=True)
    except PocketbaseError:
        await interaction.response.send_message(
            "No message found with that key", ephemeral=True
        )


@message_group.command()
@option("key", description="The key of the message to delete")
async def delete(interaction: discord.Interaction, key: str):
    """Delete a stored message"""
    try:
        await PB.collection("messages").get_first(
            {"filter": f"id='{key}' && user_id='{str(interaction.user.id)}'"}
        )
        await PB.collection("messages").delete(key)
        await interaction.response.send_message("Message deleted", ephemeral=True)
    except PocketbaseError:
        await interaction.response.send_message(
            "No message found with that key", ephemeral=True
        )


@bert.slash_command(integration_types={discord.IntegrationType.user_install})
async def everythingisawesome(interaction: discord.Interaction):
    """Everything is AWESOME"""
    await interaction.response.send_message(
        """[Everything is awesome!
Everything is cool when you're part of a team!
Everything is awesome!
When you're living out a dream!
Everything thing is better when we stick together!
Side by side, you and I, gonna win forever!
Let's party forever!
We're the same, I'm like you, you're like me.
We're all working in harmony.
Everything is awesome!
Everything is cool when you're part of a team!
Everything is awesome!
When you're living out a dream!

Whoo!
Three, two, one, go. Have you heard the news?
Everyone's talking!
Life is good 'cause everything's awesome!
Lost my job, there's a new opportunity!
More free time for my awesome community!
I feel more awesome than an awesome possum!
Dip my body in chocolate frosting!
Three years later, wash off the frosting!
Smellin' like a blossom.
Everything is awesome!
Stepped in mud, got brand new shoes!
It's awesome to win and it's awesome to lose!

Everything is better when we stick together!
Side by side, you and I, gonna win forever!
Let's party forever!
We're the same, I'm like you, you're like me.
We're all working in harmony-y-y-y-y-y-y-y.
Everything is awesome!
Everything is cool when you're part of a team!
Everything is awesome!
When you're living out a dream.](https://youtu.be/g55SloahAj0)"""
    )


@bert.slash_command(name="bert")
async def _bert(interaction: discord.Interaction):
    """bert"""
    await interaction.response.send_message(interaction.user.mention)

muted_users = set()
unmutables = (747766456820695072,)

@bert.user_command()
@bert.slash_command()
async def mute(interaction: discord.Interaction, user: discord.Member):
    """Mute a user permanently"""
    if user == interaction.user:
        await interaction.response.send_message("You can't mute yourself", ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message("You can't mute a bot", ephemeral=True)
        return
    if user.id in muted_users:
        await interaction.response.send_message(f"{user.display_name} is already muted", ephemeral=True)
        return
    if user in (await bert.application_info()).team.members or user.id in unmutables:
        await interaction.response.send_message("nuh uh", ephemeral=True)
        return
    muted_users.add(user.id)
    await interaction.response.send_message(f"Muted {user.display_name}", ephemeral=True)
    if user.voice:
        await user.edit(mute=True)

@bert.user_command()
@bert.slash_command()
async def unmute(interaction: discord.Interaction, user: discord.Member):
    """Unmute a user"""
    if user == interaction.user:
        await interaction.response.send_message("You can't unmute yourself", ephemeral=True)
        return
    if user.bot:
        await interaction.response.send_message("You can't unmute a bot", ephemeral=True)
        return
    if user.id not in muted_users:
        await interaction.response.send_message(f"{user.display_name} is not muted", ephemeral=True)
        return
    if user in (await bert.application_info()).team.members or user.id in unmutables:
        await interaction.response.send_message("nuh uh", ephemeral=True)
        return
    muted_users.remove(user.id)
    await interaction.response.send_message(f"Unmuted {user.display_name}", ephemeral=True)
    if user.voice:
        await user.edit(mute=False)

@bert.slash_command()
@option("user", description="The user to send messages to")
@option("message", description="The message to send")
@option("amount", description="The amount of messages to send")
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


randomSlash = bert.create_group("random", "random thingies")


@randomSlash.command(name="number")
@option("minimum", description="the least it can generate (default: 0)")
@option("maximum", description="the most it can generate (default: 10)")
async def _number(
    interaction: discord.Interaction, minimum: int = 0, maximum: int = 10
):
    """random number"""
    if minimum > maximum:
        minimum, maximum = maximum, minimum

    await interaction.response.send_message(randint(minimum, maximum))


@randomSlash.command(name="string")
@option("length", description="how long the text should be (default: 10)")
async def _string(interaction: discord.Interaction, length: int = 10):
    """random string"""
    if length > 2000:
        await interaction.response.send_message("String length must be less than 2000")
        return
    if length < 1:
        await interaction.response.send_message("String length must be greater than 0")
        return
    await interaction.response.send_message(
        "".join(choice(string.ascii_letters + string.digits) for _ in range(length))
    )


@randomSlash.command(name="member")
async def _member(interaction: discord.Interaction):
    """random member"""
    await interaction.response.send_message(choice(interaction.guild.members).mention)


@randomSlash.command(name="role")
async def _role(interaction: discord.Interaction):
    """random role"""
    await interaction.response.send_message(choice(interaction.guild.roles).mention)


@randomSlash.command(name="channel")
async def _channel(interaction: discord.Interaction):
    """random channel"""
    await interaction.response.send_message(choice(interaction.guild.channels).mention)


base64Slash = bert.create_group("base64", "base64 cryptology")


@base64Slash.command(name="encode")
@option("text", description="the text")
async def base64_encode(interaction: discord.Interaction, text: str):
    """encode text to base64"""
    encoded = base64.b64encode(text.encode()).decode("utf-8")
    if len(encoded) > 2000:
        await interaction.response.send_message(
            "Encoded string is too long to send in Discord", ephemeral=True
        )
        return
    await interaction.response.send_message(encoded)


@base64Slash.command(name="decode")
@option("text", description="the text")
async def base64_decode(interaction: discord.Interaction, text: str):
    """decode base64 to text"""
    try:
        decoded = base64.b64decode(text.encode("utf-8")).decode("utf-8")
    except binascii.Error:
        await interaction.response.send_message("Invalid base64 string", ephemeral=True)
        return
    await interaction.response.send_message(decoded)


hexSlash = bert.create_group("hex", "hexadecimal cryptology")


@hexSlash.command(name="encode")
@option("text", description="the text")
async def hex_encode(interaction: discord.Interaction, text: str):
    """encode text to hexadecimal"""
    encoded = text.encode("utf-8").hex()
    if len(encoded) > 2000:
        await interaction.response.send_message(
            "Encoded string is too long to send in Discord", ephemeral=True
        )
        return
    await interaction.response.send_message(encoded)


@hexSlash.command(name="decode")
@option("text", description="the text")
async def hex_decode(interaction: discord.Interaction, text: str):
    """decode hexadecimal to text"""
    try:
        decoded = bytes.fromhex(text).decode("utf-8")
    except ValueError:
        await interaction.response.send_message(
            "Invalid hexadecimal string", ephemeral=True
        )
        return
    await interaction.response.send_message(decoded)


caesarSlash = bert.create_group("caesar", "caesar cryptology")


def caesar(text: str, shift: int):
    """Caesar cipher implementation"""
    return "".join(
        (
            chr((ord(char) - 65 + shift) % 26 + 65)
            if char.isupper()
            else chr((ord(char) - 97 + shift) % 26 + 97) if char.islower() else char
        )
        for char in text
    )


@caesarSlash.command(name="encode")
@option("text", description="the text")
@option("shift", description="displacement amount")
async def caesar_encode(interaction: discord.Interaction, text: str, shift: int):
    """encode text to caesar"""
    await interaction.response.send_message(caesar(text, shift))


@caesarSlash.command(name="decode")
@option("text", description="the text")
@option("shift", description="displacement amount")
async def caesar_decode(interaction: discord.Interaction, text: str, shift: int):
    """decode caesar to text"""
    await interaction.response.send_message(caesar(text, -shift))


binarySlash = bert.create_group("binary", "binary cryptology")


@binarySlash.command(name="encode")
@option("text", description="the text")
async def binary_encode(interaction: discord.Interaction, text: str):
    """encode text to binary"""
    encoded = " ".join(format(ord(char), "08b") for char in text)
    if len(encoded) > 2000:
        await interaction.response.send_message(
            "Encoded string is too long to send in Discord", ephemeral=True
        )
        return
    await interaction.response.send_message(encoded)


@binarySlash.command(name="decode")
@option("text", description="the text")
async def binary_decode(interaction: discord.Interaction, text: str):
    """decode binary to text"""
    try:
        decoded = "".join(chr(int(char, 2)) for char in text.split())
    except (OverflowError, ValueError):
        await interaction.response.send_message("Invalid binary string", ephemeral=True)
        return
    await interaction.response.send_message(decoded)


decimalSlash = bert.create_group("decimal", "decimal cryptology")


@decimalSlash.command(name="encode")
@option("text", description="the text")
async def decimal_encode(interaction: discord.Interaction, text: str):
    """encode text to decimal"""
    encoded = " ".join(str(ord(char)) for char in text)
    if len(encoded) > 2000:
        await interaction.response.send_message(
            "Encoded string is too long to send in Discord", ephemeral=True
        )
        return
    await interaction.response.send_message(encoded)


@decimalSlash.command(name="decode")
@option("text", description="the text")
async def decimal_decode(interaction: discord.Interaction, text: str):
    """decode decimal to text"""
    try:
        decoded = "".join(chr(int(char)) for char in text.split())
    except (OverflowError, ValueError):
        await interaction.response.send_message(
            "Invalid decimal string", ephemeral=True
        )
        return
    await interaction.response.send_message(decoded)


@bert.slash_command()
@option("category", description="the category to put the VC in")
async def makevcmaker(
    interaction: discord.Interaction, category: discord.CategoryChannel = None
):
    """Make a voice channel"""
    vc = await interaction.guild.create_voice_channel(
        "Join to create VC", category=category
    )
    await PB.collection("vcmaker").create({"channel": str(vc.id), "type": "PERMANENT"})
    await interaction.response.send_message(f"Created {vc.mention}")


async def get_videos(ctx: discord.AutocompleteContext):
    """search for videos"""
    try:
        tracks = await wavelink.Playable.search(ctx.value)
    except wavelink.exceptions.LavalinkLoadException:
        return []
    return [
        discord.OptionChoice(f"{track.title} - {track.author}"[:100], track.uri)
        for track in tracks
    ]


@bert.slash_command()
@option("query", description="what to search for", autocomplete=get_videos)
@option("channel", description="the voice channel to join (default: yours)")
async def play(
    interaction: discord.ApplicationContext,
    query: str,
    channel: discord.VoiceChannel = None,
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
        await interaction.response.send_message("No tracks found", ephemeral=True)
        return

    player: wavelink.Player | None = interaction.guild.voice_client

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
    player: wavelink.Player | None = interaction.guild.voice_client

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
    player: wavelink.Player | None = interaction.guild.voice_client

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


async def main():
    try:
        await pb_login()
    except PocketbaseError:
        logger.critical("Failed to login to Pocketbase")
        sys.exit(111)  # Exit code 111: Connection refused
    async with bert:
        await bert.start(os.getenv("BOT_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
