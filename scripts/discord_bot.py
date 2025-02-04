import os
from typing import Optional

import discord
from discord import app_commands
from discord.app_commands import CommandTree

from elroy.api import Elroy
from elroy.config.constants import USER
from elroy.io.formatters.markdown_formatter import MarkdownFormatter

# Initialize Elroy
# Bot configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
REFRESH_AFTER_MESSAGES = 10  # Number of messages before context compression


# Initialize Discord client
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Required for slash commands
client = discord.Client(intents=intents)
tree = CommandTree(client)


def get_elroy(interaction: discord.Interaction):
    return Elroy(token=f"discord-{interaction.channel_id}", show_internal_thought=True, formatter=MarkdownFormatter())


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


# Message counter for each channel
channel_message_counts = {}


@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Initialize channel counter if it doesn't exist
    if message.channel.id not in channel_message_counts:
        channel_message_counts[message.channel.id] = 0
    elroy = Elroy(token=f"discord-{message.channel.id}", show_internal_thought=True, formatter=MarkdownFormatter())

    # Format message with user prefix
    formatted_message = f"{message.author.name}: {message.content}"

    # Check if bot was mentioned
    was_mentioned = client.user in message.mentions

    if was_mentioned:
        print("Was mentioned, responding")
        # Process message through Elroy and get response
        response = elroy.message(formatted_message)
        print(response)
        await message.channel.send(response)
        channel_message_counts[message.channel.id] += 2  # Increment by 2 since bot was mentioned
    else:
        # Record the message without generating a response
        elroy.record_message(USER, formatted_message)

        # Increment message counter for this channel
        channel_message_counts[message.channel.id] += 1

        # Check if we should refresh context
    if channel_message_counts[message.channel.id] >= REFRESH_AFTER_MESSAGES:
        elroy.context_refresh()

        # Reset counter
        channel_message_counts[message.channel.id] = 0


def main():
    if not DISCORD_TOKEN:
        raise ValueError("Please set the DISCORD_TOKEN environment variable")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
