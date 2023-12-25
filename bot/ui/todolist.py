import discord
from db import db
from discord.interactions import Interaction


class AddModal(discord.ui.Modal):
    def __init__(self, msg: discord.Message):
        super().__init__(title="Add Todo Item")
        self.add_item(discord.ui.InputText(label="Name"))
        self.add_item(discord.ui.InputText(label="Description"))
        self.msg = msg

    async def callback(self, interaction: Interaction):
        name_in_use = db.execute(
            "SELECT * FROM todo WHERE name = %s AND guild = %s",
            (self.children[0].value, interaction.guild.id),
        ).fetchone()
        if name_in_use is not None:
            await interaction.response.send_message(
                "That name is already in use", ephemeral=True
            )
            return
        db.execute(
            "INSERT INTO todo (name, description, owner, guild) VALUES (%s, %s, %s, %s)",
            (
                self.children[0].value,
                self.children[1].value,
                interaction.user.id,
                interaction.guild.id,
            ),
        )
        db.commit()
        await interaction.response.send_message(
            f"Added todo item **{self.children[0].value}**", ephemeral=True
        )
        self.msg.embeds[0].add_field(
            name=self.children[0].value, value=self.children[1].value
        )
        await self.msg.edit(embed=self.msg.embeds[0])


class DeleteSelect(discord.ui.Select):
    def __init__(self, userId: int, guildId: int, msg: discord.Message):
        results = db.execute(
            "SELECT * FROM todo WHERE owner = %s AND guild = %s", (userId, guildId)
        ).fetchmany()
        options = [
            discord.SelectOption(label=row[1], value=str(row[0]), description=row[2])
            for row in results
        ]
        super().__init__(placeholder="Please select a todo item", options=options)
        self.msg = msg

    async def callback(self, interaction: Interaction):
        deleted = db.execute(
            "DELETE FROM todo WHERE id = %s AND guild = %s RETURNING *",
            (self.values[0], interaction.guild.id),
        ).fetchone()
        await interaction.response.send_message(
            f"Deleted todo item **{deleted[1]}**", ephemeral=True
        )

        for i, field in enumerate(self.msg.embeds[0].fields):
            if field.name == deleted[1]:
                del self.msg.embeds[0].fields[i]
                break
        await self.msg.edit(embed=self.msg.embeds[0])


class DeleteView(discord.ui.View):
    def __init__(self, userId: int, guildId: int, msg: discord.Message):
        super().__init__()
        self.add_item(DeleteSelect(userId, guildId, msg))


class Todolist(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Add", style=discord.ButtonStyle.success, emoji="➕", custom_id="todo-add"
    )
    async def add_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.send_modal(AddModal(self.message))

    @discord.ui.button(
        label="Delete",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        custom_id="todo-delete",
    )
    async def delete_callback(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.send_message(
            view=DeleteView(interaction.user.id, interaction.guild.id, self.message),
            ephemeral=True,
        )
