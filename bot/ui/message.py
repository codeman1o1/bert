import discord
from discord.ui import Modal, InputText
from pb import PB


class StoreMessage(Modal):
    def __init__(self) -> None:
        super().__init__(title="Store a message")

        self.add_item(
            InputText(
                label="Message",
                placeholder="Enter your message here",
                max_length=2000,
                required=True,
                style=discord.InputTextStyle.long,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        row = await PB.collection("messages").create(
            {"message": self.children[0].value, "user_id": str(interaction.user.id)}
        )
        await interaction.response.send_message(
            f"Message stored with the key `{row['id']}`", ephemeral=True
        )
