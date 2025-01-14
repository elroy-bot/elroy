"""
An interactive D&D-style game where players can interact with multiple AI characters.
Each character maintains their own memories and personality while sharing a common narrative.
"""

from typing import Dict, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from elroy.api import Elroy


class Character:
    def __init__(self, player_name: str, assistant_name: str, persona: str, text_color: str):
        self.text_color = text_color
        self.name = assistant_name
        self.ai = Elroy(token=f"{player_name}_{assistant_name}", persona=persona, assistant_name=assistant_name)

    def message(self, input: str) -> str:
        return self.ai.message(input)

    def remember(self, message: str, name: Optional[str]):
        self.ai.remember(message, name)


class ElroyQuestGame:
    def __init__(self, player_name: str):
        self.player_name = player_name
        self.characters: Dict[str, Character] = {}
        self.console = Console()

    def add_character(self, assistant_name: str, persona: str, text_color: str):
        self.characters[assistant_name] = Character(self.player_name, assistant_name, persona, text_color)

    def print_character_list(self):
        table = Table(title="Available Characters")
        table.add_column("Name", style="cyan")
        table.add_column("Role", style="magenta")

        for name, char in self.characters.items():
            table.add_row(name, char.ai.get_persona()[:50] + "...")

        self.console.print(table)

    def create_shared_memory(self, message: str):
        """Create a memory shared by all characters"""
        self.console.print(Panel(f"[yellow]Creating shared memory:[/yellow]\n{message}", title="Shared Memory"))
        for character in self.characters.values():
            character.remember(message, None)

    def run_game(self):
        self.console.print(Markdown("# Welcome to the Elroy Quest Game!"))

        while True:
            self.console.print("\n[bold cyan]What would you like to do?[/bold cyan]")
            self.console.print("1. Talk to a character")
            self.console.print("2. Create a shared memory")
            self.console.print("3. List characters")
            self.console.print("4. Exit")

            choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4"])

            if choice == "1":
                self.print_character_list()
                character_name = Prompt.ask("Which character would you like to talk to?", choices=list(self.characters.keys()))
                message = Prompt.ask("What would you like to say?")

                character = self.characters[character_name]
                response = character.message(message)

                self.console.print(Panel(f"[{character.text_color}]{response}[/{character.text_color}]", title=f"{character_name} says"))

            elif choice == "2":
                memory = Prompt.ask("Enter the shared memory")
                self.create_shared_memory(memory)

            elif choice == "3":
                self.print_character_list()

            elif choice == "4":
                self.console.print("[bold red]Goodbye![/bold red]")
                break


import typer

app = typer.Typer()


@app.command()
def run_quest(player_name: str = typer.Option("player1", "--player-name", "-p", help="Your player name")):
    game = ElroyQuestGame(player_name)

    # Add some D&D characters
    game.add_character(
        "Gandalf", "You are Gandalf the Grey, a wise and powerful wizard. You speak in riddles and offer cryptic advice.", "grey70"
    )

    game.add_character(
        "Aragorn",
        "You are Aragorn, a noble ranger and heir to the throne of Gondor. You are brave, honorable, and protective of others.",
        "green",
    )

    game.add_character(
        "Gimli",
        "You are Gimli, son of Glóin, a proud dwarf warrior. You are gruff but loyal, and have a friendly rivalry with elves.",
        "red",
    )

    # Create some initial shared context
    game.create_shared_memory(
        "The party has gathered in the Prancing Pony inn in Bree. "
        "Dark riders have been seen on the road, and there are whispers of growing darkness in the East."
    )

    # Run the interactive game
    game.run_game()


if __name__ == "__main__":
    app()
