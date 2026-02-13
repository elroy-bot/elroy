#!/usr/bin/env python3
"""
Discord bot for announcing Elroy releases.
"""

import argparse
import os
import sys

import discord
from discord.ext import commands

ANNOUNCEMENTS_CHANNEL_ID = 1309680926745169930
TEST_CHANNEL_ID = 1308566429779492874

# Find project root (3 levels up from this script)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHANGELOG_LOCATION = os.path.join(PROJECT_ROOT, "CHANGELOG.md")


class ReleaseBot:
    """Discord bot for announcing releases"""

    def __init__(self, channel_id: int, token: str, version: str):
        self.channel_id = channel_id
        self.token = token
        self.version = version
        intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix="!", intents=intents)

        @self.bot.event
        async def on_ready():
            print(f"{self.bot.user} has connected to Discord!")
            await self._announce_release()
            await self.bot.close()

    def _get_release_url(self, version: str) -> str:
        """Get the GitHub release URL"""
        if version.startswith("v"):
            version = version[1:]
        return f"https://github.com/elroy-bot/elroy/releases/tag/v{version}"

    async def _announce_release(self):
        """Announce the release in the configured channel"""
        channel = self.bot.get_channel(self.channel_id)

        if not channel:
            print(f"Error: Could not find channel with ID {self.channel_id}", file=sys.stderr)
            sys.exit(1)

        release_url = self._get_release_url(self.version)
        release_notes = self._get_release_notes(self.version)

        description = "A new version of Elroy has been released!\n\n"
        description += f"**Changes in this release:**\n{release_notes}\n\n"
        description += f"View the full release on GitHub: {release_url}"

        embed = discord.Embed(
            title=f"New Release: v{self.version}",
            url=release_url,
            description=description,
            color=discord.Color.green(),
        )

        await channel.send(embed=embed)  # type: ignore

    def _get_release_notes(self, version: str) -> str | None:
        """Extract release notes from CHANGELOG.md for the given version"""
        if version.startswith("v"):
            version = version[1:]

        if not os.path.exists(CHANGELOG_LOCATION):
            print(f"Warning: CHANGELOG.md not found at {CHANGELOG_LOCATION}", file=sys.stderr)
            sys.exit(1)

        try:
            with open(CHANGELOG_LOCATION) as f:
                content = f.read()

            # Find the section for this version
            # Look for "## [version]" pattern
            version_pattern = f"## [{version}]"
            start_idx = content.find(version_pattern)

            if start_idx == -1:
                return None

            # Find the start of the next version section or end of file
            next_version_idx = content.find("\n## [", start_idx + 1)
            section_content = content[start_idx:] if next_version_idx == -1 else content[start_idx:next_version_idx]

            # Extract lines after the version header
            lines = section_content.split("\n")[1:]  # Skip the version line

            formatted_notes = ""
            current_section = ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("### "):
                    # Section header (Added, Improved, Fixed, etc.)
                    if formatted_notes and not formatted_notes.endswith("\n\n"):
                        formatted_notes += "\n"
                    current_section = line.replace("### ", "**") + "**\n"
                    formatted_notes += current_section
                elif line.startswith("- "):
                    # Bullet point
                    formatted_notes += f"• {line[2:]}\n"
                elif line.startswith("    - "):
                    # Sub-bullet point (indented)
                    formatted_notes += f"  ◦ {line[6:]}\n"
                elif not line.startswith("##") and not line.startswith("["):
                    # Regular text (but skip other section headers and links)
                    formatted_notes += f"{line}\n"

            return formatted_notes.strip() if formatted_notes.strip() else None

        except Exception as e:
            print(f"Warning: Could not read release notes: {e}", file=sys.stderr)
            sys.exit(1)

    def run(self):
        """Run the bot"""
        self.bot.run(self.token)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Announce Elroy release on Discord")
    parser.add_argument("version", help="Version number to announce")
    parser.add_argument("--test", action="store_true", help="Use test channel instead of general")
    args = parser.parse_args()

    channel_id = TEST_CHANNEL_ID if args.test else ANNOUNCEMENTS_CHANNEL_ID
    bot = ReleaseBot(channel_id, os.environ["ELROY_DISCORD_TOKEN"], args.version)
    bot.run()


if __name__ == "__main__":
    main()
