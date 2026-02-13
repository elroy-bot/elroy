#!/usr/bin/env python3
import logging
import os
from abc import ABC, abstractmethod
from functools import cached_property

import discord
from discord import app_commands
from discord.app_commands import CommandTree

from elroy.api import Elroy
from elroy.config.personas import DISCORD_GROUP_CHAT_PERSONA
from elroy.core.constants import USER
from elroy.io.formatters.markdown_formatter import MarkdownFormatter
from elroy.repository.user.tools import get_user_preferred_name, set_user_preferred_name

# Possible improvements:
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


def get_discord_responder(input: discord.Interaction | discord.Message) -> DiscordResponder:
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


@tree.command(description="Search through memories and reminders")
@app_commands.describe(query="Search query to find relevant memories and reminders")
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

    logging.info(f"Determined responder: {responder.__class__.__name__}")

    # Format message with user prefix
    formatted_message = responder.format_user_message(message)

    # Check if bot was mentioned
    was_mentioned = client.user in message.mentions
    is_dm = isinstance(responder, DMResponder)

    if was_mentioned or is_dm:
        logging.info(f"responding: was_mentioned={was_mentioned}, is_dm={is_dm}")
        # Process message through Elroy and get response
        response = responder.ai.message(formatted_message)
        logging.info(response)
        await message.channel.send(response)
    else:
        logging.info("Not a dm and wasn't mentioned, recording")
        # Record the message without generating a response
        responder.ai.record_message(USER, formatted_message)

    responder.ai.refresh_context_if_needed()


def main():
    if not DISCORD_TOKEN:
        raise ValueError("Please set the DISCORD_TOKEN environment variable")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,  # Default level for all loggers
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Logs to stderr
        ],
    )
    main()
