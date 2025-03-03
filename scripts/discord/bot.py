import os
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Optional, Union

import discord
from discord import app_commands
from discord.app_commands import CommandTree

from elroy.api import Elroy
from elroy.config.constants import USER
from elroy.config.personas import DISCORD_GROUP_CHAT_PERSONA
from elroy.io.formatters.markdown_formatter import MarkdownFormatter
from elroy.repository.user.tools import get_user_preferred_name, set_user_preferred_name

# TODO:
# - limit responses to 2000 characters
# - adjust system instruct to let elroy know when it's a dm or group dm

# Initialize Elroy
# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


# Initialize Discord client
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Required for slash commands
client = discord.Client(intents=intents)
tree = CommandTree(client)


class DiscordResponder(ABC):
    @abstractmethod
    def format_user_message(self, msg: discord.Message) -> str:
        """How the message should be represented in chat logs"""
        raise NotImplementedError

    @property
    @abstractmethod
    def user_token(self) -> str:
        raise NotImplementedError

    @cached_property
    @abstractmethod
    def ai(self) -> Elroy:
        raise NotImplementedError


class DMResponder(DiscordResponder):
    """Each channel gets its own instance"""

    def __init__(self, user_id: str):
        self.user_id = user_id

    @property
    def user_token(self) -> str:
        return f"discord-user-{self.user_id}"

    def format_user_message(self, msg: discord.Message) -> str:
        return msg.content

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            show_internal_thought=True,
            formatter=MarkdownFormatter(),
        )


class GroupDMResponder(DiscordResponder):
    def __init__(self, channel_id: str, author_name: str):
        self.channel_id = channel_id
        self.author_name = author_name

    @property
    def user_token(self) -> str:
        return f"discord-private-{self.channel_id}"

    def format_user_message(self, msg: discord.Message) -> str:
        return f"{msg.author.name}: {msg.content}"

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            show_internal_thought=True,
            formatter=MarkdownFormatter(),
            exclude_tools=[get_user_preferred_name.__name__, set_user_preferred_name.__name__],
            persona=DISCORD_GROUP_CHAT_PERSONA,
        )


class PublicChannelResponder(DiscordResponder):
    """Responder for public channels: One instance per guild"""

    def __init__(self, guild_id: str):
        self.guild_id = guild_id

    @property
    def user_token(self) -> str:
        return f"discord-guild-{self.guild_id}"

    def format_user_message(self, msg: discord.Message) -> str:
        # include both author and channel
        channel_name = getattr(msg.channel, "name", None)
        assert channel_name
        return f"{msg.author.name} in #{channel_name}: {msg.content}"

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            show_internal_thought=True,
            formatter=MarkdownFormatter(),
            exclude_tools=[get_user_preferred_name.__name__, set_user_preferred_name.__name__],
            persona=DISCORD_GROUP_CHAT_PERSONA,
        )


class PrivateChannelResponder(DiscordResponder):
    """Each channel gets its own instance"""

    def __init__(self, channel_id: str, guild_id: str):
        self.channel_id = channel_id
        self.guild_id = guild_id

    @property
    def user_token(self) -> str:
        return f"discord-private-{self.channel_id}"

    def format_user_message(self, msg: discord.Message) -> str:
        return f"{msg.author.name}: {msg.content}"

    @cached_property
    def ai(self) -> Elroy:
        return Elroy(
            token=self.user_token,
            show_internal_thought=True,
            formatter=MarkdownFormatter(),
            exclude_tools=[get_user_preferred_name.__name__, set_user_preferred_name.__name__],
        )


def get_discord_responder(input: Union[discord.Interaction, discord.Message]) -> DiscordResponder:
    if isinstance(input, discord.Interaction):
        if input.guild_id is None:
            # DM with bot
            return DMResponder(str(input.user.id))

        if input.channel is None:
            # Fallback to guild-wide responder if no channel context
            return PublicChannelResponder(str(input.guild_id))

        # Check if it's a public channel in guild
        if input.channel.type in (
            discord.ChannelType.text,  # 0
            discord.ChannelType.news,  # 5 (announcement)
            discord.ChannelType.news_thread,  # 10
            discord.ChannelType.public_thread,  # 11
            discord.ChannelType.forum,  # 15
            discord.ChannelType.media,  # 16
        ):
            return PublicChannelResponder(str(input.guild_id))
        else:
            # Private channel in guild
            return PrivateChannelResponder(str(input.channel_id), str(input.guild_id))
    else:
        # Handle regular messages
        if isinstance(input.channel, discord.DMChannel):
            return DMResponder(str(input.author.id))
        elif isinstance(input.channel, discord.GroupChannel):
            return GroupDMResponder(str(input.channel.id), input.author.name)
        elif input.guild is not None:
            # Check if public channel in guild
            if input.channel.type in (
                discord.ChannelType.text,  # 0
                discord.ChannelType.news,  # 5 (announcement)
                discord.ChannelType.news_thread,  # 10
                discord.ChannelType.public_thread,  # 11
                discord.ChannelType.forum,  # 15
                discord.ChannelType.media,  # 16
            ):
                return PublicChannelResponder(str(input.guild.id))
            else:
                return PrivateChannelResponder(str(input.channel.id), str(input.guild.id))
        else:
            # Fallback for unexpected cases
            return DMResponder(str(input.author.id))

    ...


