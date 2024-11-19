"""
Discord bot for announcing Elroy releases.
"""

import argparse
import os
import sys
from typing import Optional

import discord
from discord.ext import commands

GENERAL_CHANNEL_ID = 1307066378053877841
TEST_CHANNEL_ID = 1308566429779492874

# parent dir of script is the root of the project
CHANGELOG_LOCATION = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "CHANGELOG.md")


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

        description = f"A new version of Elroy has been released!\n\n"
        description += f"**Changes in this release:**\n{release_notes}\n\n"
        description += f"View the full release on GitHub: {release_url}"

        embed = discord.Embed(
            title=f"New Release: v{self.version}",
            url=release_url,
            description=description,
            color=discord.Color.green(),
        )

        await channel.send(embed=embed)  # type: ignore

    def _get_release_notes(self, version: str) -> Optional[str]:
        """Extract release notes from CHANGELOG.md for the given version"""
        if version.startswith("v"):
            version = version[1:]

        try:
            with open(CHANGELOG_LOCATION, "r") as f:
                content = f.read()

            # Find the section for this version
            sections = content.split("\n## [")

            for section in sections:
                if section.startswith(version):
                    # Extract everything up to the next section or end
                    notes = section.split("\n", 1)[1].strip()

                    # Format the notes nicely
                    formatted_notes = ""
                    current_section = ""

                    for line in notes.split("\n"):
                        line = line.strip()
                        if line.startswith("###"):
                            if current_section:
                                formatted_notes += "\n"
                            current_section = line.replace("###", "").strip()
                        elif line and not line.startswith("["):  # Skip links
                            if line.startswith("-"):
                                formatted_notes += f"• {line[1:].strip()}\n"
                            else:
                                formatted_notes += f"{line}\n"

                    return formatted_notes.strip()

            return None
        except Exception as e:
            print(f"Warning: Could not read release notes: {e}", file=sys.stderr)
            return None

    def run(self):
        """Run the bot"""
        self.bot.run(self.token)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Announce Elroy release on Discord")
    parser.add_argument("version", help="Version number to announce")
    parser.add_argument("--test", action="store_true", help="Use test channel instead of general")
    args = parser.parse_args()

    channel_id = TEST_CHANNEL_ID if args.test else GENERAL_CHANNEL_ID
    bot = ReleaseBot(channel_id, os.environ["ELROY_DISCORD_TOKEN"], args.version)
    bot.run()


if __name__ == "__main__":
    main()
