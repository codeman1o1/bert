import os
from datetime import timedelta
from typing import List

import discord
from discord.commands import option
from discord.ext import commands
from generic import logger
from ollama import AsyncClient

ollama = AsyncClient(os.getenv("OLLAMA_URL"))

TOO_LONG_MSG = " **[MESSAGE TOO LONG]**"


async def download_ai_models(models: List[str]):
    """Download the AI models from the Ollama server."""
    downloaded_models = await ollama.list()
    for model in models.copy():
        if any(
            m.model.replace(":latest", "") == model for m in downloaded_models.models
        ):
            models.remove(model)
    if not models:
        return
    logger.debug("Downloading %s AI models (%s)", len(models), ", ".join(models))
    for model in models:
        logger.debug("Downloading %s...", model)
        await ollama.pull(model=model)


async def autocomplete_models(ctx: discord.AutocompleteContext):
    """Autocomplete the AI models from the Ollama server."""
    models = await ollama.list()
    return [
        discord.OptionChoice(model.model.split(":")[0])
        for model in models.models
        if ctx.value in model.model.split(":")[0]
    ]


class AICog(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bert = bot
        self._models_downloaded = False

    @commands.slash_command(
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        }
    )
    @option("prompt", description="The prompt to give to the AI")
    @option("model", description="The model to use", autocomplete=autocomplete_models)
    async def ai(
        self, ctx: discord.ApplicationContext, prompt: str, model: str = "llama3.2"
    ):
        """Bert AI Technologies Ltd."""
        await ctx.defer()
        ai_response = await ollama.generate(model, prompt)
        if response := ai_response.response:
            if len(response) > 2000:
                await ctx.send_followup(
                    response[: 2000 - len(TOO_LONG_MSG)] + TOO_LONG_MSG
                )
            else:
                await ctx.send_followup(response)
        else:
            await ctx.send_followup("_No response from AI_")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._models_downloaded:
            # To avoid checking when Discord reconnects due to network issues
            await download_ai_models(["llama2-uncensored", "llava"])
            self._models_downloaded = True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            isinstance(message.channel, discord.TextChannel)
            and message.channel.name != "bert-ai"
        ) or message.author.bot:
            return

        available_models = [
            model.model.split(":")[0] for model in (await ollama.list()).models
        ]
        model = "llama2-uncensored"

        if message.content == "bert clear":
            await message.channel.send("Understood. ||bert-ignore||")
            return

        if message.content.startswith("bert model"):
            if len(message.content.split(" ")) == 2:
                history = await message.channel.history(
                    limit=100,
                    before=message.created_at,
                    after=message.created_at - timedelta(minutes=10),
                ).flatten()
                history.reverse()
                for msg in history:
                    if "bert-ignore" not in msg.content and not msg.author.bot:
                        if msg.content == "bert clear":
                            break
                        if (
                            msg.content.startswith("bert model ")
                            and msg.content.split(" ")[2] in available_models
                        ):
                            model = msg.content.split(" ")[2]
                            break
                await message.channel.send(f"Current model is {model}. ||bert-ignore||")
            elif (model := message.content.split(" ")[2]) in available_models:
                await message.channel.send(f"Model set to {model}. ||bert-ignore||")
            else:
                await message.channel.send(
                    f"Model {model} is not available. ||bert-ignore||"
                )
            return

        async with message.channel.typing():
            images = []
            for sticker in message.stickers:
                if sticker.format.name in ("png", "apng"):
                    images.append(await sticker.read())
            for attachment in message.attachments:
                if attachment.content_type.startswith("image"):
                    images.append(await attachment.read())

            messages = []
            history = await message.channel.history(
                limit=100,
                before=message.created_at,
                after=message.created_at - timedelta(minutes=10),
                oldest_first=True,
            ).flatten()
            for msg in history:
                if "bert-ignore" not in msg.content:
                    if msg.author.bot:
                        if msg.author == self.bert.user:
                            messages.append(
                                {"role": "assistant", "content": msg.content}
                            )
                    elif msg.content == "bert clear":
                        messages.clear()
                    elif msg.content.startswith("bert model "):
                        if msg.content.split(" ")[2] in available_models:
                            model = msg.content.split(" ")[2]
                    else:
                        images_ = []
                        for sticker in msg.stickers:
                            if sticker.format.name in ("png", "apng"):
                                images_.append(await sticker.read())
                        for attachment in msg.attachments:
                            if attachment.content_type.startswith("image"):
                                images_.append(await attachment.read())

                        messages.append(
                            {"role": "user", "content": msg.content, "images": images_}
                        )
            messages.append(
                {"role": "user", "content": message.content, "images": images}
            )

            ai_reply = await ollama.chat(
                "llava" if images else model, messages=messages
            )

            if response := ai_reply.message.content:
                if len(response) > 2000:
                    await message.channel.send(
                        response[: 2000 - len(TOO_LONG_MSG)] + TOO_LONG_MSG
                    )
                else:
                    await message.channel.send(response)
            else:
                await message.channel.send("_No response from AI_")


def setup(bot: discord.Bot):
    bot.add_cog(AICog(bot))
