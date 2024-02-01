import discord
import wavelink


class MusicView(discord.ui.View):
    async def setup_player(self, interaction: discord.Interaction) -> wavelink.Player:
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
        player.autoplay = wavelink.AutoPlayMode.partial
        return player


class AddBack(MusicView):
    def __init__(self, track):
        super().__init__()
        self.track: wavelink.Playable = track

    @discord.ui.button(label="Add back", style=discord.ButtonStyle.green, emoji="🔙")
    async def add_back(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        player = await self.setup_player(interaction)
        await player.queue.put_wait(self.track)
        if not player.playing:
            await player.play(player.queue.get(), volume=30)
        await interaction.response.send_message("Added back")
        button.disabled = True
        await interaction.followup.edit_message(
            message_id=interaction.message.id, view=self
        )


class RestoreQueue(MusicView):
    def __init__(self, queue):
        super().__init__()
        self.queue: wavelink.Queue = queue

    @discord.ui.button(label="Restore", style=discord.ButtonStyle.green, emoji="♻️")
    async def restore(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        player = await self.setup_player(interaction)
        for track in self.queue:
            await player.queue.put_wait(track)
        if not player.playing:
            await player.play(player.queue.get(), volume=30)
        await interaction.response.send_message("Queue restored")
        button.disabled = True
        await interaction.followup.edit_message(interaction.message.id, view=self)