def get_elroy(interaction: discord.Interaction):
    return get_discord_responder(interaction).ai


@tree.command(description="Creates a specific and measurable goal")
@app_commands.describe(
    goal_name="Name of the goal",
    strategy="Strategy to achieve the goal (max 100 words)",
    description="Brief description of the goal (max 100 words)",
    end_condition="Observable condition that indicates goal completion",
    time_to_completion="Time until completion (e.g. '1 DAYS', '2 WEEKS')",
    priority="Priority from 0-4 (0 highest, 4 lowest)",
)
async def create_goal(
    interaction: discord.Interaction,
    goal_name: str,
    strategy: Optional[str] = None,
    description: Optional[str] = None,
    end_condition: Optional[str] = None,
    time_to_completion: Optional[str] = None,
    priority: Optional[app_commands.Range[int, 0, 4]] = None,
):

    await interaction.response.send_message(
        get_elroy(interaction).create_goal(goal_name, strategy, description, end_condition, time_to_completion, priority)
    )


@tree.command(description="Add a status update or note to an existing goal")
@app_commands.describe(goal_name="Name of the goal to update", status_update_or_note="Status update or note to add (max 100 words)")
async def add_goal_status_update(interaction: discord.Interaction, goal_name: str, status_update_or_note: str):
    await interaction.response.send_message(get_elroy(interaction).add_goal_status_update(goal_name, status_update_or_note))


@tree.command(description="Mark a goal as completed")
@app_commands.describe(goal_name="Name of the goal to mark as completed", closing_comments="Final comments about the goal completion")
async def mark_goal_completed(interaction: discord.Interaction, goal_name: str, closing_comments: Optional[str] = None):
    await interaction.response.send_message(get_elroy(interaction).mark_goal_completed(goal_name, closing_comments))


@tree.command(description="Get a list of all active goals")
async def get_active_goal_names(interaction: discord.Interaction):
    names = get_elroy(interaction).get_active_goal_names()
    await interaction.response.send_message("\n".join(names) if names else "No active goals")


@tree.command(description="Get details about a specific goal")
@app_commands.describe(goal_name="Name of the goal to look up")
async def get_goal_by_name(interaction: discord.Interaction, goal_name: str):
    result = get_elroy(interaction).get_goal_by_name(goal_name)
    await interaction.response.send_message(result if result else "Goal not found")


@tree.command(description="Search through memories and goals")
@app_commands.describe(query="Search query to find relevant memories and goals")
async def query_memory(interaction: discord.Interaction, query: str):
    await interaction.response.send_message(get_elroy(interaction).query_memory(query))


@tree.command(description="Create a new memory")
@app_commands.describe(name="Name/title of the memory (should be specific and discuss one topic)", text="Content of the memory")
async def create_memory(interaction: discord.Interaction, name: str, text: str):
    await interaction.response.send_message(f"Memory created: {get_elroy(interaction).create_memory(name, text)}")


@tree.command(description="Get the current persona settings")
async def get_persona(interaction: discord.Interaction):
    await interaction.response.send_message(get_elroy(interaction).get_persona())


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")

    # Get the guild ID from environment variable
    guild_id = os.getenv("DISCORD_GUILD_ID")

    try:
        # Register commands globally (takes up to an hour)
        await tree.sync()
        print("Started global command sync (this can take up to an hour)")

        # If guild ID is provided, also register commands for that specific server
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                await tree.sync(guild=guild)
                print(f"Commands registered instantly for guild ID: {guild_id}")
            except ValueError:
                print("Invalid guild ID provided. Check DISCORD_GUILD_ID environment variable")
            except Exception as e:
                print(f"Error registering guild commands: {str(e)}")
        else:
            print("No guild ID provided, skipping guild command registration")
    except Exception as e:
        print(f"Error syncing commands: {str(e)}")


@client.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    responder = get_discord_responder(message)

    # Format message with user prefix
    formatted_message = responder.format_user_message(message)

    # Check if bot was mentioned
    was_mentioned = client.user in message.mentions
    is_dm = type(responder) == DMResponder

    if was_mentioned or is_dm:
        print(f"responding: was_mentioned={was_mentioned}, is_dm={is_dm}")
        # Process message through Elroy and get response
        response = responder.ai.message(formatted_message)
        print(response)
        await message.channel.send(response)
    else:
        # Record the message without generating a response
        responder.ai.record_message(USER, formatted_message)

    responder.ai.refresh_context_if_needed()


def main():
    if not DISCORD_TOKEN:
        raise ValueError("Please set the DISCORD_TOKEN environment variable")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
